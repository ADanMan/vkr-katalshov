"""Общие фикстуры pytest для тестов модуля FLV."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_flv_on_path() -> None:
    """Гарантирует, что пакет flv/ доступен при запуске pytest без
    предварительной установки `pip install -e`."""
    pkg_root = Path(__file__).resolve().parent.parent
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))


@pytest.fixture()
def sample_dsl_yaml(tmp_path: Path) -> Path:
    """Маленький, но валидный DSL для S1-подобного процесса."""
    p = tmp_path / "spec.yaml"
    p.write_text(
        """
meta:
  id: test-s1
  version: 1.0
  unit_system: SI

process:
  name: temperature_measurement_test
  description: Минимальный тестовый сценарий

parameters:
  T_min:
    type: float
    unit: "°C"
    default: 50
  T_set_max:
    type: float
    unit: "°C"
    default: 250
  delta_stable:
    type: float
    default: 0.02

states:
  - name: INIT
    required: true
  - name: HEAT
    required: true
  - name: HOLD
    required: true
  - name: MEASURE
    required: true
  - name: POST
    required: true

transitions:
  - id: t1
    from: INIT
    to: HEAT
    guard: "device_ready == True"
  - id: t2
    from: HEAT
    to: HOLD
    guard: "T >= T_min"
  - id: t3
    from: HOLD
    to: MEASURE
    guard: "abs(dT_dt) <= delta_stable"
    time:
      min: 300
      max: 600
  - id: t4
    from: MEASURE
    to: POST
    guard: "N >= 20"

checks:
  - id: c1
    kind: sequence
    must_include: [INIT, HEAT, HOLD, MEASURE, POST]
  - id: c2
    kind: timing
    state: HOLD
    min_duration: 300
    max_duration: 600
  - id: c3
    kind: predicate
    when: "state == POST"
    condition: "N_collected >= 20"
  - id: c4
    kind: range
    variable: T_set
    min: 30
    max: T_set_max

violations_catalog:
  SEQ_MISS:
    severity: critical
    message: "Пропущен обязательный шаг"
    related_check: c1
  SEQ_ORDER:
    severity: critical
    message: "Нарушен порядок переходов"
  TIME_UNDER:
    severity: critical
    message: "Недостаточная длительность"
    related_check: c2
  TIME_OVER:
    severity: warning
    message: "Превышение длительности"
    related_check: c2
  PRED_FAIL:
    severity: critical
    message: "Не выполнен предикат стабилизации"
    related_check: c3
  N_TOO_LOW:
    severity: critical
    message: "Недостаточно отсчётов"
    related_check: c3
  RANGE_MISM:
    severity: critical
    message: "Параметр вне диапазона"
    related_check: c4
""",
        encoding="utf-8",
    )
    return p


def _write_jsonl(path: Path, events: list[dict]) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return path


@pytest.fixture()
def correct_run_jsonl(tmp_path: Path) -> Path:
    """Эталонный прогон без нарушений."""
    return _write_jsonl(
        tmp_path / "correct.jsonl",
        [
            {"ts": "2026-05-04T10:00:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 0, "state": "INIT",
             "event": "RUN_START",
             "params": {"_ts_rel_s": 0.0, "T_set": 150}, "signals": {"T": 24.0}},
            {"ts": "2026-05-04T10:00:00.500Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 1, "state": "INIT",
             "event": "INIT_END",
             "params": {"_ts_rel_s": 0.5, "device_ready": True}, "signals": {}},
            {"ts": "2026-05-04T10:00:00.500Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 2, "state": "HEAT",
             "event": "HEAT_START", "params": {"_ts_rel_s": 0.5}, "signals": {}},
            {"ts": "2026-05-04T10:02:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 3, "state": "HEAT",
             "event": "HEAT_END",
             "params": {"_ts_rel_s": 120.0}, "signals": {"T": 50.5}},
            {"ts": "2026-05-04T10:02:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 4, "state": "HOLD",
             "event": "HOLD_START", "params": {"_ts_rel_s": 120.0}, "signals": {}},
            {"ts": "2026-05-04T10:07:30.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 5, "state": "HOLD",
             "event": "HOLD_END",
             "params": {"_ts_rel_s": 450.0, "t_hold": 330, "dT_dt": 0.01},
             "signals": {"T": 150.0}},
            {"ts": "2026-05-04T10:07:30.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 6, "state": "MEASURE",
             "event": "MEAS_START", "params": {"_ts_rel_s": 450.0}, "signals": {}},
            {"ts": "2026-05-04T10:07:50.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 7, "state": "MEASURE",
             "event": "MEAS_END",
             "params": {"_ts_rel_s": 470.0, "N_collected": 25}, "signals": {}},
            {"ts": "2026-05-04T10:07:50.000Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 8, "state": "POST",
             "event": "POST_END",
             "params": {"_ts_rel_s": 470.0, "N_collected": 25}, "signals": {}},
            {"ts": "2026-05-04T10:07:50.500Z", "stand_id": "S1",
             "run_id": "S1-T-001", "seq": 9, "state": "POST",
             "event": "RUN_END",
             "params": {"_ts_rel_s": 470.5, "run_status": "completed"},
             "signals": {}},
        ],
    )


@pytest.fixture()
def time_under_jsonl(tmp_path: Path) -> Path:
    """Прогон с инъекцией TIME_UNDER (HOLD = 30 c вместо ≥ 300)."""
    return _write_jsonl(
        tmp_path / "time_under.jsonl",
        [
            {"ts": "2026-05-04T10:00:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 0, "state": "INIT",
             "event": "RUN_START",
             "params": {"_ts_rel_s": 0.0, "T_set": 150}, "signals": {"T": 24.0}},
            {"ts": "2026-05-04T10:00:00.500Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 1, "state": "INIT",
             "event": "INIT_END",
             "params": {"_ts_rel_s": 0.5, "device_ready": True}, "signals": {}},
            {"ts": "2026-05-04T10:00:00.500Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 2, "state": "HEAT",
             "event": "HEAT_START", "params": {"_ts_rel_s": 0.5}, "signals": {}},
            {"ts": "2026-05-04T10:02:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 3, "state": "HEAT",
             "event": "HEAT_END",
             "params": {"_ts_rel_s": 120.0}, "signals": {"T": 50.5}},
            {"ts": "2026-05-04T10:02:00.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 4, "state": "HOLD",
             "event": "HOLD_START", "params": {"_ts_rel_s": 120.0}, "signals": {}},
            {"ts": "2026-05-04T10:02:30.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 5, "state": "HOLD",
             "event": "HOLD_END",
             "params": {"_ts_rel_s": 150.0, "t_hold": 30, "dT_dt": 0.045},
             "signals": {"T": 80.0}},
            {"ts": "2026-05-04T10:02:30.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 6, "state": "MEASURE",
             "event": "MEAS_START", "params": {"_ts_rel_s": 150.0}, "signals": {}},
            {"ts": "2026-05-04T10:02:50.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 7, "state": "MEASURE",
             "event": "MEAS_END",
             "params": {"_ts_rel_s": 170.0, "N_collected": 25}, "signals": {}},
            {"ts": "2026-05-04T10:02:50.000Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 8, "state": "POST",
             "event": "POST_END",
             "params": {"_ts_rel_s": 170.0, "N_collected": 25}, "signals": {}},
            {"ts": "2026-05-04T10:02:50.500Z", "stand_id": "S1",
             "run_id": "S1-T-002", "seq": 9, "state": "POST",
             "event": "RUN_END",
             "params": {"_ts_rel_s": 170.5, "run_status": "completed"},
             "signals": {}},
        ],
    )
