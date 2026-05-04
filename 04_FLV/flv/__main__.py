"""
flv.__main__ — CLI точка входа модуля FLV.

Команды:

    flv check       — основная проверка: spec + log → verdict
    flv validate    — валидировать DSL без runtime
    flv extract     — LLM-извлечение DSL из текста методики (Роль 1)
    flv plugins     — посмотреть доступные плагины (4 группы)

Все команды поддерживают флаг `--source` / `--dsl` / `--llm` для
выбора нужного плагина (jsonl/yaml/openrouter/mock и др.).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from .plugins import discover, get
from .reporter import render_json, render_markdown, write_reports
from .verdict import aggregate

logger = logging.getLogger(__name__)
console = Console()


@click.group(help="FLV — функционально-логическая верификация измерительных протоколов в составе ИИС.")
@click.option("-v", "--verbose", count=True, help="-v INFO, -vv DEBUG.")
def cli(verbose: int) -> None:
    level = logging.WARNING - 10 * min(verbose, 2)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


# ──────────────────────────────────────────────────────────────────────
# flv check
# ──────────────────────────────────────────────────────────────────────


@cli.command(help="Проверить event-log на соответствие DSL-спецификации.")
@click.option(
    "--spec", "spec_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True,
)
@click.option(
    "--log", "log_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True,
)
@click.option(
    "--report", "md_path",
    type=click.Path(dir_okay=False, path_type=Path), default=None,
    help="Куда сохранить Markdown-отчёт.",
)
@click.option(
    "--json", "json_path",
    type=click.Path(dir_okay=False, path_type=Path), default=None,
    help="Куда сохранить JSON-отчёт.",
)
@click.option("--source", default="jsonl", show_default=True, help="Source-адаптер")
@click.option("--dsl", "dsl_kind", default="yaml", show_default=True, help="DSL-адаптер")
@click.option(
    "--explain/--no-explain", default=False,
    help="Подключить LLM-объяснение verdict'а (Роль 3 ADR-002).",
)
@click.option("--llm", "llm_kind", default="openrouter", show_default=True, help="LLM-провайдер")
@click.option("--model", default=None, help="Имя модели для LLM (если --explain).")
def check(
    spec_path: Path,
    log_path: Path,
    md_path: Path | None,
    json_path: Path | None,
    source: str,
    dsl_kind: str,
    explain: bool,
    llm_kind: str,
    model: str | None,
) -> None:
    """Прогнать matcher pipeline и сохранить отчёты."""
    # Загрузка плагинов через discovery
    DslAdapter = get("dsl_adapter", dsl_kind)
    SourceAdapter = get("source_adapter", source)

    spec = DslAdapter().load(spec_path)
    trace = SourceAdapter().load(log_path)

    # Все matcher'ы из реестра
    plugins = discover()
    matchers = [cls() for cls in plugins["matcher"].values()]

    violations: list[Any] = []
    for matcher in matchers:
        violations.extend(matcher.match(spec, trace))

    verdict = aggregate(
        violations,
        run_id=trace.run_id,
        spec_id=spec.id,
        extra_summary={
            "source_adapter": source,
            "dsl_adapter": dsl_kind,
            "n_matchers": len(matchers),
        },
    )

    explanation: str | None = None
    if explain:
        from .llm_explainer import LlmExplainer

        Provider = get("llm_provider", llm_kind)
        provider = Provider()
        explainer = LlmExplainer(provider=provider, model=model)
        explanation = explainer.explain(verdict, spec=spec, trace=trace)

    # Печать сводки в консоль
    _print_verdict(verdict)

    # Опциональная запись отчётов
    if md_path or json_path:
        artifacts = write_reports(
            verdict,
            json_path=json_path,
            markdown_path=md_path,
            explanation=explanation,
        )
        if artifacts.json_path:
            console.print(f"[blue]JSON:[/blue] {artifacts.json_path}")
        if artifacts.markdown_path:
            console.print(f"[blue]Markdown:[/blue] {artifacts.markdown_path}")

    # Exit-code: 0 при OK / OK_WITH_WARNINGS, 1 при FAIL — для CI
    sys.exit(0 if verdict.status.value != "FAIL" else 1)


def _print_verdict(verdict: Any) -> None:
    badge = {"OK": "[green]✅ OK[/green]",
             "OK_WITH_WARNINGS": "[yellow]⚠️ OK_WITH_WARNINGS[/yellow]",
             "FAIL": "[red]❌ FAIL[/red]"}.get(verdict.status.value, verdict.status.value)
    console.print(f"\n[bold]Verdict:[/bold] {badge}")
    console.print(f"  Run: [cyan]{verdict.run_id}[/cyan] · Spec: [cyan]{verdict.spec_id}[/cyan]")
    console.print(f"  Critical: {verdict.critical_count} · Warnings: {verdict.warning_count}")

    if verdict.violations:
        table = Table(title="Нарушения")
        table.add_column("#", justify="right")
        table.add_column("Code")
        table.add_column("Sev")
        table.add_column("Matcher")
        table.add_column("State")
        table.add_column("Expected", overflow="fold")
        table.add_column("Actual", overflow="fold")
        for i, v in enumerate(verdict.violations, start=1):
            sev_color = {"critical": "red", "warning": "yellow", "info": "white"}.get(
                v.severity.value, "white"
            )
            table.add_row(
                str(i),
                f"[bold]{v.code}[/bold]",
                f"[{sev_color}]{v.severity.value}[/{sev_color}]",
                v.matcher,
                v.state or "—",
                str(dict(v.expected)),
                str(dict(v.actual)),
            )
        console.print(table)


# ──────────────────────────────────────────────────────────────────────
# flv validate
# ──────────────────────────────────────────────────────────────────────


@cli.command(help="Валидировать DSL по JSON-Schema без запуска прогонов.")
@click.option("--spec", "spec_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--dsl", "dsl_kind", default="yaml", show_default=True)
def validate(spec_path: Path, dsl_kind: str) -> None:
    DslAdapter = get("dsl_adapter", dsl_kind)
    errors = DslAdapter().validate(spec_path)
    if not errors:
        console.print(f"[green]✓[/green] {spec_path}: DSL валиден.")
        sys.exit(0)
    console.print(f"[red]✗[/red] {spec_path}: {len(errors)} ошибок:")
    for err in errors:
        console.print(f"  - {err}")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# flv extract — LLM Роль 1
# ──────────────────────────────────────────────────────────────────────


@cli.command(help="LLM-извлечение DSL из текстового описания методики (Роль 1 ADR-002).")
@click.option("--text", "text_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
@click.option("--llm", "llm_kind", default="openrouter", show_default=True)
@click.option("--model", default=None)
def extract(text_path: Path, out_path: Path, llm_kind: str, model: str | None) -> None:
    from .llm_extractor import LlmExtractor

    Provider = get("llm_provider", llm_kind)
    provider = Provider()
    extractor = LlmExtractor(provider=provider, model=model)
    text = text_path.read_text(encoding="utf-8")
    result = extractor.extract(text, output_path=out_path)
    console.print(f"[green]✓[/green] DSL-черновик сохранён: {result}")
    console.print(
        "[yellow]i[/yellow] Это LLM-черновик. Просмотрите его перед коммитом — "
        "human-in-the-loop обязателен (ADR-002, Роль 1)."
    )


# ──────────────────────────────────────────────────────────────────────
# flv plugins
# ──────────────────────────────────────────────────────────────────────


@cli.command(help="Показать все доступные плагины фреймворка (4 группы по ADR-004).")
def plugins() -> None:
    catalog = discover(load=False)
    table = Table(title="FLV plugins (entry-points)")
    table.add_column("Group")
    table.add_column("Name")
    table.add_column("Module")
    for group, items in catalog.items():
        for name, ep in items.items():
            table.add_row(group, name, str(ep))
    console.print(table)


# ──────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        cli(standalone_mode=False)
        return 0
    except click.exceptions.Abort:
        return 130
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 0


if __name__ == "__main__":
    sys.exit(main())
