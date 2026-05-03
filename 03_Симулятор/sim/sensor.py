"""
sim.sensor — модель измерительной цепи: PT100 + АЦП.

Цепь:
    T_объект (°C)
        ↓ PT100 R(T) — нелинейная характеристика по ГОСТ 6651-2009
    R (Ом)
        ↓ нормирующий усилитель — линейный, единичный коэффициент
          (опускаем как идеальный)
    U (В) → АЦП 16 бит, диапазон 0…500 °C
        ↓ квантование + аддитивный шум + долговременный дрейф нуля
    T_показанная (°C)

Дополнительно учитывается тепловая инерция самого датчика —
PT100 не успевает отслеживать резкие изменения T_объекта мгновенно,
а ведёт себя как RC-фильтр с постоянной времени SENSOR_TIME_CONSTANT.
Это реализовано как первого порядка фильтр на дискретной сетке.

Все случайные процессы параметризованы numpy.random.Generator с
заданным seed — обеспечивает побитовую воспроизводимость прогонов.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config as cfg
from . import uncertainty_model as um


# ----------------------------------------------------------------------
# Структуры
# ----------------------------------------------------------------------


@dataclass
class SensorReading:
    """Один отсчёт сенсора."""

    t_s: float            # время от начала прогона, с
    T_object_C: float     # истинная температура объекта (для отладки)
    T_internal_C: float   # температура чувствительного элемента
                          # (после теплового RC-фильтра)
    R_ohm: float          # сопротивление PT100
    adc_code: int         # код АЦП
    T_indicated_C: float  # показание после восстановления T(R)


# ----------------------------------------------------------------------
# АЦП
# ----------------------------------------------------------------------


class ADC16:
    """16-битный АЦП с диапазоном 0…500 °C, шумом и долговременным
    дрейфом нуля.

    Идеальный нормирующий усилитель опущен — считаем, что R PT100
    линейно отображается на код АЦП в пропорции к диапазону температур
    (на практике это делает нормирующий мост с источником тока 1 мА).
    """

    def __init__(self, *, seed: int | None = None) -> None:
        self.bits = cfg.ADC_BITS
        self.T_min = cfg.to_celsius(cfg.ADC_RANGE_MIN)
        self.T_max = cfg.to_celsius(cfg.ADC_RANGE_MAX)
        self.q_C = um.adc_quantum_C()
        self.noise_sigma_LSB = cfg.ADC_NOISE_SIGMA_LSB
        self.drift_per_hour_C = cfg.ADC_DRIFT_PER_HOUR.to(
            "delta_degC / hour"
        ).magnitude
        self._rng = np.random.default_rng(seed)

    @property
    def fs_max(self) -> int:
        return 2 ** self.bits - 1

    def temperature_to_code(self, T_C: float, *, t_run_hours: float = 0.0) -> int:
        """Преобразовать температуру в код АЦП с учётом квантования,
        шума и дрейфа нуля.

        Это «упрощённая модель»: код пропорционален температуре, как
        если бы аналоговый тракт был идеально линейным. Реальная
        нелинейность PT100 учитывается отдельно при пересчёте кода
        обратно в температуру в `code_to_temperature_via_resistance`.
        """
        # Дрейф нуля АЦП
        drift_C = self.drift_per_hour_C * t_run_hours

        # Аддитивный гауссов шум АЦП в LSB
        noise_LSB = float(self._rng.standard_normal() * self.noise_sigma_LSB)

        # Идеальный код
        T_clamped = max(self.T_min, min(self.T_max, T_C + drift_C))
        ideal_code = (T_clamped - self.T_min) / (self.T_max - self.T_min) * self.fs_max

        # Квантование + шум
        return int(np.clip(round(ideal_code + noise_LSB), 0, self.fs_max))

    def code_to_temperature(self, code: int) -> float:
        """Восстановить температуру из кода АЦП (линейная инверсия)."""
        return self.T_min + (code / self.fs_max) * (self.T_max - self.T_min)


# ----------------------------------------------------------------------
# Модель PT100 с тепловой инерцией
# ----------------------------------------------------------------------


class PT100Sensor:
    """Чувствительный элемент PT100 с собственной тепловой инерцией.

    Внутреннее состояние — температура чувствительного элемента T_int,
    которая «отстаёт» от температуры объекта T_obj по уравнению:

        d T_int / dt = (T_obj - T_int) / τ_sensor

    Где τ_sensor = SENSOR_TIME_CONSTANT (≈ 2 c для тонкоплёночного).

    Реализовано в виде дискретного шага через явный Эйлер.
    """

    def __init__(self, *, T0_C: float | None = None) -> None:
        self.T_int_C: float = (
            cfg.to_celsius(cfg.T_AMBIENT) if T0_C is None else T0_C
        )
        self.tau_s: float = cfg.to_seconds(cfg.SENSOR_TIME_CONSTANT)

    def step(self, dt_s: float, T_object_C: float) -> float:
        """Сделать шаг dt_s, возвращает текущую T_int."""
        if dt_s > 0:
            dT = (T_object_C - self.T_int_C) / self.tau_s
            self.T_int_C += dT * dt_s
        return self.T_int_C

    def resistance_ohm(self) -> float:
        """Сопротивление PT100 при текущей температуре чувствит. эл-та."""
        return um.pt100_resistance(self.T_int_C)


# ----------------------------------------------------------------------
# Полная цепь: PT100 + АЦП + восстановление T(R)
# ----------------------------------------------------------------------


class MeasurementChain:
    """Полная измерительная цепь стенда S1.

    Используется так:
        chain = MeasurementChain(seed=42)
        for t, T_obj in trajectory:
            reading = chain.read(t_s=t, T_object_C=T_obj, dt_s=0.1)
        # reading.T_indicated_C — то, что видит сценарий измерения

    Параметр dt_s — длительность с прошлого вызова read(); используется
    для тепловой инерции PT100 и накопления дрейфа АЦП.
    """

    def __init__(self, *, seed: int | None = None) -> None:
        self.pt100 = PT100Sensor()
        self.adc = ADC16(seed=seed)
        self._t_total_s: float = 0.0

    def read(
        self,
        *,
        t_s: float,
        T_object_C: float,
        dt_s: float,
    ) -> SensorReading:
        """Один отсчёт измерительной цепи."""
        # 1. Обновить тепловое состояние сенсора
        T_int = self.pt100.step(dt_s, T_object_C)

        # 2. Сопротивление PT100 при T_int
        R = self.pt100.resistance_ohm()

        # 3. Накопленное время прогона — для дрейфа АЦП
        self._t_total_s = max(self._t_total_s, t_s)
        t_run_hours = self._t_total_s / 3600.0

        # 4. АЦП-преобразование
        # Передаём именно T_int (то, что «видит» датчик), а не T_obj
        code = self.adc.temperature_to_code(T_int, t_run_hours=t_run_hours)

        # 5. Программное восстановление через линейную инверсию АЦП.
        # На практике в ИИС часто хранится R и потом считается
        # обратная функция R⁻¹, но здесь ради простоты — сразу T.
        T_ind = self.adc.code_to_temperature(code)

        return SensorReading(
            t_s=t_s,
            T_object_C=float(T_object_C),
            T_internal_C=float(T_int),
            R_ohm=float(R),
            adc_code=int(code),
            T_indicated_C=float(T_ind),
        )


__all__ = [
    "SensorReading",
    "ADC16",
    "PT100Sensor",
    "MeasurementChain",
]
