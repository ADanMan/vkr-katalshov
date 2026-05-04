"""
flv.llm_extractor — Роль 1 LLM из ADR-002:
текст методики → DSL-черновик в YAML.

Workflow:

1. Пользователь даёт фрагмент текста методики (ГОСТ/МИ/ТУ).
2. LLM получает: текст + system-промпт с инструкцией + json-schema
   нашего DSL + few-shot примеры.
3. LLM возвращает structured-output по pydantic-модели DslDraft.
4. Дамп DslDraft в YAML, валидация по flv_dsl.schema.json через
   YamlDslAdapter.validate(). При ошибке — retry (до 2 попыток)
   с приклеиванием сообщения об ошибке к промпту.
5. Если валидация прошла — DSL ВОЗВРАЩАЕТСЯ как черновик. Дальше
   обязателен этап human-in-the-loop утверждения (вне FLV: инженер
   просматривает YAML и коммитит).

В Phase 4 реализуется минимально достаточная версия. Тонкая
оптимизация промптов и подбор few-shot — Phase 5 (бенчмарк
точности извлечения по 5 моделям OpenRouter).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .core import LlmProvider
from .dsl import YamlDslAdapter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Pydantic-модели для structured output LLM
# ──────────────────────────────────────────────────────────────────────


class StateDraft(BaseModel):
    name: str = Field(..., description="Имя состояния (UPPER_SNAKE_CASE)")
    required: bool = True
    description: str = ""


class TransitionDraft(BaseModel):
    id: str = ""
    from_: str = Field(..., alias="from")
    to: str
    guard: str | None = None
    time_min_s: float | None = None
    time_max_s: float | None = None
    description: str = ""

    class Config:
        populate_by_name = True


class CheckDraft(BaseModel):
    id: str = ""
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ViolationDraft(BaseModel):
    code: str
    severity: str = "critical"
    message: str = ""
    related_check: str | None = None


class DslDraft(BaseModel):
    """Контракт structured output из LLM (Роль 1)."""

    process_name: str = Field(..., description="Имя процесса (snake_case)")
    description: str = ""
    states: list[StateDraft]
    initial_state: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    transitions: list[TransitionDraft]
    checks: list[CheckDraft] = Field(default_factory=list)
    violations: list[ViolationDraft] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
# System-промпт
# ──────────────────────────────────────────────────────────────────────


_SYSTEM_PROMPT = """\
Ты — инженер-метролог, задача которого — формализовать методику
измерений из текстового описания (ГОСТ / МИ / ТУ / методички ВУЗа)
в виде формальной модели измерительного процесса.

Формализм: расширенный конечный автомат с временными ограничениями
(Timed FSM) + предикаты + каталог нарушений. Структурно — наш DSL
из 02_Спецификация/dsl_v1.yaml. Ты должен вернуть structured-output
по схеме DslDraft.

Принципы:

1. Имена состояний — UPPER_SNAKE_CASE (INIT, HEAT, HOLD, MEASURE, POST).
2. Каждый существенный шаг методики — отдельное состояние.
3. Условие перехода (guard) — булево выражение в синтаксисе Python:
   abs(dT_dt) <= 0.02, T >= T_min, N >= N_min.
4. Временные ограничения (time_min_s / time_max_s) ставятся на
   переходе из соответствующего состояния, в секундах.
5. parameters: каждый числовой параметр процесса (T_set, T_min,
   t_hold_min, N_min, ...) — отдельная запись с полями type, unit,
   min, max, default.
6. checks обязательны для:
   - kind=sequence — must_include = список обязательных состояний.
   - kind=timing — state, min_duration, max_duration.
   - kind=predicate — when, condition.
   - kind=range — variable, min, max.
7. violations: для каждого критичного отклонения от методики —
   отдельный код (UPPER_SNAKE_CASE), severity ('critical' /
   'warning' / 'info'), сообщение, привязка к related_check.
8. НЕ выдумывай численных параметров, не указанных в тексте: если
   значения в методике нет — используй разумный default (например,
   τ=60c для лабораторной термокамеры) И отметь это в description.
9. Все имена параметров и сообщения — на русском или транслите,
   согласовано с DSL Phase 2.
"""


@dataclass
class LlmExtractor:
    """Роль 1 LLM: текст методики → DslDraft → YAML.

    Использование:
        provider = OpenRouterProvider()
        extractor = LlmExtractor(provider=provider, model="anthropic/claude-sonnet-4.6")
        yaml_path = extractor.extract(
            text=Path("methodology.txt").read_text(),
            output_path=Path("spec.yaml"),
        )
    """

    provider: LlmProvider
    model: str | None = None
    system_prompt: str = _SYSTEM_PROMPT
    max_retries: int = 2
    dsl_validator: YamlDslAdapter = field(default_factory=YamlDslAdapter)

    # ──────────────────────────────────────────────────────────────────

    def extract(
        self,
        text: str,
        *,
        output_path: Path | str | None = None,
    ) -> Path | str:
        """Извлечь DSL из текста; сохранить в YAML, если задан
        output_path. Возвращает путь либо YAML-строку.
        """
        draft = self._call_llm(text, error_context="")
        yaml_text = self._draft_to_yaml(draft)

        # Валидация + retry при ошибке
        errors = self._validate_yaml_in_memory(yaml_text)
        attempt = 0
        while errors and attempt < self.max_retries:
            attempt += 1
            logger.info("Валидация не прошла; retry %d/%d", attempt, self.max_retries)
            error_ctx = "\n".join(errors)
            draft = self._call_llm(
                text,
                error_context=(
                    f"Прошлая попытка не прошла валидацию по Schema:\n"
                    f"{error_ctx}\n\nИсправь и попробуй ещё раз."
                ),
            )
            yaml_text = self._draft_to_yaml(draft)
            errors = self._validate_yaml_in_memory(yaml_text)

        if errors:
            raise RuntimeError(
                "LLM не смог извлечь валидный DSL за "
                f"{self.max_retries + 1} попыток. Ошибки:\n  - "
                + "\n  - ".join(errors)
            )

        if output_path is not None:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(yaml_text, encoding="utf-8")
            return p
        return yaml_text

    # ──────────────────────────────────────────────────────────────────

    def _call_llm(self, text: str, *, error_context: str) -> DslDraft:
        prompt_parts = [
            "Текст методики:",
            "<<<METHODOLOGY",
            text.strip(),
            "METHODOLOGY",
        ]
        if error_context:
            prompt_parts.extend(["", error_context])
        prompt_parts.extend([
            "",
            "Верни structured-output по схеме DslDraft.",
        ])
        prompt = "\n".join(prompt_parts)
        return self.provider.complete(  # type: ignore[no-any-return]
            prompt,
            model=self.model,
            response_model=DslDraft,
            system=self.system_prompt,
            temperature=0.0,
        )

    @staticmethod
    def _draft_to_yaml(draft: DslDraft) -> str:
        """Перевод pydantic-модели DslDraft в YAML-формат нашего DSL.

        Структурно собирается так, чтобы пройти flv_dsl.schema.json:
        meta / process / parameters / states / transitions / checks /
        violations_catalog.
        """
        violations: dict[str, Any] = {}
        for v in draft.violations:
            entry: dict[str, Any] = {
                "severity": v.severity,
                "message": v.message,
            }
            if v.related_check:
                entry["related_check"] = v.related_check
            violations[v.code] = entry

        transitions: list[dict[str, Any]] = []
        for t in draft.transitions:
            entry = {
                "id": t.id or f"{t.from_}_to_{t.to}",
                "from": t.from_,
                "to": t.to,
            }
            if t.guard:
                entry["guard"] = t.guard
            if t.time_min_s is not None or t.time_max_s is not None:
                t_obj: dict[str, Any] = {}
                if t.time_min_s is not None:
                    t_obj["min"] = t.time_min_s
                if t.time_max_s is not None:
                    t_obj["max"] = t.time_max_s
                entry["time"] = t_obj
            if t.description:
                entry["description"] = t.description
            transitions.append(entry)

        checks: list[dict[str, Any]] = []
        for c in draft.checks:
            entry = {"kind": c.kind}
            if c.id:
                entry["id"] = c.id
            entry.update(c.payload)
            checks.append(entry)

        spec_dict: dict[str, Any] = {
            "$schema": "./flv_dsl.schema.json",
            "meta": {
                "id": f"llm_extract_{draft.process_name}",
                "version": 1.0,
                "unit_system": "SI",
            },
            "process": {
                "name": draft.process_name,
                "description": draft.description,
            },
            "parameters": dict(draft.parameters),
            "states": [
                {"name": s.name, "required": s.required, "description": s.description}
                for s in draft.states
            ],
            "initial_state": draft.initial_state,
            "transitions": transitions,
            "checks": checks,
            "violations_catalog": violations,
        }
        return yaml.safe_dump(
            spec_dict,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    def _validate_yaml_in_memory(self, yaml_text: str) -> list[str]:
        """Сохранить во временный файл, валидировать YamlDslAdapter."""
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", encoding="utf-8", delete=False
        ) as f:
            f.write(yaml_text)
            tmp = Path(f.name)
        try:
            return self.dsl_validator.validate(tmp)
        finally:
            tmp.unlink(missing_ok=True)


__all__ = [
    "DslDraft", "StateDraft", "TransitionDraft", "CheckDraft", "ViolationDraft",
    "LlmExtractor",
]
