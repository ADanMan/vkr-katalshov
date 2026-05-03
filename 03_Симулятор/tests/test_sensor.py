"""Тесты измерительной цепи `sim.sensor`."""

from __future__ import annotations

import pytest

from sim.sensor import ADC16, MeasurementChain, PT100Sensor


@pytest.mark.unit
def test_adc16_round_trip_within_quantum() -> None:
    """temperature_to_code → code_to_temperature должно отличаться
    от исходной температуры не более чем на квантование."""
    adc = ADC16(seed=42)
    for T in [50.0, 100.0, 150.0, 200.0]:
        code = adc.temperature_to_code(T)
        T_back = adc.code_to_temperature(code)
        assert abs(T_back - T) <= adc.q_C * 2.0  # 2·LSB на шум + округление


@pytest.mark.unit
def test_adc16_clamps_outside_range() -> None:
    adc = ADC16(seed=0)
    code_lo = adc.temperature_to_code(-100.0)
    code_hi = adc.temperature_to_code(1000.0)
    assert code_lo == 0
    assert code_hi == adc.fs_max


@pytest.mark.unit
def test_pt100_sensor_lags_object() -> None:
    """T_int сенсора должна отставать от резкого скачка T_object."""
    sensor = PT100Sensor(T0_C=20.0)
    # Резкий скачок до 100 °C
    T_int_after_1s = sensor.step(1.0, 100.0)
    assert T_int_after_1s < 100.0  # ещё не догнал
    # Через 10 c — близко
    for _ in range(20):
        sensor.step(0.5, 100.0)
    assert sensor.T_int_C == pytest.approx(100.0, abs=1.0)


@pytest.mark.unit
def test_measurement_chain_indicated_close_to_object() -> None:
    """В стационарном режиме T_indicated должна быть близка к
    T_object с точностью класса A PT100 + квант АЦП."""
    chain = MeasurementChain(seed=7)
    # Дать сенсору устаканиться при T=150 °C
    for _ in range(200):
        reading = chain.read(t_s=0.0, T_object_C=150.0, dt_s=0.5)
    # После 100 c при tau=2 c сенсор полностью догнал
    assert reading.T_indicated_C == pytest.approx(150.0, abs=0.5)


@pytest.mark.unit
def test_measurement_chain_respects_seed() -> None:
    chain1 = MeasurementChain(seed=99)
    chain2 = MeasurementChain(seed=99)
    r1 = chain1.read(t_s=0.0, T_object_C=120.0, dt_s=0.1)
    r2 = chain2.read(t_s=0.0, T_object_C=120.0, dt_s=0.1)
    assert r1.adc_code == r2.adc_code
