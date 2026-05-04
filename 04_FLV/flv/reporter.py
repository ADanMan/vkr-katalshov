"""
flv.reporter — генератор отчётов о вердикте.

Поддерживает два формата:

* JSON — машинно-читаемый, для интеграции с пайплайнами Phase 5
  (статистика прогонов, confusion matrix).
* Markdown — для человеческого чтения и встраивания в архив прогонов
  как «FLV-сертификат соответствия». Структура — по
  `02_Спецификация/violations_catalog.md` §4.

Reporter не зависит от LLM-объяснителя — `LlmExplainer` (Phase 4.8)
обрабатывает Verdict отдельно и вкладывает свой текст в Markdown
через ключ `explanation` (опционально).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .verdict import Verdict, VerdictStatus


@dataclass
class ReportArtifacts:
    """Что сохранено по итогам генерации."""

    json_path: Path | None = None
    markdown_path: Path | None = None


def render_json(verdict: Verdict, *, indent: int = 2) -> str:
    """Собрать машинно-читаемое JSON-представление вердикта."""
    return json.dumps(verdict.to_dict(), ensure_ascii=False, indent=indent)


_STATUS_BADGE = {
    VerdictStatus.OK: "✅ OK",
    VerdictStatus.OK_WITH_WARNINGS: "⚠️ OK_WITH_WARNINGS",
    VerdictStatus.FAIL: "❌ FAIL",
}


def render_markdown(
    verdict: Verdict,
    *,
    explanation: str | None = None,
    title: str | None = None,
) -> str:
    """Собрать Markdown-отчёт о вердикте.

    Параметры
    ---------
    verdict : результат FLV-проверки.
    explanation : дополнительный текст от LLM-explainer (Phase 4.8).
        Включается под отдельным заголовком, если задан.
    title : переопределить заголовок отчёта.
    """
    out = StringIO()
    out.write(f"# {title or 'FLV-сертификат соответствия'}\n\n")
    out.write(f"**Run ID:** `{verdict.run_id}`  \n")
    out.write(f"**Spec ID:** `{verdict.spec_id}`  \n")
    out.write(f"**Verdict:** {_STATUS_BADGE.get(verdict.status, verdict.status.value)}  \n")
    out.write(f"**Critical:** {verdict.critical_count}  \n")
    out.write(f"**Warnings:** {verdict.warning_count}  \n")
    out.write("\n")

    if not verdict.violations:
        out.write("Нарушений не обнаружено. Прогон соответствует "
                  "нормативной модели методики.\n\n")
    else:
        out.write("## Обнаруженные нарушения\n\n")
        out.write("| # | Код | Severity | Matcher | State | Expected | Actual | Location |\n")
        out.write("|---|---|---|---|---|---|---|---|\n")
        for i, v in enumerate(verdict.violations, start=1):
            loc = (
                f"seq={v.location.event_seq}, t={v.location.ts_rel_s:.2f}c"
                if v.location is not None
                else "—"
            )
            out.write(
                f"| {i} | `{v.code}` | {v.severity.value} | {v.matcher} | "
                f"{v.state or '—'} | {_compact(v.expected)} | "
                f"{_compact(v.actual)} | {loc} |\n"
            )
        out.write("\n")

        # Подробности по каждому нарушению
        out.write("## Детализация\n\n")
        for i, v in enumerate(verdict.violations, start=1):
            out.write(f"### {i}. `{v.code}` — {v.message or v.code}\n\n")
            out.write(f"- Matcher: `{v.matcher}`\n")
            if v.state:
                out.write(f"- Состояние FSM: `{v.state}`\n")
            if v.spec_ref:
                out.write(f"- DSL-привязка: `{v.spec_ref}`\n")
            if v.norm_ref:
                out.write(f"- Нормативка: {v.norm_ref}\n")
            if v.expected:
                out.write(f"- Ожидалось: `{_compact(v.expected)}`\n")
            if v.actual:
                out.write(f"- Фактически: `{_compact(v.actual)}`\n")
            if v.location is not None:
                out.write(
                    f"- Событие: seq=`{v.location.event_seq}`, "
                    f"t={v.location.ts_rel_s:.3f} c\n"
                )
            out.write("\n")

    # Сводка
    if verdict.summary:
        out.write("## Сводка\n\n")
        for k, val in verdict.summary.items():
            out.write(f"- **{k}:** `{val}`\n")
        out.write("\n")

    if explanation:
        out.write("## Объяснение (LLM)\n\n")
        out.write(explanation.rstrip())
        out.write("\n\n")
        out.write(
            "> _Это объяснение сгенерировано LLM (Роль 3 по ADR-002) и "
            "является справочным дополнением к формальному вердикту._\n"
        )

    return out.getvalue()


def write_reports(
    verdict: Verdict,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
    explanation: str | None = None,
) -> ReportArtifacts:
    """Сохранить JSON и/или Markdown отчёт по запросу."""
    artifacts = ReportArtifacts()
    if json_path is not None:
        p = Path(json_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_json(verdict), encoding="utf-8")
        artifacts.json_path = p
    if markdown_path is not None:
        p = Path(markdown_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_markdown(verdict, explanation=explanation), encoding="utf-8")
        artifacts.markdown_path = p
    return artifacts


def _compact(d: Any) -> str:
    """Компактный JSON-репр для одной ячейки таблицы."""
    if not d:
        return "—"
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))


__all__ = [
    "ReportArtifacts",
    "render_json",
    "render_markdown",
    "write_reports",
]
