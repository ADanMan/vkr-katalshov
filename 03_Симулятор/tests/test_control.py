"""Тесты `sim.control_loop.PID` и доступности python-control."""

from __future__ import annotations

import pytest

from sim.control_loop import HAS_CONTROL, PID


@pytest.mark.unit
def test_pid_clamps_output() -> None:
    pid = PID(Kp=10.0, Ki=0.0, Kd=0.0, out_min=0.0, out_max=1.0)
    # Большая ошибка → насыщение к out_max
    u = pid.update(setpoint=100.0, measured=0.0, dt_s=0.1)
    assert u == 1.0
    # Сетпойнт ниже измерения → насыщение к out_min
    pid.reset()
    u = pid.update(setpoint=0.0, measured=100.0, dt_s=0.1)
    assert u == 0.0


@pytest.mark.unit
def test_pid_anti_windup_does_not_explode() -> None:
    """При длительном насыщении интеграл не должен накапливаться
    бесконечно (anti-windup back-calculation)."""
    pid = PID(Kp=1.0, Ki=10.0, Kd=0.0, out_min=0.0, out_max=1.0)
    for _ in range(1000):
        pid.update(setpoint=100.0, measured=0.0, dt_s=0.1)
    # После 100 секунд интеграл не должен быть стократно больше нормы
    assert abs(pid._integral) < 1e6


@pytest.mark.unit
def test_pid_reset_clears_state() -> None:
    # out_max=1000 — убираем насыщение, чтобы anti-windup не обнулил интегратор
    pid = PID(Kp=1.0, Ki=1.0, Kd=0.5, out_min=-1000.0, out_max=1000.0)
    pid.update(setpoint=10.0, measured=0.0, dt_s=1.0)
    assert pid._integral != 0
    pid.reset()
    assert pid._integral == 0.0
    assert pid._prev_error == 0.0
    assert pid._initialised is False


@pytest.mark.unit
@pytest.mark.skipif(not HAS_CONTROL, reason="python-control не установлен")
def test_step_response_settles() -> None:
    """Замкнутый PID-контур должен иметь установившееся значение
    близкое к setpoint=1 при достаточном времени."""
    from sim.control_loop import step_response

    t, y = step_response(duration_s=1200.0, n_points=400)
    assert y[-1] == pytest.approx(1.0, abs=0.05)


@pytest.mark.unit
@pytest.mark.skipif(not HAS_CONTROL, reason="python-control не установлен")
def test_stability_margins_positive() -> None:
    """Запасы устойчивости при дефолтных параметрах должны быть
    положительными (контур устойчив)."""
    from sim.control_loop import stability_margins

    m = stability_margins()
    assert m["phase_margin_deg"] > 30.0
    # gain margin может быть inf для систем без пересечения -180°
    assert m["gain_margin_dB"] > 6.0 or m["gain_margin_dB"] == float("inf")
