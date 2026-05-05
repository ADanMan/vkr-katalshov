"""
sim.thermal_model — физическая модель термокамеры.

Используется scipy.integrate.solve_ivp как профессиональный
ODE-интегратор с адаптивным шагом и контролем локальной ошибки,
вместо ручного явного Эйлера.

Уравнение теплопередачи 1-го порядка с управлением и шумом:

    dT/dt = (u(t) * T_set_max - T) / τ + ξ(t),

где u(t) ∈ [0; 1] — нормированный выход PID-регулятора (скважность
ШИМ нагревателя), τ — постоянная времени системы, ξ(t) — окрашенный
гауссовский шум объекта.

Шум окрашивается через scipy.signal с целью имитировать тепловые
флуктуации, не являющиеся чистым AWGN: типичная корреляционная длина
порядка нескольких секунд.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.signal import lfilter

from . import config as cfg

# ----------------------------------------------------------------------
# Шум объекта (окрашенный)
# ----------------------------------------------------------------------


def make_coloured_noise(
    duration_s: float,
    fs_hz: float,
    sigma_K: float,
    correlation_time_s: float = 5.0,
    seed: int | None = None,
) -> np.ndarray:
    """
    Сгенерировать окрашенный гауссов шум — белый, пропущенный через
    однополюсный low-pass с τ_corr = correlation_time_s.

    Параметры
    ---------
    duration_s : длительность участка, с
    fs_hz : частота дискретизации, Гц
    sigma_K : СКО шума, К
    correlation_time_s : корреляционная длина, с
    seed : seed для воспроизводимости

    Возвращает
    ----------
    np.ndarray длины int(duration_s * fs_hz) — отсчёты шума.
    """
    rng = np.random.default_rng(seed)
    n = max(int(duration_s * fs_hz), 1)
    white = rng.standard_normal(n) * sigma_K

    # Однополюсный low-pass с дискретной аппроксимацией
    # y[n] = α·y[n-1] + (1-α)·x[n], α = exp(-1/(τ·fs))
    alpha = float(np.exp(-1.0 / max(correlation_time_s * fs_hz, 1.0)))
    b = [1.0 - alpha]
    a = [1.0, -alpha]
    coloured = lfilter(b, a, white)

    # Коррекция СКО после фильтрации (low-pass снижает мощность).
    # Эмпирический коэффициент → возвращаем target sigma.
    actual = coloured.std()
    if actual > 1e-12:
        coloured = coloured * (sigma_K / actual)
    return coloured


# ----------------------------------------------------------------------
# Модель теплопередачи
# ----------------------------------------------------------------------


@dataclass
class ThermalState:
    """Снимок состояния тепловой системы."""

    t_s: float       # время от начала прогона, с
    T_C: float       # текущая температура, °C


@dataclass
class ThermalSimResult:
    """Результат численного интегрирования отрезка t ∈ [t0; t1]."""

    t_s: np.ndarray   # массив времён, с
    T_C: np.ndarray   # массив температур, °C
    success: bool
    message: str


def _heat_eq(
    t: float,
    T_arr: np.ndarray,
    *,
    u_fn: Callable[[float], float],
    tau_s: float,
    T_set_max_C: float,
    noise_fn: Callable[[float], float],
) -> np.ndarray:
    """
    Правая часть ODE dT/dt в формате scipy.integrate.solve_ivp.

    T_arr — состояние ([T_C]) формой (1,).
    """
    T_now = float(T_arr[0])
    u = float(np.clip(u_fn(t), 0.0, 1.0))
    drive = (u * T_set_max_C - T_now) / tau_s
    return np.array([drive + noise_fn(t)])


def simulate_segment(
    *,
    t0_s: float,
    t1_s: float,
    T0_C: float,
    u_fn: Callable[[float], float],
    seed: int | None = None,
    tau_s: float | None = None,
    T_set_max_C: float | None = None,
    noise_sigma_K: float | None = None,
    correlation_time_s: float = 5.0,
    max_step_s: float | None = None,
    method: str = "RK45",
) -> ThermalSimResult:
    """
    Проинтегрировать модель теплопередачи на интервале [t0_s; t1_s]
    из начального условия T(t0) = T0_C при заданной функции
    управления u(t).

    Параметры
    ---------
    t0_s, t1_s : концы временного интервала, с
    T0_C : начальная температура, °C
    u_fn : функция времени → нормированный сигнал управления [0;1]
    seed : seed для воспроизводимого шума
    tau_s : постоянная времени; если None — берётся из config.TAU
    T_set_max_C : предел нагрева; если None — config.T_SET_MAX
    noise_sigma_K : СКО шума объекта; если None — config.SYSTEM_NOISE_SIGMA
    correlation_time_s : корреляционная длина шума
    max_step_s : ограничение шага интегратора; None → config.DT_MAX
    method : метод интегрирования scipy.integrate.solve_ivp
             ('RK45', 'LSODA', 'BDF', 'Radau', и т.д.)

    Возвращает
    ----------
    ThermalSimResult с массивами t_s и T_C.
    """
    tau = float(cfg.to_seconds(cfg.TAU)) if tau_s is None else tau_s
    Tmax = float(cfg.to_celsius(cfg.T_SET_MAX)) if T_set_max_C is None else T_set_max_C
    sigma = (
        float(cfg.SYSTEM_NOISE_SIGMA.to("delta_degC").magnitude)
        if noise_sigma_K is None
        else noise_sigma_K
    )
    step_lim = float(cfg.to_seconds(cfg.DT_MAX)) if max_step_s is None else max_step_s

    # Готовим окрашенный шум на сетке частоты fs = 1/max_step
    fs = 1.0 / step_lim
    duration = max(t1_s - t0_s, step_lim)
    noise_samples = make_coloured_noise(
        duration_s=duration,
        fs_hz=fs,
        sigma_K=sigma,
        correlation_time_s=correlation_time_s,
        seed=seed,
    )

    def noise_fn(t: float) -> float:
        idx = int((t - t0_s) * fs)
        idx = max(0, min(idx, len(noise_samples) - 1))
        return float(noise_samples[idx])

    # scipy.solve_ivp принимает только args=(...) кортежем позиционных
    # аргументов, но _heat_eq использует keyword-only. Используем замыкание:
    return _simulate_via_closure(
        t0_s=t0_s,
        t1_s=t1_s,
        T0_C=T0_C,
        u_fn=u_fn,
        tau_s=tau,
        T_set_max_C=Tmax,
        noise_fn=noise_fn,
        max_step_s=step_lim,
        method=method,
    )


def _simulate_via_closure(
    *,
    t0_s: float,
    t1_s: float,
    T0_C: float,
    u_fn: Callable[[float], float],
    tau_s: float,
    T_set_max_C: float,
    noise_fn: Callable[[float], float],
    max_step_s: float,
    method: str,
) -> ThermalSimResult:
    """Вспомогательная обёртка с замыканием — обходит ограничение
    scipy.solve_ivp на kwargs."""

    def rhs(t: float, y: np.ndarray) -> np.ndarray:
        return _heat_eq(
            t,
            y,
            u_fn=u_fn,
            tau_s=tau_s,
            T_set_max_C=T_set_max_C,
            noise_fn=noise_fn,
        )

    sol = solve_ivp(
        fun=rhs,
        t_span=(t0_s, t1_s),
        y0=[T0_C],
        method=method,
        max_step=max_step_s,
        rtol=1e-6,
        atol=1e-8,
    )
    return ThermalSimResult(
        t_s=sol.t,
        T_C=sol.y[0],
        success=bool(sol.success),
        message=str(sol.message),
    )


# ----------------------------------------------------------------------
# Удобный API: пошаговое интегрирование (для simpy-сценария)
# ----------------------------------------------------------------------


class ThermalIntegrator:
    """
    Пошаговый интегратор: умеет двигаться вперёд во времени
    короткими шагами Δt ≤ max_step с заданной функцией управления.

    Используется в scenario_runner: simpy ставит таймауты, после
    каждого таймаута мы продвигаем тепловую модель на это Δt.
    """

    def __init__(
        self,
        *,
        T0_C: float | None = None,
        seed: int | None = None,
        tau_s: float | None = None,
        T_set_max_C: float | None = None,
        noise_sigma_K: float | None = None,
        correlation_time_s: float = 5.0,
        max_step_s: float | None = None,
        method: str = "RK45",
    ) -> None:
        self.T_C: float = float(cfg.to_celsius(cfg.T_AMBIENT)) if T0_C is None else T0_C
        self.t_s: float = 0.0
        self.tau_s: float = float(cfg.to_seconds(cfg.TAU)) if tau_s is None else tau_s
        self.T_set_max_C: float = (
            float(cfg.to_celsius(cfg.T_SET_MAX)) if T_set_max_C is None else T_set_max_C
        )
        self.sigma: float = (
            float(cfg.SYSTEM_NOISE_SIGMA.to("delta_degC").magnitude)
            if noise_sigma_K is None
            else noise_sigma_K
        )
        self.correlation_time_s = correlation_time_s
        self.max_step_s: float = (
            float(cfg.to_seconds(cfg.DT_MAX)) if max_step_s is None else max_step_s
        )
        self.method = method
        self._rng = np.random.default_rng(seed)

    def step(self, dt_s: float, u: float) -> ThermalState:
        """
        Сделать один шаг длительностью dt_s при постоянном
        управлении u ∈ [0; 1]. Возвращает обновлённое состояние.
        """
        if dt_s <= 0:
            return ThermalState(t_s=self.t_s, T_C=self.T_C)

        # На малых шагах используем прямой Эйлер с шумом — это быстрее,
        # чем поднимать solve_ivp каждый шаг. Метод выбран потому, что
        # вне фазы интенсивного управления тепловая модель почти
        # линейна, а scipy.solve_ivp в каждом шаге simpy — дорогой
        # overhead.
        n_sub = max(int(np.ceil(dt_s / self.max_step_s)), 1)
        sub_dt = dt_s / n_sub
        u_clip = float(np.clip(u, 0.0, 1.0))

        for _ in range(n_sub):
            noise = float(self._rng.standard_normal()) * self.sigma * np.sqrt(sub_dt / self.tau_s)
            drive = (u_clip * self.T_set_max_C - self.T_C) / self.tau_s
            self.T_C += drive * sub_dt + noise

        self.t_s += dt_s
        return ThermalState(t_s=self.t_s, T_C=self.T_C)

    def run_to(self, t_target_s: float, u_fn: Callable[[float], float]) -> ThermalSimResult:
        """
        Проинтегрировать через scipy.solve_ivp от текущего t до
        t_target_s. Используется для разовых длинных участков, где
        важна точность (например, оценка переходной характеристики).
        """
        result = _simulate_via_closure(
            t0_s=self.t_s,
            t1_s=t_target_s,
            T0_C=self.T_C,
            u_fn=u_fn,
            tau_s=self.tau_s,
            T_set_max_C=self.T_set_max_C,
            noise_fn=lambda t: float(self._rng.standard_normal()) * self.sigma,
            max_step_s=self.max_step_s,
            method=self.method,
        )
        if result.success and len(result.T_C) > 0:
            self.t_s = float(result.t_s[-1])
            self.T_C = float(result.T_C[-1])
        return result


__all__ = [
    "ThermalState",
    "ThermalSimResult",
    "ThermalIntegrator",
    "simulate_segment",
    "make_coloured_noise",
]
