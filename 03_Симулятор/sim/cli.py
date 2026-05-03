"""
sim.cli — CLI-обёртка симулятора.

Команды:
    sim run --scenario scenarios/s1_correct.yaml --output run.jsonl --seed 42
    sim run --scenario scenarios/s1_time_under.yaml --batch 50 --seed-base 1000 \
            --output-dir ../05_Эксперименты/runs/
    sim list-injections
    sim list-scenarios scenarios/

Все прогоны детерминированы при фиксированном seed.

Используется как entry-point из pyproject.toml: sim = sim.cli:main.
"""

from __future__ import annotations

import csv
import logging
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.table import Table

from . import config as cfg
from .event_logger import EventLogger
from .injector import INJECTIONS, get_injection
from .scenario_runner import RunSummary, ScenarioParams, ScenarioRunner

logger = logging.getLogger(__name__)
console = Console()


# ----------------------------------------------------------------------
# Загрузка YAML-сценария
# ----------------------------------------------------------------------


def load_scenario(path: Path) -> dict[str, Any]:
    """Прочитать YAML-сценарий и вернуть его как dict."""
    with open(path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    if "id" not in data or "inject" not in data:
        raise click.UsageError(f"Сценарий {path}: отсутствуют поля id/inject")
    return data


def make_params(overrides: dict[str, Any] | None) -> ScenarioParams:
    """Создать ScenarioParams, применив overrides из YAML."""
    params = ScenarioParams()
    for key, value in (overrides or {}).items():
        if not hasattr(params, key):
            raise click.UsageError(f"Неизвестный override параметр: {key}")
        setattr(params, key, value)
    return params


def build_run_id(stand_id: str, idx: int = 0) -> str:
    """Сгенерировать run_id формата <STAND>-<YYYYMMDD>-<NNN>."""
    today = date.today().strftime("%Y%m%d")
    return f"{stand_id}-{today}-{idx:03d}"


# ----------------------------------------------------------------------
# CLI группа
# ----------------------------------------------------------------------


@click.group(help="Симулятор стенда S1 — термокамера со стабилизацией PT100.")
@click.option(
    "-v", "--verbose", count=True, help="Уровень логирования: -v INFO, -vv DEBUG."
)
def cli(verbose: int) -> None:
    level = logging.WARNING - 10 * min(verbose, 2)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


# ----------------------------------------------------------------------
# sim run
# ----------------------------------------------------------------------


@cli.command(help="Прогнать один или несколько сценариев и записать event-log.")
@click.option(
    "--scenario",
    "scenario_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Путь к YAML-сценарию (scenarios/s1_*.yaml).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Путь к выходному .jsonl (для одиночного прогона).",
)
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Каталог для batch-режима (создаётся, если не существует).",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    show_default=True,
    help="Seed для одиночного прогона.",
)
@click.option(
    "--batch",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="Количество прогонов (для статистики).",
)
@click.option(
    "--seed-base",
    type=int,
    default=1000,
    show_default=True,
    help="Базовый seed для batch (i-й прогон → seed_base + i).",
)
@click.option(
    "--metadata",
    "metadata_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="CSV-файл с метаданными прогонов (создаётся/дописывается).",
)
def run(
    scenario_path: Path,
    output_path: Path | None,
    output_dir: Path | None,
    seed: int,
    batch: int,
    seed_base: int,
    metadata_path: Path | None,
) -> None:
    """Прогнать сценарий N раз и записать event-log в JSONL."""
    scenario = load_scenario(scenario_path)
    inject_code = scenario["inject"]["code"]
    spec = get_injection(inject_code)
    params = make_params(scenario.get("overrides"))

    if batch == 1:
        if output_path is None:
            raise click.UsageError("--output обязателен для batch=1.")
        outputs = [(0, seed, output_path)]
    else:
        if output_dir is None:
            raise click.UsageError("--output-dir обязателен для batch>1.")
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            (i, seed_base + i, output_dir / f"{scenario['id']}-{i:03d}.jsonl")
            for i in range(batch)
        ]

    summaries: list[RunSummary] = []
    for idx, run_seed, out_file in outputs:
        run_id = build_run_id(cfg.STAND_ID, idx)
        hooks = spec.build_hooks(params)
        with EventLogger.open(out_file, run_id=run_id) as eventlog:
            runner = ScenarioRunner(
                run_id=run_id,
                params=params,
                hooks=hooks,
                seed=run_seed,
                sink=eventlog.write,
            )
            summary = runner.run()
        summaries.append(summary)
        console.log(
            f"[green]✓[/green] {scenario['id']} seed={run_seed} "
            f"→ {out_file.name}: end_state={summary.end_state}, "
            f"n_meas={summary.n_measurements}, "
            f"mean_T={summary.mean_T_C if summary.mean_T_C is not None else '—'}"
        )

    # Сводная таблица
    table = Table(title=f"Прогоны сценария {scenario['id']}")
    table.add_column("idx", justify="right")
    table.add_column("seed", justify="right")
    table.add_column("end_state")
    table.add_column("n_meas", justify="right")
    table.add_column("mean_T, °C", justify="right")
    table.add_column("t_total, c", justify="right")
    table.add_column("output", overflow="fold")
    for (idx, run_seed, out_file), summ in zip(outputs, summaries, strict=True):
        table.add_row(
            str(idx),
            str(run_seed),
            summ.end_state,
            str(summ.n_measurements),
            f"{summ.mean_T_C:.3f}" if summ.mean_T_C is not None else "—",
            f"{summ.t_total_s:.1f}",
            str(out_file),
        )
    console.print(table)

    # Метаданные прогонов
    if metadata_path is not None:
        write_metadata_csv(
            metadata_path,
            scenario_id=scenario["id"],
            inject_code=inject_code,
            expected_violation=scenario.get("expected_violation", ""),
            outputs=outputs,
            summaries=summaries,
        )
        console.log(f"[blue]meta:[/blue] {metadata_path}")


def write_metadata_csv(
    path: Path,
    *,
    scenario_id: str,
    inject_code: str,
    expected_violation: str,
    outputs: list[tuple[int, int, Path]],
    summaries: list[RunSummary],
) -> None:
    """Аппенд CSV с метаданными прогонов."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(
                [
                    "ts_iso", "scenario_id", "inject_code", "expected_violation",
                    "run_idx", "seed", "run_id", "end_state",
                    "n_measurements", "mean_T_C", "t_total_s", "output_path",
                ]
            )
        ts = datetime.now(timezone.utc).isoformat()
        for (idx, run_seed, out_file), summ in zip(outputs, summaries, strict=True):
            writer.writerow(
                [
                    ts, scenario_id, inject_code, expected_violation,
                    idx, run_seed, summ.run_id, summ.end_state,
                    summ.n_measurements,
                    f"{summ.mean_T_C:.6f}" if summ.mean_T_C is not None else "",
                    f"{summ.t_total_s:.3f}",
                    str(out_file),
                ]
            )


# ----------------------------------------------------------------------
# sim list-injections
# ----------------------------------------------------------------------


@cli.command("list-injections", help="Показать все доступные коды нарушений.")
def list_injections_cmd() -> None:
    table = Table(title="Доступные инъекции (sim.injector.INJECTIONS)")
    table.add_column("Code")
    table.add_column("Description")
    table.add_column("Expected violation")
    for code, spec in INJECTIONS.items():
        table.add_row(spec.code, spec.description, spec.expected_violation)
    console.print(table)


# ----------------------------------------------------------------------
# sim list-scenarios
# ----------------------------------------------------------------------


@cli.command("list-scenarios", help="Перечислить YAML-сценарии в каталоге.")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
def list_scenarios_cmd(directory: Path) -> None:
    files = sorted(directory.glob("*.yaml"))
    if not files:
        click.echo(f"В {directory} нет .yaml-сценариев.")
        return
    table = Table(title=f"Сценарии в {directory}")
    table.add_column("File")
    table.add_column("ID")
    table.add_column("Inject")
    table.add_column("Description", overflow="fold")
    for path in files:
        try:
            data = load_scenario(path)
            table.add_row(
                path.name,
                data.get("id", ""),
                str(data.get("inject", {}).get("code", "")),
                data.get("description", ""),
            )
        except Exception as e:  # pragma: no cover
            table.add_row(path.name, "[red]ERROR[/red]", "", str(e))
    console.print(table)


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------


def main() -> int:
    try:
        cli(standalone_mode=False)
        return 0
    except click.exceptions.UsageError as e:
        click.echo(f"Usage error: {e.format_message()}", err=True)
        return 2
    except click.exceptions.Abort:
        return 130


if __name__ == "__main__":
    sys.exit(main())
