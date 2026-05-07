"""
experiments.stats — статистическая обработка результатов Phase 5.

Отчёт пишется по протоколу ГОСТ 8.207-76 (обработка результатов
прямых измерений с многократными наблюдениями) + рекомендации GUM
(JCGM 100:2008) для непрерывных метрик качества.

Что считается:

* **McNemar test** (paired binary) — сравнение частоты детекции
  baseline vs FLV. Используем 2×2 таблицу из ``paired_outcomes``;
  при дискордантных < 25 — exact binomial, иначе χ²-аппроксимация
  (см. statsmodels.stats.contingency_tables.mcnemar).

* **Shapiro-Wilk normality** на парных разностях для непрерывных
  метрик (например, ``flv_time_s − baseline_time_s``). Если
  p-value > α — paired t-test; иначе — Wilcoxon signed-rank.

* **Cohen's d** (эффект-сайз) для всех непрерывных метрик. Интерпретация:
  |d| ≥ 0.2 — small, ≥ 0.5 — medium, ≥ 0.8 — large.

* **Bootstrap 95% CI** (n_resamples=10 000, percentile method) на
  все парные метрики. Используем ``scipy.stats.bootstrap``.

* α = 0.05 (двусторонний тест по умолчанию).

Выход — Markdown-отчёт ``stat_report.md`` с таблицами и краткой
интерпретацией каждого блока.

CLI:

    exp-stats --results results.xlsx --out stat_report.md
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import click
import numpy as np
import pandas as pd
from rich.console import Console
from scipy import stats as scipy_stats
from statsmodels.stats.contingency_tables import mcnemar

logger = logging.getLogger(__name__)
console = Console()

ALPHA = 0.05
N_BOOT = 10_000
RANDOM_STATE = 42


# ──────────────────────────────────────────────────────────────────────
# Низкоуровневые статистические тесты
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TestResult:
    """Универсальный результат одного статтеста."""

    name: str
    statistic: float
    pvalue: float
    significant: bool
    meta: str = ""

    def to_md_row(self) -> list[str]:
        sig = "**значимо**" if self.significant else "не значимо"
        return [
            self.name,
            f"{self.statistic:.4g}",
            f"{self.pvalue:.4g}",
            sig + (f" — {self.meta}" if self.meta else ""),
        ]


def mcnemar_test(paired_table: pd.DataFrame) -> TestResult:
    """McNemar test над 2×2 paired таблицей.

    Ожидается: rows = baseline (detected/not), cols = FLV (detected/not).
    """
    table = paired_table.values.astype(int)
    # Дискордантные ячейки — b (baseline only) и c (FLV only).
    discord = table[0, 1] + table[1, 0]
    exact = discord < 25
    res = mcnemar(table, exact=exact, correction=True)
    return TestResult(
        name=f"McNemar ({'exact' if exact else 'χ²'})",
        statistic=float(res.statistic),
        pvalue=float(res.pvalue),
        significant=res.pvalue < ALPHA,
        meta=f"discordants={discord}",
    )


def paired_continuous_test(
    paired: Sequence[float] | np.ndarray,
    name: str,
) -> tuple[TestResult, TestResult]:
    """Shapiro-Wilk → t-test или Wilcoxon на парных разностях.

    Возвращает (normality_test, location_test).
    """
    arr = np.asarray(paired, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 3:
        msg = f"Недостаточно данных для {name} (n={len(arr)})"
        return (
            TestResult("Shapiro-Wilk", float("nan"), float("nan"), False, msg),
            TestResult("(skipped)", float("nan"), float("nan"), False, msg),
        )

    sh_stat, sh_p = scipy_stats.shapiro(arr)
    normality = TestResult(
        name="Shapiro-Wilk",
        statistic=float(sh_stat),
        pvalue=float(sh_p),
        significant=sh_p < ALPHA,
        meta="нормальность отвергнута" if sh_p < ALPHA else "нормальность не отвергнута",
    )

    if sh_p >= ALPHA:
        # Парный t-test: H0 — среднее разностей = 0.
        t_stat, t_p = scipy_stats.ttest_1samp(arr, popmean=0.0)
        location = TestResult(
            name=f"Paired t-test ({name})",
            statistic=float(t_stat),
            pvalue=float(t_p),
            significant=t_p < ALPHA,
            meta=f"n={len(arr)}, mean={arr.mean():.4g}, std={arr.std(ddof=1):.4g}",
        )
    else:
        # Wilcoxon signed-rank.
        try:
            w_stat, w_p = scipy_stats.wilcoxon(arr, zero_method="wilcox")
            location = TestResult(
                name=f"Wilcoxon signed-rank ({name})",
                statistic=float(w_stat),
                pvalue=float(w_p),
                significant=w_p < ALPHA,
                meta=f"n={len(arr)}, median={np.median(arr):.4g}",
            )
        except ValueError as e:
            location = TestResult(
                name=f"Wilcoxon ({name})",
                statistic=float("nan"),
                pvalue=float("nan"),
                significant=False,
                meta=f"skipped: {e}",
            )
    return normality, location


def cohen_d(paired: Sequence[float] | np.ndarray) -> float:
    """Cohen's d на парных разностях: mean(d) / std(d)."""
    arr = np.asarray(paired, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return float("nan")
    sd = arr.std(ddof=1)
    return float(arr.mean() / sd) if sd > 0 else float("nan")


def cohen_d_label(d: float) -> str:
    if np.isnan(d):
        return "—"
    a = abs(d)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    return "large"


def bootstrap_ci(
    paired: Sequence[float] | np.ndarray,
    *,
    statistic: callable = np.mean,  # type: ignore[type-arg]
    confidence: float = 0.95,
    n_resamples: int = N_BOOT,
) -> tuple[float, float, float]:
    """Bootstrap percentile CI вокруг точечной оценки statistic(arr).

    Возвращает (point, lo, hi).
    """
    arr = np.asarray(paired, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 2:
        return (float("nan"), float("nan"), float("nan"))
    point = float(statistic(arr))
    res = scipy_stats.bootstrap(
        (arr,),
        statistic,
        confidence_level=confidence,
        n_resamples=n_resamples,
        method="percentile",
        random_state=RANDOM_STATE,
        vectorized=False,
    )
    return point, float(res.confidence_interval.low), float(res.confidence_interval.high)


# ──────────────────────────────────────────────────────────────────────
# Главный pipeline
# ──────────────────────────────────────────────────────────────────────


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Простой Markdown-pipe table."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def build_report(
    raw: pd.DataFrame,
    paired: pd.DataFrame,
    summary: pd.DataFrame,
) -> str:
    """Собрать Markdown-отчёт."""
    lines: list[str] = []
    lines.append("# Phase 5 — статистический отчёт\n")
    lines.append(
        f"**Дата сборки:** {datetime.now().isoformat(timespec='seconds')}\n",
    )
    lines.append(f"**α = {ALPHA}** (двусторонний тест), bootstrap n_resamples = {N_BOOT}.\n")
    lines.append(
        "**Контекст.** Phase 5 ВКР Катальшова Д.А. (К2-81Б, 12.03.01 «Информационно-измерительная "
        "техника и технологии», МФ МГТУ Бауман). Парное сравнение наивного baseline'а "
        "и метода функционально-логической верификации (FLV).\n",
    )

    # ── 1. Сводка детекций ────────────────────────────────────────
    lines.append("## 1. Сводка по подходам\n")
    lines.append(_md_table(
        list(summary.columns),
        summary.astype(str).values.tolist(),
    ))
    lines.append("")

    # ── 2. McNemar ────────────────────────────────────────────────
    lines.append("## 2. McNemar test — сравнение частоты детекции\n")
    lines.append("Парная 2×2 таблица:")
    lines.append("")
    lines.append(_md_table(
        [""] + list(paired.columns),
        [[idx] + [str(v) for v in row] for idx, row in zip(paired.index, paired.values, strict=True)],
    ))
    lines.append("")
    mcnemar_res = mcnemar_test(paired)
    lines.append(_md_table(
        ["Тест", "Статистика", "p-value", "Вывод"],
        [mcnemar_res.to_md_row()],
    ))
    if mcnemar_res.significant:
        lines.append(
            "\n> Различие в частоте детекции **статистически значимо** на уровне α = 0.05. "
            "FLV и baseline отличаются по способности находить инъекции нарушений.",
        )
    else:
        lines.append(
            "\n> Различие в частоте детекции не значимо на уровне α = 0.05.",
        )
    lines.append("")

    # ── 3. Overhead ───────────────────────────────────────────────
    lines.append("## 3. Производительность — overhead t_FLV / t_baseline\n")
    overhead = raw["overhead_ratio"].dropna().values
    if len(overhead) >= 2:
        norm, loc = paired_continuous_test(overhead - 1.0, "overhead − 1")
        d = cohen_d(overhead - 1.0)
        point, lo, hi = bootstrap_ci(overhead, statistic=np.mean)
        lines.append(_md_table(
            ["Метрика", "Mean", "Std", "Median", "95% CI bootstrap"],
            [[
                "t_FLV / t_baseline",
                f"{overhead.mean():.3f}",
                f"{overhead.std(ddof=1):.3f}",
                f"{np.median(overhead):.3f}",
                f"[{lo:.3f}; {hi:.3f}]",
            ]],
        ))
        lines.append("")
        lines.append(_md_table(
            ["Тест", "Статистика", "p-value", "Вывод"],
            [norm.to_md_row(), loc.to_md_row()],
        ))
        lines.append(
            f"\n**Cohen's d** = {d:.3f} ({cohen_d_label(d)}) — на парных разностях "
            "overhead − 1.",
        )
    else:
        lines.append("Недостаточно данных для статистики overhead.")
    lines.append("")

    # ── 4. J_timing (длительность HOLD) ───────────────────────────
    lines.append("## 4. J_timing — отклонения длительности HOLD\n")
    sub = raw.dropna(subset=["t_hold_s"])
    if not sub.empty:
        rel_err = (sub["t_hold_s"] - 300.0).abs() / 300.0
        norm, loc = paired_continuous_test(rel_err.values, "|t_hold − 300| / 300")
        d = cohen_d(rel_err.values)
        point, lo, hi = bootstrap_ci(rel_err.values, statistic=np.mean)
        lines.append(_md_table(
            ["Метрика", "n", "Mean rel.err", "Median", "95% CI mean"],
            [[
                "J_timing",
                str(len(rel_err)),
                f"{rel_err.mean():.4g}",
                f"{np.median(rel_err):.4g}",
                f"[{lo:.4g}; {hi:.4g}]",
            ]],
        ))
        lines.append("")
        lines.append(_md_table(
            ["Тест", "Статистика", "p-value", "Вывод"],
            [norm.to_md_row(), loc.to_md_row()],
        ))
        lines.append(
            f"\n**Cohen's d** (rel.err vs 0) = {d:.3f} ({cohen_d_label(d)})",
        )
    else:
        lines.append("Нет прогонов с зафиксированным t_hold.")
    lines.append("")

    # ── 5. Δbias ──────────────────────────────────────────────────
    lines.append("## 5. Δbias — смещение результата при инъекциях\n")
    correct = raw[~raw["violation_expected"]].dropna(subset=["T_meas_mean_C", "T_set_C"])
    inj = raw[raw["violation_expected"]].dropna(subset=["T_meas_mean_C", "T_set_C"])
    delta_correct = (correct["T_meas_mean_C"] - correct["T_set_C"]).abs().values
    delta_inj = (inj["T_meas_mean_C"] - inj["T_set_C"]).abs().values

    if len(delta_correct) >= 2 and len(delta_inj) >= 2:
        norm, loc = paired_continuous_test(
            np.concatenate([delta_inj, -delta_correct]),
            "Δbias (injection − correct)",
        )
        d = (delta_inj.mean() - delta_correct.mean()) / np.sqrt(
            (delta_inj.var(ddof=1) + delta_correct.var(ddof=1)) / 2,
        ) if (delta_inj.var(ddof=1) + delta_correct.var(ddof=1)) > 0 else float("nan")

        # Mann-Whitney как непараметрика для двух независимых выборок.
        mw_stat, mw_p = scipy_stats.mannwhitneyu(
            delta_inj, delta_correct, alternative="two-sided",
        )
        lines.append(_md_table(
            ["Группа", "n", "Mean |ΔT|, °C", "Median, °C"],
            [
                ["Корректные прогоны", str(len(delta_correct)),
                 f"{delta_correct.mean():.4g}", f"{np.median(delta_correct):.4g}"],
                ["С инъекциями", str(len(delta_inj)),
                 f"{delta_inj.mean():.4g}", f"{np.median(delta_inj):.4g}"],
            ],
        ))
        lines.append("")
        mw_res = TestResult(
            name="Mann-Whitney U (independent)",
            statistic=float(mw_stat),
            pvalue=float(mw_p),
            significant=mw_p < ALPHA,
            meta="injection vs correct",
        )
        lines.append(_md_table(
            ["Тест", "Статистика", "p-value", "Вывод"],
            [mw_res.to_md_row()],
        ))
        lines.append(
            f"\n**Cohen's d** (independent groups) = {d:.3f} ({cohen_d_label(d)})",
        )
    else:
        lines.append(
            "Недостаточно данных в одной из групп (correct / injection) для Δbias.",
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Все парные тесты — двусторонние. Сглаживания по Bonferroni для multiple comparisons "
        "не делалось: тесты на разных метриках самостоятельны и относятся к разным гипотезам.*",
    )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


@click.command(help="Статистические тесты на results.xlsx → stat_report.md.")
@click.option(
    "--results", "results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("results.xlsx"), show_default=True,
)
@click.option(
    "--out", "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("stat_report.md"), show_default=True,
)
def main(results_path: Path, out_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raw = pd.read_excel(results_path, sheet_name="raw")
    paired = pd.read_excel(results_path, sheet_name="paired_outcomes", index_col=0)
    summary = pd.read_excel(results_path, sheet_name="summary")
    report = build_report(raw, paired, summary)
    out_path.write_text(report, encoding="utf-8")
    console.print(f"[green]✓[/green] stat_report.md: {out_path}")


if __name__ == "__main__":
    main()
