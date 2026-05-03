"""
sim.control_loop — контур управления температурой через python-control.

Что делает модуль:

1. Описывает термокамеру как линейный объект 1-го порядка с
   передаточной функцией:

                K
       G(s) = ─────
              τ·s + 1

   где K = T_set_max (нормированный коэффициент усиления, °C/единица
   управления) и τ — постоянная времени.

2. Реализует дискретный PID-регулятор и предоставляет анализ контура:
   шаг-ответ, Bode/Nyquist, оценка устойчивости — всё через
   python-control. Эти диаграммы пойдут в главу 2 ПЗ
   («Теоретическая часть») и в презентацию защиты.

3. Даёт удобный API контроллера для использования в scenario_runner:
   `pid.update(measured, dt) -> control` без знаний об устройстве
   объекта.

Зависимости: numpy, control (python-control).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import control as ct  # python-control package
    HAS_CONTROL = True
except ImportError:  # pragma: no cover
    HAS_CONTROL = False
    ct = None  # type: ignore[assignment]

from . import config as cfg


# ----------------------------------------------------------------------
# Передаточная функция объекта (термокамеры)
# ----------------------------------------------------------------------


def plant_transfer_function(
    *,
    tau_s: float | None = None,
    K_C: float | None = None,
):
    """Вернуть передаточную функцию объекта G(s) = K / (τs + 1) как
    control.TransferFunction. Используется для Bode/Nyquist/step.
    """
    if not HAS_CONTROL:
        raise RuntimeError("python-control not installed; pip install control")
    tau = float(cfg.to_seconds(cfg.TAU)) if tau_s is None else tau_s
    K = float(cfg.to_celsius(cfg.T_SET_MAX)) if K_C is None else K_C
    return ct.tf([K], [tau, 1.0])


def closed_loop_with_pid(
    *,
    Kp: float | None = None,
    Ki: float | None = None,
    Kd: float | None = None,
    tau_s: float | None = None,
    K_C: float | None = None,
):
    """Замкнутый контур с PID-регулятором — для расчёта step-ответа и
    оценки устойчивости.

    Возвращает TransferFunction замкнутой системы T_out(s) / T_set(s).
    """
    if not HAS_CONTROL:
        raise RuntimeError("python-control not installed; pip install control")
    Kp = cfg.PID_KP if Kp is None else Kp
    Ki = cfg.PID_KI if Ki is None else Ki
    Kd = cfg.PID_KD if Kd is None else Kd

    plant = plant_transfer_function(tau_s=tau_s, K_C=K_C)

    # PID: C(s) = Kp + Ki/s + Kd·s. Для чисто-D добавляем фильтрацию
    # (tau_d), чтобы избежать алгебраической петли при дискретизации.
    s = ct.tf([1, 0], [1])
    if Kd > 0:
        # с фильтром производной N=10 (стандартная практика)
        N = 10.0
        Ds = Kd * N * s / (s + N)
        C = Kp + Ki / s + Ds
    else:
        C = Kp + Ki / s

    open_loop = C * plant
    return ct.feedback(open_loop, 1)


# ----------------------------------------------------------------------
# Дискретный PID-регулятор (для прямого использования в simpy)
# ----------------------------------------------------------------------


@dataclass
class PID:
    """Минималистичный дискретный PID-регулятор с anti-windup и
    низкочастотной фильтрацией производной.

    Выход нормирован в [out_min; out_max]. Для нашего стенда
    out ∈ [0; 1] = скважность ШИМ нагревателя.
    """

    Kp: float = cfg.PID_KP
    Ki: float = cfg.PID_KI
    Kd: float = cfg.PID_KD
    out_min: float = cfg.PID_OUTPUT_MIN
    out_max: float = cfg.PID_OUTPUT_MAX

    # Внутреннее состояние
    _integral: float = 0.0
    _prev_error: float = 0.0
    _initialised: bool = False

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._initialised = False

    def update(self, setpoint: float, measured: float, dt_s: float) -> float:
        """Один шаг PID. Возвращает управляющий сигнал в [out_min; out_max]."""
        if dt_s <= 0:
            return float(np.clip(self.Kp * (setpoint - measured), self.out_min, self.out_max))

        error = setpoint - measured

        # P
        P = self.Kp * error

        # I с anti-windup (clamping)
        # Накопление в потенциал; финальный clamp на выходе сделает свою работу.
        self._integral += error * dt_s
        I = self.Ki * self._integral

        # D с инициализацией для избегания «удара» на первом шаге
        if not self._initialised:
            D = 0.0
            self._initialised = True
        else:
            D = self.Kd * (error - self._prev_error) / dt_s

        self._prev_error = error
        u_unclipped = P + I + D
        u = float(np.clip(u_unclipped, self.out_min, self.out_max))

        # Anti-windup: если выход насыщен, и интеграл «толкает» в ту же
        # сторону, откатываем шаг интегратора назад. Простая
        # back-calculation схема.
        if (u_unclipped > self.out_max and error > 0) or (
            u_unclipped < self.out_min and error < 0
        ):
            # «Отменить» накопление этого шага
            self._integral -= error * dt_s

        return u


# ----------------------------------------------------------------------
# Анализ устойчивости и переходной характеристики
# ----------------------------------------------------------------------


def step_response(
    *,
    Kp: float | None = None,
    Ki: float | None = None,
    Kd: float | None = None,
    duration_s: float = 600.0,
    n_points: int = 600,
):
    """Step-response замкнутой системы T_set → T_out.
    Возвращает (t_array, y_array) — массивы времени (с) и выхода (°C).

    Используется в notebook'ах главы 2 для иллюстрации работы PID.
    """
    if not HAS_CONTROL:
        raise RuntimeError("python-control not installed; pip install control")
    sys_cl = closed_loop_with_pid(Kp=Kp, Ki=Ki, Kd=Kd)
    t = np.linspace(0.0, duration_s, n_points)
    t_out, y_out = ct.step_response(sys_cl, T=t)
    return np.asarray(t_out), np.asarray(y_out)


def bode_data(
    *,
    Kp: float | None = None,
    Ki: float | None = None,
    Kd: float | None = None,
    omega_min: float = 1e-4,
    omega_max: float = 1e2,
    n_points: int = 500,
):
    """Магнитуда (дБ), фаза (°) и частоты (рад/с) для Bode-диаграммы
    разомкнутой системы C(s)·G(s).

    Отдаём массивы — рисует пользователь (matplotlib/plotly), чтобы
    модуль не тащил за собой viz-зависимости.
    """
    if not HAS_CONTROL:
        raise RuntimeError("python-control not installed; pip install control")
    Kp = cfg.PID_KP if Kp is None else Kp
    Ki = cfg.PID_KI if Ki is None else Ki
    Kd = cfg.PID_KD if Kd is None else Kd
    plant = plant_transfer_function()

    s = ct.tf([1, 0], [1])
    C = Kp + Ki / s + (Kd * 10.0 * s / (s + 10.0) if Kd > 0 else 0)
    open_loop = C * plant

    omega = np.logspace(np.log10(omega_min), np.log10(omega_max), n_points)
    mag, phase, omega_out = ct.bode(open_loop, omega=omega, plot=False)
    mag_db = 20.0 * np.log10(np.asarray(mag))
    phase_deg = np.rad2deg(np.asarray(phase))
    return np.asarray(omega_out), mag_db, phase_deg


def stability_margins(
    *,
    Kp: float | None = None,
    Ki: float | None = None,
    Kd: float | None = None,
) -> dict[str, float]:
    """Запасы устойчивости разомкнутой системы C·G:
    gain_margin_dB, phase_margin_deg, частоты пересечения.

    Используется как численный показатель в главе 2 ПЗ.
    """
    if not HAS_CONTROL:
        raise RuntimeError("python-control not installed; pip install control")
    Kp = cfg.PID_KP if Kp is None else Kp
    Ki = cfg.PID_KI if Ki is None else Ki
    Kd = cfg.PID_KD if Kd is None else Kd
    plant = plant_transfer_function()

    s = ct.tf([1, 0], [1])
    C = Kp + Ki / s + (Kd * 10.0 * s / (s + 10.0) if Kd > 0 else 0)
    open_loop = C * plant

    gm, pm, wcg, wcp = ct.margin(open_loop)
    return {
        "gain_margin_dB": float(20.0 * np.log10(gm)) if gm and gm > 0 else float("inf"),
        "phase_margin_deg": float(pm) if pm else 0.0,
        "wcg_rad_per_s": float(wcg) if wcg else 0.0,
        "wcp_rad_per_s": float(wcp) if wcp else 0.0,
    }


__all__ = [
    "PID",
    "plant_transfer_function",
    "closed_loop_with_pid",
    "step_response",
    "bode_data",
    "stability_margins",
    "HAS_CONTROL",
]
