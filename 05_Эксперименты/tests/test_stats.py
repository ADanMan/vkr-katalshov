"""Юниты stats.py — known-answer тесты статистических процедур."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from experiments.analyze import analyze, write_xlsx
from experiments.stats import (
    bootstrap_ci,
    build_report,
    cohen_d,
    cohen_d_label,
    mcnemar_test,
    paired_continuous_test,
)


@pytest.mark.unit
def test_cohen_d_standard_case() -> None:
    """Cohen's d для нормальной разницы со standard deviation = 1, mean = 0.8."""
    rng = np.random.default_rng(0)
    arr = rng.normal(0.8, 1.0, 1000)
    d = cohen_d(arr)
    assert 0.7 < d < 0.9
    assert cohen_d_label(d) in {"medium", "large"}


@pytest.mark.unit
def test_cohen_d_label_thresholds() -> None:
    assert cohen_d_label(0.0) == "negligible"
    assert cohen_d_label(0.3) == "small"
    assert cohen_d_label(0.6) == "medium"
    assert cohen_d_label(1.5) == "large"


@pytest.mark.unit
def test_paired_continuous_test_normal() -> None:
    rng = np.random.default_rng(1)
    arr = rng.normal(0.5, 1.0, 200)  # smещение есть, нормальное распределение
    norm, loc = paired_continuous_test(arr, "test")
    # Shapiro на 200 точках с нормальным шумом не должен отвергнуть нормальность.
    assert norm.pvalue > 0.01
    # Сдвиг 0.5 c std=1 — t-test должен поймать.
    assert loc.significant
    assert "Paired t-test" in loc.name


@pytest.mark.unit
def test_paired_continuous_test_skewed_uses_wilcoxon() -> None:
    rng = np.random.default_rng(2)
    arr = rng.exponential(1.0, 100) - 1.0  # сильно скошенное
    norm, loc = paired_continuous_test(arr, "skew")
    if norm.significant:
        assert "Wilcoxon" in loc.name


@pytest.mark.unit
def test_bootstrap_ci_around_mean() -> None:
    rng = np.random.default_rng(3)
    arr = rng.normal(5.0, 1.0, 500)
    point, lo, hi = bootstrap_ci(arr, statistic=np.mean, n_resamples=2000)
    assert lo < point < hi
    assert abs(point - 5.0) < 0.15
    # 95% CI на mean ≈ 5 ± 1.96/sqrt(500) ≈ ±0.088
    assert (hi - lo) < 0.30


@pytest.mark.unit
def test_mcnemar_significant_when_one_sided() -> None:
    # FLV ловит 50 сверх baseline'а — должен быть значим.
    table = pd.DataFrame(
        {"FLV detected": [10, 50], "FLV not detected": [0, 30]},
        index=["Baseline detected", "Baseline not detected"],
    )
    res = mcnemar_test(table)
    assert res.significant
    assert res.pvalue < 0.05


@pytest.mark.unit
def test_mcnemar_not_significant_when_balanced() -> None:
    table = pd.DataFrame(
        {"FLV detected": [10, 5], "FLV not detected": [4, 30]},
        index=["Baseline detected", "Baseline not detected"],
    )
    res = mcnemar_test(table)
    assert not res.significant


@pytest.mark.integration
def test_build_report_synthetic(
    synthetic_metadata: Path, synthetic_runs: Path,
) -> None:
    sheets = analyze(synthetic_metadata, runs_dir=synthetic_runs, deep=True)
    report = build_report(
        raw=sheets["raw"],
        paired=sheets["paired_outcomes"],
        summary=sheets["summary"],
    )
    # Структурные проверки: разделы 1-5 присутствуют, McNemar строка есть,
    # таблицы не пустые.
    assert "## 1. Сводка по подходам" in report
    assert "## 2. McNemar test" in report
    assert "## 3. Производительность" in report
    assert "## 4. J_timing" in report
    assert "## 5. Δbias" in report
    assert "Cohen's d" in report
    assert "значимо" in report
    # Длина — должна получиться внятный отчёт, не пара строк.
    assert len(report) > 1500
