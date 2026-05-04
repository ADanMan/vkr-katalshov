"""
flv.llm_explainer — Роль 3 LLM из ADR-002:
verdict + контекст → human-readable объяснение со ссылками на
пункты нормативки.

Принципы:

1. LLM получает строго ограниченный контекст: verdict.to_dict(),
   фрагмент event-log с релевантными событиями, выдержки DSL.
2. Промпт явно требует процитировать конкретные числа и коды из
   входных данных и НЕ изобретать новых.
3. Вывод проходит через `flv.anti_hallucination.check`. Если
   обнаружены подозрительные числа/идентификаторы — fallback на
   детерминированный шаблон-генератор (без LLM).

Это закрывает требование ADR-002: LLM в Роли 3 — справочное
дополнение, не источник истины. Истина — в детерминированном
verdict от matcher'ов.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from . import anti_hallucination as ah
from .core import LlmProvider, Spec, Trace
from .verdict import Verdict, VerdictStatus

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
Ты — инженер-метролог, который объясняет результат проверки
программной модели измерительного процесса методом FLV
(функционально-логической верификации).

Тебе дан:
- verdict (JSON) — формальный результат от детерминированного
  матчера: статус (OK / OK_WITH_WARNINGS / FAIL) и список
  обнаруженных нарушений с их кодами, ожидаемыми и фактическими
  значениями;
- фрагмент DSL — нормативная модель методики;
- релевантный фрагмент журнала событий прогона.

Твоя задача — изложить результат для человека (метролога,
руководителя ВКР, ревизора) в Markdown:

1. Сжатое резюме одной фразой: статус + главное нарушение.
2. По каждому нарушению — пункт списка с:
   - кодом (`SEQ_MISS`, `TIME_UNDER`, ...);
   - человеко-читаемым описанием на русском;
   - конкретными цифрами из verdict.expected / verdict.actual;
   - ссылкой на пункт нормативного документа, если задан
     (norm_ref) или известно из контекста.
3. Краткая рекомендация (повторить прогон / скорректировать код /
   эскалировать).

КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ:

* Все числа в твоём ответе ОБЯЗАНЫ быть из входных данных
  (verdict / event-log / DSL). Не округляй заметно (не более 0.5%).
* Не изобретай кодов нарушений или идентификаторов состояний,
  которых нет в DSL/verdict.
* Не пиши, что нарушений больше или меньше, чем в verdict.
* Не делай прогнозов и предположений — только опиши факт.
"""


@dataclass
class LlmExplainer:
    """Роль 3 LLM: verdict → human-readable объяснение."""

    provider: LlmProvider
    model: str | None = None
    system_prompt: str = _SYSTEM_PROMPT
    max_event_context: int = 30
    fallback_on_hallucination: bool = True

    # ──────────────────────────────────────────────────────────────────

    def explain(
        self,
        verdict: Verdict,
        *,
        spec: Spec | None = None,
        trace: Trace | None = None,
    ) -> str:
        """Сгенерировать Markdown-объяснение к вердикту.

        Если LLM-вывод не проходит anti-hallucination проверку —
        возвращается детерминированный fallback-шаблон.
        """
        context_blocks = self._build_context(verdict, spec=spec, trace=trace)
        prompt = self._format_prompt(context_blocks)

        try:
            raw_text = self.provider.complete(
                prompt,
                model=self.model,
                system=self.system_prompt,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning("LLM-explainer недоступен (%s); fallback.", exc)
            return self._fallback_template(verdict)

        # Проверка на галлюцинации
        sources = [verdict.to_dict()]
        if spec is not None:
            sources.append(spec.parameters)
            sources.extend([t.id for t in spec.transitions])
            sources.extend(spec.states)
        if trace is not None:
            for ev in trace.events[: self.max_event_context]:
                sources.append({**ev.params, **ev.signals})

        result = ah.check(raw_text if isinstance(raw_text, str) else str(raw_text),
                          known_sources=sources)
        if result.has_hallucination:
            logger.warning(
                "LLM-explainer: обнаружены потенциальные галлюцинации "
                "(numbers=%s, ids=%s); fallback.",
                result.suspicious_numbers, result.suspicious_ids,
            )
            if self.fallback_on_hallucination:
                return self._fallback_template(verdict)
            return result.sanitized
        return result.sanitized

    # ──────────────────────────────────────────────────────────────────

    def _build_context(
        self,
        verdict: Verdict,
        *,
        spec: Spec | None,
        trace: Trace | None,
    ) -> dict[str, Any]:
        ctx: dict[str, Any] = {"verdict": verdict.to_dict()}
        if spec is not None:
            ctx["spec_excerpt"] = {
                "id": spec.id,
                "process": spec.process_name,
                "states": list(spec.states),
                "parameters": dict(spec.parameters),
                "transitions": [
                    {
                        "id": t.id,
                        "from": t.from_state,
                        "to": t.to_state,
                        "guard": t.guard,
                        "time": {
                            "min": t.time_min_s,
                            "max": t.time_max_s,
                        }
                        if (t.time_min_s is not None or t.time_max_s is not None)
                        else None,
                    }
                    for t in spec.transitions
                ],
                "violations_catalog": {
                    code: {
                        "severity": v.severity,
                        "message": v.message,
                        "related_check": v.related_check,
                    }
                    for code, v in spec.violations_catalog.items()
                },
            }
        if trace is not None:
            # Включаем релевантные события: те, на которые ссылаются
            # location'ы нарушений + RUN_START + RUN_END.
            seq_set: set[int] = set()
            for v in verdict.violations:
                if v.location is not None:
                    seq_set.add(v.location.event_seq)
            relevant: list[dict[str, Any]] = []
            for ev in trace.events:
                if (
                    ev.name in {"RUN_START", "RUN_END"}
                    or ev.seq in seq_set
                    or len(relevant) < 5
                ):
                    relevant.append(
                        {
                            "seq": ev.seq,
                            "t_rel_s": ev.t_rel_s,
                            "state": ev.state,
                            "event": ev.name,
                            "params": dict(ev.params),
                            "signals": dict(ev.signals),
                        }
                    )
                if len(relevant) >= self.max_event_context:
                    break
            ctx["trace_excerpt"] = relevant
        return ctx

    @staticmethod
    def _format_prompt(ctx: Mapping[str, Any]) -> str:
        import json

        return (
            "Контекст:\n```json\n"
            + json.dumps(ctx, ensure_ascii=False, indent=2)
            + "\n```\n\nСгенерируй объяснение в Markdown."
        )

    @staticmethod
    def _fallback_template(verdict: Verdict) -> str:
        """Детерминированное объяснение на случай, если LLM
        недоступен или дал галлюцинацию."""
        if verdict.status is VerdictStatus.OK:
            return (
                "Прогон полностью соответствует нормативной модели методики; "
                "нарушений не обнаружено.\n"
            )
        lines: list[str] = []
        if verdict.status is VerdictStatus.FAIL:
            lines.append(
                f"Прогон признан несоответствующим методике: "
                f"обнаружено {verdict.critical_count} критичных нарушений."
            )
        else:
            lines.append(
                f"Прогон принят с предупреждениями: {verdict.warning_count} "
                f"warning'ов."
            )
        for v in verdict.violations:
            lines.append(
                f"- `{v.code}` ({v.severity.value}, {v.matcher}): "
                f"ожидалось {dict(v.expected)}, фактически {dict(v.actual)}."
            )
        lines.append("")
        lines.append(
            "_Объяснение сформировано по детерминированному шаблону "
            "(LLM Роль 3 не задействована или отбракована анти-галл фильтром)._"
        )
        return "\n".join(lines)


__all__ = ["LlmExplainer"]
