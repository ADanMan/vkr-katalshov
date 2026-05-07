"""Общие фикстуры тестов Phase 5."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_metadata(tmp_path: Path) -> Path:
    """Генерим _metadata.csv-подобный файл из 8×10 = 80 фейковых прогонов.

    Поведение:
    * s1_correct (10 прогонов) — оба подхода NOT_DETECTED (TN).
    * s1_time_under, s1_time_over (по 10) — baseline пропускает (FN), FLV ловит (TP).
    * Остальные 5 сценариев — оба ловят.
    Это даёт McNemar-значимый сдвиг в пользу FLV.
    """
    rng = np.random.default_rng(42)
    rows: list[dict[str, object]] = []
    for sc, expected, baseline_fail, flv_fail in [
        ("s1_correct", "(none)", False, False),
        ("s1_time_under", "TIME_UNDER", False, True),
        ("s1_time_over", "TIME_OVER", False, True),
        ("s1_few_samples", "FEW_SAMPLES", True, True),
        ("s1_t_set_bad", "T_SET_BAD", True, True),
        ("s1_pred_fail", "PRED_FAIL", False, True),
        ("s1_seq_miss", "SEQ_MISS", False, True),
        ("s1_range_mism", "RANGE_MISM", False, True),
    ]:
        for i in range(10):
            rows.append({
                "run_id": f"{sc}-{i:03d}",
                "scenario_id": sc,
                "expected_violation": expected,
                "seed": 1000 + i,
                "log_path": str(tmp_path / "runs" / f"{sc}-{i:03d}.jsonl"),
                "baseline_passed": int(not baseline_fail),
                "baseline_codes": "" if not baseline_fail else "FEW_SAMPLES;HOLD_TOO_SHORT",
                "baseline_time_s": round(rng.uniform(0.001, 0.003), 6),
                "flv_status": "PASS" if not flv_fail else "FAIL",
                "flv_violations": "" if not flv_fail else f"FLV_{expected};SEQ_OK",
                "flv_time_s": round(rng.uniform(0.005, 0.012), 6),
            })
    df = pd.DataFrame(rows)
    csv_path = tmp_path / "_metadata.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def synthetic_runs(tmp_path: Path, synthetic_metadata: Path) -> Path:
    """Генерим минимальные event-log'и для каждого прогона из synthetic_metadata.

    Каждый log содержит: RUN_START (T_set=150), HEAT_END, HOLD_END (t_hold≈300),
    MEAS_START, 30 точек MEAS_PROBE с T в окрестности T_set, MEAS_END.
    Это даёт osmysленные T_meas_mean и t_hold для аналитики.
    """
    df = pd.read_csv(synthetic_metadata)
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    T_set = 150.0
    for _, row in df.iterrows():
        log_path = Path(row["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Перенацеливаем log_path в реальный runs_dir.
        log_path = runs_dir / log_path.name
        events: list[dict[str, object]] = []
        seq = 0

        def _emit(event: str, state: str, t: float, params: dict | None = None,
                  signals: dict | None = None) -> None:
            nonlocal seq
            entry: dict[str, object] = {
                "ts": "2026-05-05T12:00:00.000",
                "stand_id": "S1",
                "run_id": row["run_id"],
                "seq": seq,
                "state": state,
                "event": event,
                "params": (params or {}) | {"_ts_rel_s": t},
            }
            if signals:
                entry["signals"] = signals
            if event == "RUN_START":
                entry["meta"] = {"log_format_version": "1.0", "simulator_version": "test"}
            events.append(entry)
            seq += 1

        # Привнести инъекцию: TIME_UNDER → t_hold = 100; TIME_OVER → 700.
        is_under = row["scenario_id"] == "s1_time_under"
        is_over = row["scenario_id"] == "s1_time_over"
        is_few = row["scenario_id"] == "s1_few_samples"
        is_tset_bad = row["scenario_id"] == "s1_t_set_bad"
        T_set_use = 350.0 if is_tset_bad else T_set
        t_hold = 100.0 if is_under else (700.0 if is_over else 320.0)
        n_meas = 5 if is_few else 30

        _emit("RUN_START", "INIT", 0.0,
              params={"T_set": T_set_use, "t_hold_min": 300, "N_min": 20},
              signals={"T": 22.0})
        _emit("HEAT_START", "HEAT", 5.0, signals={"T": 22.5})
        _emit("HEAT_END", "HEAT", 60.0, params={"T_reached": T_set_use},
              signals={"T": T_set_use})
        _emit("HOLD_END", "HOLD", 60.0 + t_hold,
              params={"t_hold": t_hold}, signals={"T": T_set_use})
        _emit("MEAS_START", "MEASURE", 60.0 + t_hold + 1.0, signals={"T": T_set_use})
        for k in range(n_meas):
            t_k = 60.0 + t_hold + 1.0 + (k + 1) * 0.5
            T_k = T_set_use + rng.normal(0, 0.05)
            _emit("MEAS_PROBE", "MEASURE", t_k, signals={"T": T_k})
        _emit("MEAS_END", "MEASURE", 60.0 + t_hold + 1.0 + (n_meas + 1) * 0.5,
              params={"N_collected": n_meas}, signals={"T": T_set_use})
        _emit("RUN_END", "POST", 60.0 + t_hold + (n_meas + 2) * 0.5,
              signals={"T": T_set_use})

        with open(log_path, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Обновляем log_path в csv на новые абсолютные пути.
    df["log_path"] = df["log_path"].apply(lambda p: str(runs_dir / Path(p).name))
    df.to_csv(synthetic_metadata, index=False)
    return runs_dir
