"""Тесты модели теплопередачи `sim.thermal_model`.

Проверяется:
1. Сравнение `simulate_segment` с аналитическим решением
   T(t) = T_set − (T_set − T0)·exp(−t/τ) при отсутствии шума.
2. Воспроизводимость окрашенного шума при фиксированном seed.
3. Пошаговый ThermalIntegrator при постоянном u → ассимптотика
   к u·T_set_max.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from sim.thermal_model import (
    ThermalIntegrator,
    make_coloured_noise,
    simulate_segment,
)


@pytest.mark.unit
def test_simulate_segment_matches_analytic_when_noise_is_zero() -> None:
    """При sigma_K=0 и постоянном u=1.0 численное решение должно
    точно совпасть с аналитическим (с rtol интегратора 1e-6).
    """
    T0 = 0.0
    Tmax = 200.0
    tau = 60.0
    duration = 180.0
    res = simulate_segment(
        t0_s=0.0,
        t1_s=duration,
        T0_C=T0,
        u_fn=lambda t: 1.0,
        seed=0,
        tau_s=tau,
        T_set_max_C=Tmax,
        noise_sigma_K=0.0,
        max_step_s=0.5,
        method="RK45",
    )
    assert res.success
    T_analytic = Tmax - (Tmax - T0) * math.exp(-duration / tau)
    assert res.T_C[-1] == pytest.approx(T_analytic, rel=1e-3)


@pytest.mark.unit
def test_coloured_noise_reproducible_under_seed() -> None:
    """При одном seed функция должна возвращать одинаковую
    последовательность."""
    a = make_coloured_noise(duration_s=10.0, fs_hz=10.0, sigma_K=0.05, seed=42)
    b = make_coloured_noise(duration_s=10.0, fs_hz=10.0, sigma_K=0.05, seed=42)
    assert np.allclose(a, b)
    # СКО близко к target (с допуском)
    assert abs(a.std() - 0.05) < 0.02


@pytest.mark.unit
def test_thermal_integrator_steady_state_at_full_drive() -> None:
    """ThermalIntegrator при постоянном u=1 должен асимптотически
    стремиться к T_set_max."""
    integ = ThermalIntegrator(
        T0_C=20.0,
        seed=123,
        tau_s=10.0,
        T_set_max_C=100.0,
        noise_sigma_K=0.0,
    )
    for _ in range(int(60 * 10)):  # 60 c при шаге 0.1
        integ.step(0.1, 1.0)
    assert integ.T_C == pytest.approx(100.0, abs=0.5)


@pytest.mark.unit
def test_thermal_integrator_zero_drive_stays_cool() -> None:
    """При u=0 температура должна стремиться к 0 °C (определение
    модели)."""
    integ = ThermalIntegrator(
        T0_C=50.0,
        seed=0,
        tau_s=10.0,
        T_set_max_C=100.0,
        noise_sigma_K=0.0,
    )
    for _ in range(int(60 * 10)):
        integ.step(0.1, 0.0)
    assert integ.T_C == pytest.approx(0.0, abs=0.5)
