"""Интеграционные тесты ScenarioRunner + Injector + EventLogger."""

from __future__ import annotations

from pathlib import Path

import pytest

from sim.event_logger import EventLogger, load_jsonl
from sim.injector import INJECTIONS, get_injection
from sim.scenario_runner import ScenarioParams, ScenarioRunner


def _short_params() -> ScenarioParams:
    """Сокращённые параметры для быстрого прогона тестов:
    маленький N_min и t_hold чтобы тест прошёл за секунды."""
    return ScenarioParams(
        T_set_C=80.0,           # ниже, чем 150, чтобы быстрее нагрелось
        T_min_C=40.0,
        delta_stable_Cs=2.0,    # очень снисходительный порог стабилизации
        t_hold_min_s=2.0,
        t_hold_max_s=20.0,
        n_min=3,
        f_meas_Hz=2.0,
        f_sample_Hz=2.0,
        timeout_s=120.0,
        sim_step_s=0.1,
    )


@pytest.mark.integration
def test_correct_run_completes_post(tmp_jsonl: Path) -> None:
    """Эталонный прогон должен завершиться состоянием POST и собрать
    минимум n_min отсчётов."""
    spec = get_injection("NONE")
    params = _short_params()
    with EventLogger.open(tmp_jsonl, run_id="S1-TEST-001") as log:
        runner = ScenarioRunner(
            run_id="S1-TEST-001",
            params=params,
            hooks=spec.build_hooks(params),
            seed=42,
            sink=log.write,
        )
        summary = runner.run()
    assert summary.end_state == "POST"
    assert summary.n_measurements >= params.n_min


@pytest.mark.integration
def test_seq_miss_skips_hold_in_log(tmp_jsonl: Path) -> None:
    spec = get_injection("SEQ_MISS")
    params = _short_params()
    with EventLogger.open(tmp_jsonl, run_id="S1-TEST-002") as log:
        runner = ScenarioRunner(
            run_id="S1-TEST-002",
            params=params,
            hooks=spec.build_hooks(params),
            seed=42,
            sink=log.write,
        )
        runner.run()
    events = load_jsonl(tmp_jsonl)
    states = {e["state"] for e in events}
    assert "HOLD" not in states


@pytest.mark.integration
def test_time_under_hold_is_short(tmp_jsonl: Path) -> None:
    spec = get_injection("TIME_UNDER")
    params = _short_params()
    params.t_hold_min_s = 60.0   # сделаем минимум большим, чтобы 30 ≪ 60
    with EventLogger.open(tmp_jsonl, run_id="S1-TEST-003") as log:
        runner = ScenarioRunner(
            run_id="S1-TEST-003",
            params=params,
            hooks=spec.build_hooks(params),
            seed=42,
            sink=log.write,
        )
        runner.run()
    events = load_jsonl(tmp_jsonl)
    hold_end = next((e for e in events if e["event"] == "HOLD_END"), None)
    assert hold_end is not None
    assert hold_end["params"]["t_hold"] < 35.0  # инжектор форсирует ~30 c


@pytest.mark.integration
def test_n_too_low_collects_few_samples(tmp_jsonl: Path) -> None:
    spec = get_injection("N_TOO_LOW")
    params = _short_params()
    params.n_min = 20  # нормативный минимум, но инжектор остановит на 5
    with EventLogger.open(tmp_jsonl, run_id="S1-TEST-004") as log:
        runner = ScenarioRunner(
            run_id="S1-TEST-004",
            params=params,
            hooks=spec.build_hooks(params),
            seed=42,
            sink=log.write,
        )
        summary = runner.run()
    assert summary.n_measurements == 5


@pytest.mark.integration
def test_range_mism_overrides_T_set(tmp_jsonl: Path) -> None:
    spec = get_injection("RANGE_MISM")
    params = _short_params()
    with EventLogger.open(tmp_jsonl, run_id="S1-TEST-005") as log:
        runner = ScenarioRunner(
            run_id="S1-TEST-005",
            params=params,
            hooks=spec.build_hooks(params),
            seed=42,
            sink=log.write,
        )
        runner.run()
    events = load_jsonl(tmp_jsonl)
    run_start = next(e for e in events if e["event"] == "RUN_START")
    assert run_start["params"]["T_set"] == 700.0


@pytest.mark.unit
def test_all_injections_have_unique_codes() -> None:
    codes = [s.code for s in INJECTIONS.values()]
    assert len(codes) == len(set(codes))


@pytest.mark.unit
def test_get_injection_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_injection("UNKNOWN_CODE")
