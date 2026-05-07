"""Юниты analyze.py — детекция, paired таблица, continuous-метрики."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from experiments.analyze import (
    DetectionMetrics,
    _augment_with_detection,
    _compute_continuous,
    _compute_detection,
    _compute_overhead,
    _compute_paired_outcomes,
    analyze,
)


@pytest.mark.unit
def test_detection_metrics_basic() -> None:
    m = DetectionMetrics(approach="x", tp=8, fp=1, tn=10, fn=2)
    assert m.n == 21
    assert abs(m.tpr - 8 / 10) < 1e-9
    assert abs(m.tnr - 10 / 11) < 1e-9
    assert abs(m.fpr - 1 / 11) < 1e-9
    assert abs(m.f1 - (2 * (8/9) * (8/10) / ((8/9) + (8/10)))) < 1e-9


@pytest.mark.unit
def test_augment_with_detection_columns(synthetic_metadata: Path) -> None:
    df = pd.read_csv(synthetic_metadata)
    df = _augment_with_detection(df)
    assert {"violation_expected", "baseline_detected", "flv_detected", "overhead_ratio"} <= set(df.columns)
    # s1_correct → expected=False
    correct = df[df["scenario_id"] == "s1_correct"]
    assert (~correct["violation_expected"]).all()
    # s1_time_under → expected=True
    under = df[df["scenario_id"] == "s1_time_under"]
    assert under["violation_expected"].all()


@pytest.mark.unit
def test_compute_detection_paired(synthetic_metadata: Path) -> None:
    df = _augment_with_detection(pd.read_csv(synthetic_metadata))
    base = _compute_detection(df, detected_col="baseline_detected", approach="baseline")
    flv = _compute_detection(df, detected_col="flv_detected", approach="flv")
    # FLV должен иметь TPR ≥ baseline по конструкции synthetic данных.
    assert flv.tpr >= base.tpr
    # Конкретно: FLV ловит все 70 (7 «инъекционных» сценариев × 10), baseline только 20.
    assert flv.tp == 70
    assert base.tp == 20
    # FPR одинаковые (никто не ложно-пожарит на correct).
    assert base.fpr == pytest.approx(0.0)
    assert flv.fpr == pytest.approx(0.0)


@pytest.mark.unit
def test_paired_outcomes_dimensions(synthetic_metadata: Path) -> None:
    df = _augment_with_detection(pd.read_csv(synthetic_metadata))
    paired = _compute_paired_outcomes(df)
    assert paired.shape == (2, 2)
    # FLV-only ячейка должна быть положительной.
    flv_only = paired.iloc[1, 0]
    assert flv_only > 0


@pytest.mark.unit
def test_overhead_positive(synthetic_metadata: Path) -> None:
    df = _augment_with_detection(pd.read_csv(synthetic_metadata))
    o = _compute_overhead(df)
    assert o["mean"] > 1.0  # FLV дороже baseline'а в synthetic-данных.


@pytest.mark.integration
def test_analyze_pipeline_synthetic(
    synthetic_metadata: Path, synthetic_runs: Path,
) -> None:
    sheets = analyze(synthetic_metadata, runs_dir=synthetic_runs, deep=True)
    assert set(sheets.keys()) >= {"raw", "summary", "by_scenario", "paired_outcomes", "meta"}
    raw = sheets["raw"]
    assert "T_meas_mean_C" in raw.columns
    # T_meas_mean должен быть около T_set = 150 для большинства прогонов.
    correct_temps = raw[~raw["violation_expected"]]["T_meas_mean_C"].dropna()
    assert (correct_temps - 150.0).abs().mean() < 0.5

    cont = _compute_continuous(raw)
    # J_timing > 0 — есть инъекции с t_hold ≠ 300.
    assert cont["J_timing"]["mean"] > 0
