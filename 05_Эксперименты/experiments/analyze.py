"""
experiments.analyze — расчёт метрик из event-log'ов и _metadata.csv.

Принцип. Phase 5 — paired-эксперимент: один и тот же event-log проверен
двумя подходами (baseline vs FLV). На каждом прогоне есть пара исходов
"detected/not detected" — это устраняет влияние seed'а на сравнение.

Что считается:

* **Бинарная детекция** (paired):
  TP, FP, TN, FN, TPR, TNR, FPR, FNR, accuracy, F1 — отдельно для
  baseline и FLV. Парная 2×2 таблица по 4 ячейкам (b=fail/pass × f=fail/pass)
  для McNemar в Phase 5.5.

* **Непрерывные качественные метрики**:

  - ``J_timing`` — средняя относительная ошибка по критичным временным
    окнам HOLD: ``mean(|t_fact − t_min| / t_min)`` по прогонам, где есть
    HOLD_END.params.t_hold.
  - ``K_seq`` — доля прогонов без нарушений порядка переходов (FLV
    SEQ_MISS / SEQ_ORDER в violations).
  - ``Δbias`` — отклонение результата измерения (средней T в MEASURE)
    от уставки T_set, отдельно для корректных прогонов и с инъекциями.

* **Производительность**:
  - ``overhead = t_FLV / t_baseline`` (mean ± std по прогонам);
  - ``cpu_overhead`` оценкой (через time-stamps);
  - ``mem`` — пока не считается, плэйсхолдер.

Выход: ``results.xlsx`` с листами:

* ``raw`` — расширенный _metadata.csv (детекции + continuous).
* ``by_scenario`` — сводка по scenario_id.
* ``summary`` — общие числа по двум подходам.
* ``paired_outcomes`` — 2×2 таблица для McNemar.
* ``meta`` — параметры запуска (input file, n_runs, дата).

Использование (CLI):

    exp-analyze --runs runs/ --metadata runs/_metadata.csv --out results.xlsx
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import numpy as np
import pandas as pd
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


# ──────────────────────────────────────────────────────────────────────
# Структуры
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DetectionMetrics:
    """Бинарные метрики детекции для одного подхода (baseline или FLV)."""

    approach: str
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def tpr(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else float("nan")

    @property
    def tnr(self) -> float:
        return self.tn / (self.tn + self.fp) if (self.tn + self.fp) else float("nan")

    @property
    def fpr(self) -> float:
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) else float("nan")

    @property
    def fnr(self) -> float:
        return self.fn / (self.fn + self.tp) if (self.fn + self.tp) else float("nan")

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.n if self.n else float("nan")

    @property
    def f1(self) -> float:
        prec = self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0
        rec = self.tpr
        return 2 * prec * rec / (prec + rec) if (prec + rec) else float("nan")

    def to_row(self) -> dict[str, Any]:
        return {
            "approach": self.approach,
            "TP": self.tp, "FP": self.fp, "TN": self.tn, "FN": self.fn,
            "TPR": round(self.tpr, 4),
            "TNR": round(self.tnr, 4),
            "FPR": round(self.fpr, 4),
            "FNR": round(self.fnr, 4),
            "accuracy": round(self.accuracy, 4),
            "F1": round(self.f1, 4),
        }


# ──────────────────────────────────────────────────────────────────────
# Парсинг event-log'ов для continuous metrics
# ──────────────────────────────────────────────────────────────────────


def _iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _extract_timing_and_bias(
    log_path: Path,
) -> dict[str, float | None]:
    """Из одного event-log'а вытащить метрики: t_hold, N_collected, T_set,
    T_meas_mean. Используются для J_timing и Δbias.
    """
    out: dict[str, float | None] = {
        "T_set_C": None,
        "t_hold_s": None,
        "N_collected": None,
        "T_meas_mean_C": None,
    }
    T_meas_samples: list[float] = []
    in_measure = False
    for ev in _iter_jsonl(log_path):
        params = ev.get("params") or {}
        signals = ev.get("signals") or {}
        evt = ev.get("event") or ""

        if evt == "RUN_START" and "T_set" in params:
            out["T_set_C"] = float(params["T_set"])
        if evt == "HOLD_END" and "t_hold" in params:
            out["t_hold_s"] = float(params["t_hold"])
        if evt == "MEAS_START":
            in_measure = True
        if evt == "MEAS_END":
            in_measure = False
            if "N_collected" in params:
                out["N_collected"] = int(params["N_collected"])

        if in_measure and "T" in signals:
            T_meas_samples.append(float(signals["T"]))

    if T_meas_samples:
        out["T_meas_mean_C"] = float(np.mean(T_meas_samples))
    return out


# ──────────────────────────────────────────────────────────────────────
# Расчёт метрик
# ──────────────────────────────────────────────────────────────────────


def _augment_with_detection(df: pd.DataFrame) -> pd.DataFrame:
    """Добавить колонки violation_expected, *_detected."""
    df = df.copy()
    df["violation_expected"] = df["expected_violation"].fillna("(none)").str.lower() != "(none)"
    df["baseline_passed"] = df["baseline_passed"].astype(int).astype(bool)
    df["baseline_detected"] = ~df["baseline_passed"]
    df["flv_detected"] = df["flv_status"].astype(str).str.upper() != "PASS"
    df["overhead_ratio"] = df["flv_time_s"] / df["baseline_time_s"].replace(0, np.nan)
    return df


def _compute_detection(
    df: pd.DataFrame, *, detected_col: str, approach: str,
) -> DetectionMetrics:
    """TP/FP/TN/FN для одного подхода."""
    expected = df["violation_expected"]
    detected = df[detected_col]
    tp = int(((expected) & (detected)).sum())
    fp = int(((~expected) & (detected)).sum())
    tn = int(((~expected) & (~detected)).sum())
    fn = int(((expected) & (~detected)).sum())
    return DetectionMetrics(approach=approach, tp=tp, fp=fp, tn=tn, fn=fn)


def _compute_paired_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Парная 2×2 таблица для McNemar.

    Строки — baseline (detected/not), колонки — FLV. Для каждого прогона
    смотрим, обнаружили ли подходы нарушение в *prone к нарушению*
    прогонах (violation_expected = True). McNemar test проверит, что
    diagonals (TP_b, TP_f) одинаково плотны или нет.
    """
    sub = df[df["violation_expected"]].copy()
    a = int(((sub["baseline_detected"]) & (sub["flv_detected"])).sum())   # both detect
    b = int(((sub["baseline_detected"]) & (~sub["flv_detected"])).sum())  # baseline only
    c = int(((~sub["baseline_detected"]) & (sub["flv_detected"])).sum())  # FLV only
    d = int(((~sub["baseline_detected"]) & (~sub["flv_detected"])).sum())  # both miss
    return pd.DataFrame({
        "FLV detected": [a, c],
        "FLV not detected": [b, d],
    }, index=["Baseline detected", "Baseline not detected"])


def _compute_continuous(
    df: pd.DataFrame, *, t_hold_min_s: float = 300.0,
) -> dict[str, dict[str, float | int]]:
    """Непрерывные метрики: J_timing, K_seq, Δbias."""
    sub = df.dropna(subset=["t_hold_s"]).copy()
    if sub.empty:
        j_timing: float = float("nan")
    else:
        rel_err = np.abs(sub["t_hold_s"] - t_hold_min_s) / t_hold_min_s
        j_timing = float(rel_err.mean())

    seq_mask = df["flv_violations"].astype(str).str.contains("SEQ_", na=False)
    k_seq = float(1.0 - seq_mask.mean()) if len(df) else float("nan")

    # Δbias — берём корректные прогоны как референс, остальные сравниваем.
    correct = df[~df["violation_expected"]].dropna(
        subset=["T_meas_mean_C", "T_set_C"],
    )
    delta_correct = (correct["T_meas_mean_C"] - correct["T_set_C"]).abs()
    bias_correct_mean = float(delta_correct.mean()) if not correct.empty else float("nan")

    inj = df[df["violation_expected"]].dropna(
        subset=["T_meas_mean_C", "T_set_C"],
    )
    delta_inj = (inj["T_meas_mean_C"] - inj["T_set_C"]).abs()
    bias_inj_mean = float(delta_inj.mean()) if not inj.empty else float("nan")

    return {
        "J_timing": {
            "mean": j_timing,
            "n": int(len(sub)),
        },
        "K_seq": {
            "value": k_seq,
            "n_seq_violations": int(seq_mask.sum()),
            "n": int(len(df)),
        },
        "delta_bias": {
            "correct_mean_C": bias_correct_mean,
            "injection_mean_C": bias_inj_mean,
            "delta_C": (bias_inj_mean - bias_correct_mean)
                if not (np.isnan(bias_correct_mean) or np.isnan(bias_inj_mean))
                else float("nan"),
            "n_correct": int(len(correct)),
            "n_injection": int(len(inj)),
        },
    }


def _compute_overhead(df: pd.DataFrame) -> dict[str, float]:
    sub = df.dropna(subset=["overhead_ratio"])
    if sub.empty:
        return {"mean": float("nan"), "std": float("nan"), "median": float("nan")}
    return {
        "mean": float(sub["overhead_ratio"].mean()),
        "std": float(sub["overhead_ratio"].std()),
        "median": float(sub["overhead_ratio"].median()),
        "n": int(len(sub)),
    }


def _by_scenario_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for sc, grp in df.groupby("scenario_id"):
        baseline = _compute_detection(grp, detected_col="baseline_detected", approach="baseline")
        flv = _compute_detection(grp, detected_col="flv_detected", approach="flv")
        rows.append({
            "scenario_id": sc,
            "n_runs": len(grp),
            "violation_expected": str(grp["expected_violation"].iloc[0]),
            "baseline_TPR": round(baseline.tpr, 4),
            "baseline_FPR": round(baseline.fpr, 4),
            "baseline_F1": round(baseline.f1, 4),
            "flv_TPR": round(flv.tpr, 4),
            "flv_FPR": round(flv.fpr, 4),
            "flv_F1": round(flv.f1, 4),
            "baseline_time_s_mean": round(grp["baseline_time_s"].mean(), 6),
            "flv_time_s_mean": round(grp["flv_time_s"].mean(), 6),
            "overhead_ratio_mean": round(grp["overhead_ratio"].mean(), 3),
        })
    return pd.DataFrame(rows).sort_values("scenario_id")


# ──────────────────────────────────────────────────────────────────────
# Главный pipeline
# ──────────────────────────────────────────────────────────────────────


def analyze(
    metadata_path: Path,
    *,
    runs_dir: Path | None = None,
    deep: bool = True,
) -> dict[str, Any]:
    """Прочитать metadata.csv, при ``deep=True`` подтянуть continuous
    метрики из event-log'ов; вернуть словарь pandas.DataFrame.
    """
    df = pd.read_csv(metadata_path)
    df = _augment_with_detection(df)

    if deep:
        rows: list[dict[str, Any]] = []
        for log_path in df["log_path"]:
            p = Path(log_path)
            if not p.is_absolute() and runs_dir is not None:
                p = runs_dir / p.name
            rows.append(_extract_timing_and_bias(p))
        deep_df = pd.DataFrame(rows)
        df = pd.concat([df.reset_index(drop=True), deep_df.reset_index(drop=True)], axis=1)
    else:
        for col in ("T_set_C", "t_hold_s", "N_collected", "T_meas_mean_C"):
            df[col] = np.nan

    baseline = _compute_detection(df, detected_col="baseline_detected", approach="baseline")
    flv = _compute_detection(df, detected_col="flv_detected", approach="flv")

    summary = pd.DataFrame([baseline.to_row(), flv.to_row()])
    by_scenario = _by_scenario_summary(df)
    paired = _compute_paired_outcomes(df)
    continuous = _compute_continuous(df)
    overhead = _compute_overhead(df)

    meta = pd.DataFrame([
        {"key": "n_runs", "value": len(df)},
        {"key": "n_scenarios", "value": int(df["scenario_id"].nunique())},
        {"key": "metadata_path", "value": str(metadata_path)},
        {"key": "runs_dir", "value": str(runs_dir) if runs_dir else ""},
        {"key": "deep_metrics", "value": deep},
        {"key": "analyzed_at", "value": datetime.now().isoformat(timespec="seconds")},
        {"key": "J_timing_mean", "value": continuous["J_timing"]["mean"]},
        {"key": "J_timing_n", "value": continuous["J_timing"]["n"]},
        {"key": "K_seq", "value": continuous["K_seq"]["value"]},
        {"key": "delta_bias_correct_C", "value": continuous["delta_bias"]["correct_mean_C"]},
        {"key": "delta_bias_injection_C", "value": continuous["delta_bias"]["injection_mean_C"]},
        {"key": "overhead_mean", "value": overhead["mean"]},
        {"key": "overhead_std", "value": overhead["std"]},
    ])

    return {
        "raw": df,
        "summary": summary,
        "by_scenario": by_scenario,
        "paired_outcomes": paired,
        "meta": meta,
    }


def write_xlsx(sheets: Mapping[str, pd.DataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=isinstance(df.index, pd.MultiIndex)
                        or name == "paired_outcomes")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


@click.command(help="Расчёт метрик из _metadata.csv и event-log'ов.")
@click.option(
    "--metadata", "metadata_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("runs/_metadata.csv"), show_default=True,
)
@click.option(
    "--runs", "runs_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("runs"), show_default=True,
)
@click.option(
    "--out", "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("results.xlsx"), show_default=True,
)
@click.option(
    "--deep/--no-deep", default=True, show_default=True,
    help="Подтягивать continuous-метрики (J_timing, Δbias) из event-log'ов",
)
def main(
    metadata_path: Path,
    runs_dir: Path,
    out_path: Path,
    deep: bool,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sheets = analyze(metadata_path, runs_dir=runs_dir, deep=deep)
    write_xlsx(sheets, out_path)
    console.print(f"[green]✓[/green] results.xlsx: {out_path}")
    console.print(
        f"  baseline TPR={sheets['summary'].iloc[0]['TPR']:.3f}, "
        f"FLV TPR={sheets['summary'].iloc[1]['TPR']:.3f}",
    )
    console.print(
        f"  paired outcomes (FLV finds, baseline misses): "
        f"{sheets['paired_outcomes'].iloc[1, 0]}",
    )


if __name__ == "__main__":
    main()
