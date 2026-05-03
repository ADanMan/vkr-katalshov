"""
sim.uncertainty_model — propagation погрешностей через измерительную
цепь стенда S1, реализованная через библиотеку `uncertainties`.

Цепь: T_объект → PT100 (R(T)) → нормирующий усилитель (опускаем,
считаем линейным с единичным коэффициентом) → 16-битный АЦП →
программная инверсия R → T.

Составляющие неопределённости:
  Класс A (статистическая):
    1. СКО отсчётов температуры (рассчитывается по выборке из MEASURE).
    2. Тепловые флуктуации объекта (system noise) — частично попадают
       в выборку MEASURE и закрываются классом A.
  Класс B (систематическая, оценивается по характеристикам):
    3. Допуск PT100 класса A:
         δT_pt100 = ±(0.15 + 0.002·|T|) °C
       по ГОСТ 6651-2009, табл. A.1.
    4. Квантование АЦП: u_quant = q / √12, где q — шаг квантования.
    5. Шум АЦП: σ_adc = ADC_NOISE_SIGMA_LSB · q.
    6. Дрейф нуля АЦП: u_drift = ADC_DRIFT_PER_HOUR · t_run.

Суммарная стандартная неопределённость u_C — корень из суммы
квадратов составляющих (некоррелированные источники):

    u_C(T) = √( u_A² + u_pt100² + u_quant² + u_adc² + u_drift² )

Расширенная неопределённость U = k · u_C, где k = 2 для уровня
доверия P ≈ 0.95 (по ГОСТ 8.207-76 / GUM JCGM 100:2008).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats as sstats
from uncertainties import UFloat, ufloat
from uncertainties.umath import sqrt as usqrt

from . import config as cfg


# ----------------------------------------------------------------------
# Помощники: характеристики PT100 и АЦП
# ----------------------------------------------------------------------


def pt100_resistance(T_C: float) -> float:
    """Сопротивление PT100 при температуре T (°C) — прямая функция R(T).
    ГОСТ 6651-2009, формула квадратичной аппроксимации для T ≥ 0:
        R = R0 · (1 + α·T + β·T²).
    """
    R0 = cfg.to_ohm(cfg.R0)
    alpha = cfg.ALPHA.to("1 / kelvin").magnitude
    beta = cfg.BETA.to("1 / kelvin**2").magnitude
    return R0 * (1.0 + alpha * T_C + beta * T_C * T_C)


def pt100_temperature(R_ohm: float) -> float:
    """Температура (°C) по сопротивлению PT100 — обратная функция R⁻¹(R).
    Решение квадратного уравнения, ветка T ≥ 0."""
    R0 = cfg.to_ohm(cfg.R0)
    alpha = cfg.ALPHA.to("1 / kelvin").magnitude
    beta = cfg.BETA.to("1 / kelvin**2").magnitude
    discriminant = alpha * alpha - 4.0 * beta * (1.0 - R_ohm / R0)
    if discriminant < 0:
        # Численная нестабильность около 0 °C
        discriminant = 0.0
    return (-alpha + math.sqrt(discriminant)) / (2.0 * beta)


def adc_quantum_C() -> float:
    """Размер шага квантования АЦП в °C."""
    span_C = cfg.to_celsius(cfg.ADC_RANGE_MAX) - cfg.to_celsius(cfg.ADC_RANGE_MIN)
    return span_C / (2 ** cfg.ADC_BITS - 1)


def pt100_class_tolerance_C(T_C: float, sensor_class: str | None = None) -> float:
    """
    Допуск PT100 (по модулю), °C, по ГОСТ 6651-2009 / IEC 60751.
    Класс A: ±(0.15 + 0.002·|T|).
    Класс B: ±(0.30 + 0.005·|T|).
    """
    cls = sensor_class or cfg.SENSOR_CLASS
    cls = cls.upper()
    if cls == "A":
        return 0.15 + 0.002 * abs(T_C)
    if cls == "B":
        return 0.30 + 0.005 * abs(T_C)
    raise ValueError(f"Unknown PT100 class: {cls!r}")


# ----------------------------------------------------------------------
# Структура отчёта о неопределённости
# ----------------------------------------------------------------------


@dataclass
class UncertaintyBudget:
    """Полный «бюджет неопределённости» одного измерения / выборки.

    Все компоненты — стандартные неопределённости (СКО), °C.
    """

    # Класс A
    u_A: float                          # статистическая по выборке
    n_samples: int                      # число отсчётов в выборке

    # Класс B
    u_pt100: float                      # допуск сенсора
    u_self_heating: float               # самонагрев (ГОСТ 6651-2009 п.5.4)
    u_quant: float                      # квантование АЦП
    u_adc_noise: float                  # шум АЦП
    u_drift: float                      # дрейф нуля АЦП

    # Сводка
    u_combined: float                   # суммарная стандартная (root-sum-square)
    coverage_factor_k: float            # 2 для GUM или t-Стьюдента для ГОСТ 8.207
    U_expanded: float                   # расширенная = k · u_combined
    coverage_method: str                # 'fixed' | 'student_t'

    # Диагностика по ГОСТ 8.207-76 п. 5
    theta_combined: float               # суммарная систематическая (компоненты класса B)
    delta_random: float                 # случайная (= u_A)
    dominant_component: str             # 'systematic' | 'random' | 'mixed'

    # Контекст
    mean_T_C: float                     # среднее измерение, °C
    t_run_hours: float                  # длительность прогона, ч
    sensor_class: str = field(default="A")

    def to_dict(self) -> dict:
        """Сериализация в JSON-совместимый словарь."""
        return {
            "mean_T_C": self.mean_T_C,
            "n_samples": self.n_samples,
            "components": {
                "u_A_statistical": self.u_A,
                "u_pt100_class": self.u_pt100,
                "u_self_heating": self.u_self_heating,
                "u_quant_adc": self.u_quant,
                "u_adc_noise": self.u_adc_noise,
                "u_drift_adc": self.u_drift,
            },
            "u_combined": self.u_combined,
            "coverage_factor_k": self.coverage_factor_k,
            "coverage_method": self.coverage_method,
            "U_expanded_P95": self.U_expanded,
            "diagnostic_GOST_8207": {
                "delta_random_S_A": self.delta_random,
                "theta_systematic_combined": self.theta_combined,
                "ratio_theta_over_S_A": (
                    float("inf") if self.delta_random == 0
                    else self.theta_combined / self.delta_random
                ),
                "dominant_component": self.dominant_component,
                "interpretation": _interpret_dominance(
                    self.dominant_component, self.theta_combined, self.delta_random
                ),
            },
            "sensor_class": self.sensor_class,
            "t_run_hours": self.t_run_hours,
            "report_line": (
                f"T = ({self.mean_T_C:.3f} ± {self.U_expanded:.3f}) °C, "
                f"k = {self.coverage_factor_k:.3f}, P ≈ 0.95"
            ),
        }


def _interpret_dominance(dominant: str, theta: float, delta: float) -> str:
    """Текстовая интерпретация по ГОСТ 8.207-76 п. 5."""
    if delta == 0:
        return "Случайная составляющая отсутствует (n=1) — итог определяется систематикой"
    ratio = theta / delta
    if dominant == "systematic":
        return f"θ/S(A) ≈ {ratio:.2f} > 8: случайная составляющая пренебрежимо мала; итог ≈ θ"
    if dominant == "random":
        return f"θ/S(A) ≈ {ratio:.2f} < 0.8: систематика пренебрежима; итог ≈ Δ"
    return f"θ/S(A) ≈ {ratio:.2f} ∈ [0.8; 8]: смешанный режим, корректная композиция"


# ----------------------------------------------------------------------
# Базовый расчёт по статической точке
# ----------------------------------------------------------------------


def _coverage_factor_student_t(n_samples: int, P: float = 0.95) -> float:
    """Коэффициент Стьюдента t_{P, n-1} для двусторонней доверительной
    вероятности P. По ГОСТ 8.207-76 п. 3.2 / приложение 2.

    При n = 1 (нет статистической выборки) возвращает 2.0 как стандартный
    GUM-фактор для P ≈ 0.95.
    """
    if n_samples <= 1:
        return 2.0
    df = n_samples - 1
    return float(sstats.t.ppf(0.5 + P / 2.0, df))


def estimate_uncertainty_from_samples(
    samples_C: np.ndarray,
    *,
    t_run_hours: float = 0.0,
    sensor_class: str | None = None,
    coverage_factor: float | str = 2.0,
    confidence_P: float = 0.95,
) -> UncertaintyBudget:
    """
    Полный расчёт бюджета неопределённости по выборке отсчётов
    температуры из режима MEASURE.

    Параметры
    ---------
    samples_C : массив значений температуры (°C), полученных в MEASURE.
    t_run_hours : длительность прогона до момента измерения, ч
                  (для оценки дрейфа АЦП).
    sensor_class : 'A' или 'B'; по умолчанию из config.
    coverage_factor : k для расширенной неопределённости.
        * float (например, 2.0) — фиксированный GUM-стиль для P≈0.95.
        * 'student_t' — рассчитать по таблице Стьюдента на основе n
          (соответствует ГОСТ 8.207-76 п. 3.2). При n>30 практически
          совпадает с фиксированным k=2.
    confidence_P : уровень доверительной вероятности (для student_t).

    Возвращает UncertaintyBudget с полным разбиением и диагностикой
    «случайная vs систематическая» по ГОСТ 8.207-76 п. 5.
    """
    if len(samples_C) == 0:
        raise ValueError("Empty samples array")

    samples = np.asarray(samples_C, dtype=float)
    n = len(samples)
    mean_T = float(samples.mean())

    # Класс A — стандартное отклонение среднего по ГОСТ 8.207-76 п. 2.4
    if n > 1:
        sample_std = float(samples.std(ddof=1))
        u_A = sample_std / math.sqrt(n)
    else:
        u_A = 0.0

    # Класс B — компоненты по характеристикам:
    cls = sensor_class or cfg.SENSOR_CLASS

    # 1. Допуск PT100 (по модулю) делим на √3 (равномерное распределение)
    pt100_tol = pt100_class_tolerance_C(mean_T, sensor_class=cls)
    u_pt100 = pt100_tol / math.sqrt(3.0)

    # 2. Самонагрев датчика (ГОСТ 6651-2009 п. 5.4) — равномерное
    self_heating_C = cfg.SENSOR_SELF_HEATING_C.to("delta_degC").magnitude
    u_self_heating = abs(self_heating_C) / math.sqrt(3.0)

    # 3. Квантование АЦП — равномерное распределение шириной q
    q = adc_quantum_C()
    u_quant = q / math.sqrt(12.0)

    # 4. Шум АЦП — задан как СКО в LSB → переводим в °C
    u_adc_noise = cfg.ADC_NOISE_SIGMA_LSB * q

    # 5. Дрейф нуля — линейный, оценка как равномерное распределение
    drift_per_hour = cfg.ADC_DRIFT_PER_HOUR.to("delta_degC / hour").magnitude
    drift_total = abs(drift_per_hour) * t_run_hours
    u_drift = drift_total / math.sqrt(3.0)

    # Суммарная стандартная неопределённость (root-sum-square,
    # некоррелированные компоненты — GUM 5.1.2)
    u_combined = math.sqrt(
        u_A * u_A
        + u_pt100 * u_pt100
        + u_self_heating * u_self_heating
        + u_quant * u_quant
        + u_adc_noise * u_adc_noise
        + u_drift * u_drift
    )

    # Расширенная неопределённость
    if isinstance(coverage_factor, str) and coverage_factor.lower() in {"student_t", "auto"}:
        k = _coverage_factor_student_t(n, P=confidence_P)
        coverage_method = "student_t"
    elif isinstance(coverage_factor, (int, float)):
        k = float(coverage_factor)
        coverage_method = "fixed"
    else:
        raise ValueError(
            f"coverage_factor must be float or 'student_t', got {coverage_factor!r}"
        )

    # Диагностика по ГОСТ 8.207-76 п. 5: соотношение случайной и
    # систематической составляющих. theta = композиция всех B-компонентов
    theta_combined = math.sqrt(
        u_pt100 * u_pt100
        + u_self_heating * u_self_heating
        + u_quant * u_quant
        + u_adc_noise * u_adc_noise
        + u_drift * u_drift
    )
    delta_random = u_A
    if delta_random == 0:
        dominant = "systematic"
    else:
        ratio = theta_combined / delta_random
        if ratio > 8.0:
            dominant = "systematic"
        elif ratio < 0.8:
            dominant = "random"
        else:
            dominant = "mixed"

    return UncertaintyBudget(
        u_A=u_A,
        n_samples=n,
        u_pt100=u_pt100,
        u_self_heating=u_self_heating,
        u_quant=u_quant,
        u_adc_noise=u_adc_noise,
        u_drift=u_drift,
        u_combined=u_combined,
        coverage_factor_k=k,
        U_expanded=k * u_combined,
        coverage_method=coverage_method,
        theta_combined=theta_combined,
        delta_random=delta_random,
        dominant_component=dominant,
        mean_T_C=mean_T,
        t_run_hours=t_run_hours,
        sensor_class=cls,
    )


# ----------------------------------------------------------------------
# Symbolic propagation через `uncertainties` — для главы 2 ПЗ
# ----------------------------------------------------------------------


def propagate_through_pt100(T_with_unc: UFloat) -> UFloat:
    """Прокинуть температуру с заданной неопределённостью через
    нелинейную характеристику PT100; возвращает сопротивление с
    автоматически вычисленной неопределённостью.

    Это символическая иллюстрация GUM-метода для главы 2 ПЗ:
        u_R = |dR/dT|_T0 · u_T
    Библиотека `uncertainties` делает это автоматически через
    автоматическое дифференцирование.
    """
    R0 = cfg.to_ohm(cfg.R0)
    alpha = cfg.ALPHA.to("1 / kelvin").magnitude
    beta = cfg.BETA.to("1 / kelvin**2").magnitude
    return R0 * (1.0 + alpha * T_with_unc + beta * T_with_unc * T_with_unc)


def propagate_inverse_pt100(R_with_unc: UFloat) -> UFloat:
    """Обратная пропогация: сопротивление с неопределённостью →
    температура с неопределённостью."""
    R0 = cfg.to_ohm(cfg.R0)
    alpha = cfg.ALPHA.to("1 / kelvin").magnitude
    beta = cfg.BETA.to("1 / kelvin**2").magnitude
    discriminant = alpha * alpha - 4.0 * beta * (1.0 - R_with_unc / R0)
    return (-alpha + usqrt(discriminant)) / (2.0 * beta)


def measurement_with_full_uncertainty(
    mean_T_C: float,
    *,
    t_run_hours: float = 0.0,
    sensor_class: str | None = None,
) -> UFloat:
    """Удобная обёртка: возвращает UFloat (T_mean, u_combined) для
    одной точки T без выборки (n=1). Используется для онлайн-оценки
    в дашборде."""
    samples = np.array([mean_T_C])
    budget = estimate_uncertainty_from_samples(
        samples, t_run_hours=t_run_hours, sensor_class=sensor_class
    )
    # Класс A = 0 при n=1, поэтому суммарная без неё
    return ufloat(mean_T_C, budget.u_combined)


__all__ = [
    "pt100_resistance",
    "pt100_temperature",
    "adc_quantum_C",
    "pt100_class_tolerance_C",
    "UncertaintyBudget",
    "estimate_uncertainty_from_samples",
    "propagate_through_pt100",
    "propagate_inverse_pt100",
    "measurement_with_full_uncertainty",
    "_coverage_factor_student_t",
]
