"""
experiments.run_all — оркестратор экспериментальных батч-прогонов
Phase 5.

Принцип работы:

1. Для каждого сценария из 8 (s1_correct + 7 инъекций) запускается
   `--batch` прогонов с разными seed'ами.
2. Каждый прогон даёт один JSONL-файл event-log в `runs/`.
3. На каждом event-log прогоняются baseline-проверка
   (`experiments.baseline.check_log`) и FLV-модуль (через CLI или
   in-process). Замеряется wall-time каждого подхода (overhead).
4. Сводка по всем прогонам пишется в `runs/_metadata.csv`:
   run_id, scenario, expected_violation, seed, baseline_passed,
   baseline_time_s, flv_status, flv_violations, flv_time_s.

Дальше скрипт `analyze.py` читает _metadata.csv и считает метрики.
"""

from __future__ import annotations

import csv
import logging
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.progress import Progress

logger = logging.getLogger(__name__)
console = Console()


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


@dataclass
class RunRecord:
    """Метаданные одного прогона эксперимента."""

    run_id: str
    scenario_id: str
    expected_violation: str
    seed: int
    log_path: Path
    baseline_passed: bool = True
    baseline_codes: tuple[str, ...] = ()
    baseline_time_s: float = 0.0
    flv_status: str = ""
    flv_violations: tuple[str, ...] = ()
    flv_time_s: float = 0.0

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "expected_violation": self.expected_violation,
            "seed": self.seed,
            "log_path": str(self.log_path),
            "baseline_passed": int(self.baseline_passed),
            "baseline_codes": ";".join(self.baseline_codes),
            "baseline_time_s": f"{self.baseline_time_s:.6f}",
            "flv_status": self.flv_status,
            "flv_violations": ";".join(self.flv_violations),
            "flv_time_s": f"{self.flv_time_s:.6f}",
        }


def _ensure_paths_for_local_imports(repo_root: Path) -> None:
    """Добавляем в sys.path локальные пакеты sim/ и flv/, чтобы
    модули можно было импортировать без `pip install -e`."""
    for sub in ("03_Симулятор", "04_FLV"):
        p = repo_root / sub
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def _read_scenarios(scenarios_dir: Path) -> list[Path]:
    return sorted(scenarios_dir.glob("s1_*.yaml"))


def _scenario_meta(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ──────────────────────────────────────────────────────────────────────
# Запуск симулятора и матчеров
# ──────────────────────────────────────────────────────────────────────


def run_simulator(
    scenario_path: Path,
    *,
    seed: int,
    output_path: Path,
    sim_cli: str = "sim",
) -> None:
    """Запустить sim run --scenario X --output Y --seed N."""
    cmd = [
        sim_cli, "run",
        "--scenario", str(scenario_path),
        "--output", str(output_path),
        "--seed", str(seed),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def run_baseline(log_path: Path) -> tuple[bool, tuple[str, ...], float]:
    """In-process baseline-проверка."""
    from experiments.baseline import check_log

    t0 = time.perf_counter()
    verdict = check_log(log_path)
    elapsed = time.perf_counter() - t0
    return verdict.passed, tuple(f.code for f in verdict.findings), elapsed


def run_flv(
    spec_path: Path,
    log_path: Path,
) -> tuple[str, tuple[str, ...], float]:
    """In-process прогон FLV-модуля поверх spec и log."""
    from flv.adapters import JsonlAdapter
    from flv.dsl import YamlDslAdapter
    from flv.matchers import PredicateMatcher, SequenceMatcher, TimingMatcher
    from flv.verdict import aggregate

    t0 = time.perf_counter()
    spec = YamlDslAdapter().load(spec_path)
    trace = JsonlAdapter().load(log_path)
    matchers = [SequenceMatcher(), TimingMatcher(), PredicateMatcher()]
    violations: list = []
    for m in matchers:
        violations.extend(m.match(spec, trace))
    verdict = aggregate(violations, run_id=trace.run_id, spec_id=spec.id)
    elapsed = time.perf_counter() - t0
    codes = tuple(v.code for v in verdict.violations)
    return verdict.status.value, codes, elapsed


# ──────────────────────────────────────────────────────────────────────
# Главный pipeline
# ──────────────────────────────────────────────────────────────────────


def run_batch(
    *,
    scenarios: Iterable[Path],
    spec_path: Path,
    batch: int,
    seed_base: int,
    output_dir: Path,
    sim_cli: str,
) -> list[RunRecord]:
    """Прогнать все сценарии × batch прогонов; сохранить event-log'и
    в `output_dir`, прогнать через baseline и FLV, собрать
    `RunRecord` на каждый прогон.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[RunRecord] = []
    scenarios = list(scenarios)
    total = len(scenarios) * batch

    with Progress() as progress:
        task = progress.add_task("[cyan]прогоны[/cyan]", total=total)

        for sc_path in scenarios:
            sc_meta = _scenario_meta(sc_path)
            sc_id = sc_meta.get("id", sc_path.stem)
            expected = sc_meta.get("expected_violation", "(none)")

            for i in range(batch):
                seed = seed_base + i
                log_path = output_dir / f"{sc_id}-{i:03d}.jsonl"
                run_simulator(sc_path, seed=seed, output_path=log_path, sim_cli=sim_cli)

                bl_passed, bl_codes, bl_time = run_baseline(log_path)
                flv_status, flv_codes, flv_time = run_flv(spec_path, log_path)

                record = RunRecord(
                    run_id=f"{sc_id}-{i:03d}",
                    scenario_id=sc_id,
                    expected_violation=expected,
                    seed=seed,
                    log_path=log_path,
                    baseline_passed=bl_passed,
                    baseline_codes=bl_codes,
                    baseline_time_s=bl_time,
                    flv_status=flv_status,
                    flv_violations=flv_codes,
                    flv_time_s=flv_time,
                )
                records.append(record)
                progress.advance(task)

    return records


def write_metadata(records: list[RunRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].to_csv_row().keys()) if records else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_csv_row())


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


@click.command(help="Прогнать пакетный эксперимент: симулятор × baseline × FLV.")
@click.option(
    "--scenarios-dir", "scenarios_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("../03_Симулятор/scenarios"), show_default=True,
)
@click.option(
    "--spec", "spec_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("../02_Спецификация/dsl_v1.yaml"), show_default=True,
)
@click.option(
    "--output-dir", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("runs"), show_default=True,
)
@click.option("--batch", type=click.IntRange(min=1), default=50, show_default=True)
@click.option("--seed-base", type=int, default=1000, show_default=True)
@click.option(
    "--scenarios", "scenarios_filter", default="all", show_default=True,
    help="'all' или comma-separated список scenario id (s1_correct,s1_time_under,...)",
)
@click.option("--sim-cli", default="sim", show_default=True, help="Путь к sim CLI")
def main(
    scenarios_dir: Path,
    spec_path: Path,
    output_dir: Path,
    batch: int,
    seed_base: int,
    scenarios_filter: str,
    sim_cli: str,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    repo_root = Path(__file__).resolve().parents[2]
    _ensure_paths_for_local_imports(repo_root)

    all_scenarios = _read_scenarios(scenarios_dir)
    if scenarios_filter != "all":
        wanted = {s.strip() for s in scenarios_filter.split(",")}
        all_scenarios = [
            p for p in all_scenarios if _scenario_meta(p).get("id", p.stem) in wanted
        ]

    if not all_scenarios:
        console.print("[red]Не найдено ни одного сценария.[/red]")
        sys.exit(2)

    console.print(
        f"[bold]Сценариев:[/bold] {len(all_scenarios)}, "
        f"прогонов на сценарий: {batch}, всего: {len(all_scenarios) * batch}"
    )

    records = run_batch(
        scenarios=all_scenarios,
        spec_path=spec_path,
        batch=batch,
        seed_base=seed_base,
        output_dir=output_dir,
        sim_cli=sim_cli,
    )

    metadata_path = output_dir / "_metadata.csv"
    write_metadata(records, metadata_path)
    console.print(f"[green]✓[/green] Метаданные: {metadata_path}")
    console.print(f"[green]✓[/green] Логи: {output_dir} (всего {len(records)} файлов)")


if __name__ == "__main__":
    main()
