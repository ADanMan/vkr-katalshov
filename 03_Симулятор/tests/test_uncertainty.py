"""Тесты `sim.uncertainty_model`.

Проверяется:
1. Прямая и обратная функции PT100 (R↔T) — round-trip.
2. Допуски PT100 классов A/B по ГОСТ 6651-2009.
3. Проверочное значение W₁₀₀ = 1.385.
4. Бюджет неопределённости содержит все 6 компонентов.
5. Коэффициент Стьюдента для n=20 даёт ~2.093.
6. Диагностика dominant_component корректна.
"""

from __future__ import annotations

import numpy as np
import pytest

from sim.uncertainty_model import (
    UncertaintyBudget,
    _coverage_factor_student_t,
    estimate_uncertainty_from_samples,
    pt100_class_tolerance_C,
    pt100_resistance,
    pt100_temperature,
)


@pytest.mark.unit
def test_pt100_round_trip() -> None:
    for T in [0.0, 50.0, 100.0, 150.0, 200.0]:
        R = pt100_resistance(T)
        T_back = pt100_temperature(R)
        assert T_back == pytest.approx(T, abs=1e-6)


@pytest.mark.unit
def test_pt100_w100_normative_value() -> None:
    """W100 = R(100°C)/R(0°C) должно быть 1.385 (ГОСТ 6651-2009 п.5.1.1)."""
    R0 = pt100_resistance(0.0)
    R100 = pt100_resistance(100.0)
    W100 = R100 / R0
    assert W100 == pytest.approx(1.385, abs=1e-4)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("T_C", "cls", "expected"),
    [
        (0.0, "A", 0.15),
        (100.0, "A", 0.35),
        (200.0, "A", 0.55),
        (0.0, "B", 0.30),
        (100.0, "B", 0.80),
    ],
)
def test_pt100_class_tolerance(T_C: float, cls: str, expected: float) -> None:
    assert pt100_class_tolerance_C(T_C, sensor_class=cls) == pytest.approx(expected)


@pytest.mark.unit
def test_pt100_class_unknown_raises() -> None:
    with pytest.raises(ValueError):
        pt100_class_tolerance_C(100.0, sensor_class="X")


@pytest.mark.unit
def test_uncertainty_budget_contains_all_components() -> None:
    samples = np.full(20, 150.0) + np.random.default_rng(42).normal(0, 0.01, 20)
    b = estimate_uncertainty_from_samples(samples, t_run_hours=0.5)
    assert isinstance(b, UncertaintyBudget)
    assert b.n_samples == 20
    assert b.u_A > 0  # шум есть
    assert b.u_pt100 > 0
    assert b.u_self_heating > 0  # покрывает требование ГОСТ 6651 п.5.4
    assert b.u_quant > 0
    assert b.u_adc_noise > 0
    assert b.u_drift > 0
    assert b.u_combined > 0
    # u_combined должно быть >= max(component) (RSS)
    assert b.u_combined >= max(
        b.u_A, b.u_pt100, b.u_self_heating, b.u_quant, b.u_adc_noise, b.u_drift
    )


@pytest.mark.unit
def test_student_t_factor_n20_matches_table() -> None:
    """t_{0.95, 19} = 2.093 (двусторонний)."""
    k = _coverage_factor_student_t(n_samples=20, P=0.95)
    assert k == pytest.approx(2.093, abs=1e-3)


@pytest.mark.unit
def test_student_t_factor_n2_inflates() -> None:
    """t_{0.95, 1} ≈ 12.706 — должно быть значительно больше 2."""
    k = _coverage_factor_student_t(n_samples=2, P=0.95)
    assert k > 10.0


@pytest.mark.unit
def test_uncertainty_budget_dominance_systematic() -> None:
    """При нулевом разбросе и большой систематике dominant=systematic."""
    samples = np.full(20, 150.0)  # ровный сигнал → u_A = 0
    b = estimate_uncertainty_from_samples(samples)
    assert b.u_A == 0.0
    assert b.dominant_component == "systematic"
    d = b.to_dict()
    assert d["diagnostic_GOST_8207"]["dominant_component"] == "systematic"


@pytest.mark.unit
def test_uncertainty_budget_coverage_method_options() -> None:
    samples = np.full(20, 150.0) + np.random.default_rng(0).normal(0, 0.05, 20)
    b_fixed = estimate_uncertainty_from_samples(samples, coverage_factor=2.0)
    b_student = estimate_uncertainty_from_samples(samples, coverage_factor="student_t")
    assert b_fixed.coverage_method == "fixed"
    assert b_student.coverage_method == "student_t"
    # Для n=20 t≈2.093 > 2.0
    assert b_student.coverage_factor_k > b_fixed.coverage_factor_k


@pytest.mark.unit
def test_uncertainty_budget_invalid_coverage_factor() -> None:
    samples = np.full(5, 100.0)
    with pytest.raises(ValueError):
        estimate_uncertainty_from_samples(samples, coverage_factor="bogus")  # type: ignore[arg-type]


@pytest.mark.unit
def test_estimate_uncertainty_empty_samples_raises() -> None:
    with pytest.raises(ValueError):
        estimate_uncertainty_from_samples(np.array([]))
