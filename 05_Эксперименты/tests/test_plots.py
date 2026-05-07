"""Smoke-тесты plots.py — фигуры сохраняются, файлы непустые."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

from experiments.analyze import analyze, write_xlsx  # noqa: E402
from experiments.plots import (  # noqa: E402
    plot_boxplot_overhead,
    plot_confusion_paired,
    plot_delta_bias,
    plot_j_timing,
    plot_metrics_bar,
    plot_roc,
    plot_timeline_example,
)


@pytest.fixture
def results_xlsx(tmp_path: Path, synthetic_metadata: Path, synthetic_runs: Path) -> tuple[Path, dict]:
    sheets = analyze(synthetic_metadata, runs_dir=synthetic_runs, deep=True)
    out = tmp_path / "results.xlsx"
    write_xlsx(sheets, out)
    return out, sheets


@pytest.mark.integration
def test_plots_smoke(results_xlsx: tuple[Path, dict], tmp_path: Path) -> None:
    _, sheets = results_xlsx
    out_dir = tmp_path / "figures"
    raw = sheets["raw"]
    summary = sheets["summary"]
    runs_dir = Path(raw["log_path"].iloc[0]).parent

    plot_confusion_paired(summary, out_dir)
    plot_metrics_bar(summary, out_dir)
    plot_timeline_example(raw, runs_dir, out_dir)
    plot_boxplot_overhead(raw, out_dir)
    plot_roc(raw, out_dir)
    plot_j_timing(raw, out_dir)
    plot_delta_bias(raw, out_dir)

    expected = [
        "confusion_matrix_paired.png", "metrics_bar.png", "timeline_example.png",
        "boxplot_overhead.png", "roc_curve.png", "j_timing_distribution.png",
        "delta_bias_scatter.png",
    ]
    for name in expected:
        f = out_dir / name
        assert f.exists(), f"Не сохранилась фигура: {name}"
        assert f.stat().st_size > 0
