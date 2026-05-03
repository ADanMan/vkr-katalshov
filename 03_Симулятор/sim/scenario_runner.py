"""
sim.scenario_runner — исполнитель FSM-сценария на основе simpy.

Связывает физический слой (thermal_model + sensor + control_loop)
с формальной FSM из DSL Phase 2 в виде event-driven процессов.

Идея:
    Каждое состояние FSM (INIT, HEAT, HOLD, MEASURE, POST) — это
    отдельная simpy-процедура (generator). Внутри неё:
      • запрашиваются ресурсы (физическая модель шага);
      • ждутся timeout / условия (env.timeout, env.event);
      • при срабатывании условий переходов — yield в следующее
        состояние через диспетчер.
    Логгер событий получает уведомления на каждом существенном
    переходе/отсчёте.

Это нативный для дискретно-событийных систем подход, удобнее
ручного while-цикла и ближе к реальному поведению LabVIEW QSM.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import simpy

from . import config as cfg
from .control_loop import PID
from .sensor import MeasurementChain, SensorReading
from .thermal_model import ThermalIntegrator


# ----------------------------------------------------------------------
# Типы для логгера событий
# ----------------------------------------------------------------------

# Подпись логгера: (event_name, state, params, signals, ts) -> None
EventSink = Callable[[str, str, dict[str, Any], dict[str, Any], float], None]


def _noop_sink(*args: Any, **kwargs: Any) -> None:  # pragma: no cover
    """Пустой логгер для тестов и dry-run."""
    return None


# ----------------------------------------------------------------------
# Конфиг прогона (то, что приходит из YAML-сценария)
# ----------------------------------------------------------------------


@dataclass
class ScenarioParams:
    """Параметры одного прогона сценария.

    Параметры по умолчанию — из config (т.е. эталонная методика S1).
    Для инъекций нарушений — переопределяются в injector.py.
    """

    T_set_C: float = field(default_factory=lambda: cfg.to_celsius(cfg.T_SET_DEFAULT))
    T_min_C: float = field(default_factory=lambda: cfg.to_celsius(cfg.T_MIN))
    delta_stable_Cs: float = field(
        default_factory=lambda: cfg.DELTA_STABLE.to("delta_degC / s").magnitude
    )
    t_hold_min_s: float = field(default_factory=lambda: cfg.to_seconds(cfg.T_HOLD_MIN))
    t_hold_max_s: float = field(default_factory=lambda: cfg.to_seconds(cfg.T_HOLD_MAX))
    n_min: int = cfg.N_MIN
    f_meas_Hz: float = field(default_factory=lambda: cfg.F_MEAS.to("Hz").magnitude)
    f_sample_Hz: float = field(default_factory=lambda: cfg.F_SAMPLE.to("Hz").magnitude)

    # Лимит на длительность всего прогона (защита от бесконечного цикла)
    timeout_s: float = field(default_factory=lambda: cfg.to_seconds(cfg.RUN_TIMEOUT))

    # Шаг физической интеграции (одного «такта» simpy)
    sim_step_s: float = 0.1


# ----------------------------------------------------------------------
# Хуки для инъектора нарушений
# ----------------------------------------------------------------------


@dataclass
class ScenarioHooks:
    """Точки расширения, через которые injector.py может изменить
    штатное поведение runner'а. По умолчанию — все None (штатный
    прогон).

    Каждый хук получает текущий ScenarioRunner, может изменить его
    параметры или прервать состояние. См. injector.py.
    """

    # Если задан — runner пропускает указанные состояния (SEQ_MISS).
    skip_states: tuple[str, ...] = ()

    # Если задан — runner идёт в этом порядке вместо стандартного
    # (для SEQ_ORDER).
    custom_state_sequence: tuple[str, ...] = ()

    # Принудительно завершить HOLD после этого времени, даже если
    # стабилизация не достигнута (для TIME_UNDER) или продлить
    # (для TIME_OVER). Если None — штатно.
    force_t_hold_s: float | None = None

    # Принудительно завершить HOLD при этом dT/dt, даже если он
    # выше delta_stable (для PRED_FAIL).
    force_dTdt_at_exit: float | None = None

    # Принудительно остановить MEASURE после N отсчётов вместо n_min
    # (для N_TOO_LOW).
    force_n_collected: int | None = None

    # Override стартового T_set для проверки RANGE_MISM.
    override_T_set_C: float | None = None


# ----------------------------------------------------------------------
# Основной runner
# ----------------------------------------------------------------------


@dataclass
class RunSummary:
    """Сводка завершённого прогона."""

    run_id: str
    t_total_s: float
    end_state: str            # POST / TIMEOUT / ABORTED
    n_measurements: int
    mean_T_C: float | None
    measurements_C: list[float] = field(default_factory=list)


class ScenarioRunner:
    """Исполнитель FSM-сценария на simpy.

    Использование:
        runner = ScenarioRunner(
            run_id="S1-20260503-001",
            params=ScenarioParams(),
            seed=42,
            sink=event_logger.write,
        )
        summary = runner.run()
    """

    DEFAULT_SEQUENCE: tuple[str, ...] = ("INIT", "HEAT", "HOLD", "MEASURE", "POST")

    def __init__(
        self,
        *,
        run_id: str,
        params: ScenarioParams | None = None,
        hooks: ScenarioHooks | None = None,
        seed: int | None = None,
        sink: EventSink = _noop_sink,
    ) -> None:
        self.run_id = run_id
        self.params = params or ScenarioParams()
        self.hooks = hooks or ScenarioHooks()
        self.seed = seed
        self.sink = sink

        # Применить override T_set, если задан хуком
        if self.hooks.override_T_set_C is not None:
            self.params.T_set_C = self.hooks.override_T_set_C

        # Физический слой
        self.env = simpy.Environment()
        self.thermal = ThermalIntegrator(seed=seed)
        self.chain = MeasurementChain(seed=(seed + 1) if seed is not None else None)
        self.pid = PID()

        # История измерений
        self._measurements_C: list[float] = []
        self._last_reading: SensorReading | None = None
        self._dT_dt_recent: float = 0.0
        self._end_state: str = "PENDING"

        # Для расчёта dT/dt — храним предыдущий отсчёт
        self._prev_T_indicated: float | None = None
        self._prev_t_s: float | None = None

    # ---------- внутренние помощники ----------

    def _emit(
        self,
        event: str,
        state: str,
        *,
        params: dict[str, Any] | None = None,
        signals: dict[str, Any] | None = None,
    ) -> None:
        self.sink(
            event,
            state,
            params or {},
            signals or {},
            float(self.env.now),
        )

    def _physics_step(self, state_name: str) -> SensorReading:
        """Один шаг физики: PID → thermal → sensor."""
        dt = self.params.sim_step_s
        # Управляющий сигнал PID на основе предыдущего показания
        T_meas = (
            self._last_reading.T_indicated_C
            if self._last_reading is not None
            else cfg.to_celsius(cfg.T_AMBIENT)
        )
        u = self.pid.update(self.params.T_set_C, T_meas, dt)
        # Шаг тепловой модели
        thermal_state = self.thermal.step(dt, u)
        # Отсчёт сенсора
        reading = self.chain.read(
            t_s=thermal_state.t_s,
            T_object_C=thermal_state.T_C,
            dt_s=dt,
        )
        # Обновить производную dT/dt
        if self._prev_T_indicated is not None and self._prev_t_s is not None:
            d_t = reading.t_s - self._prev_t_s
            if d_t > 0:
                self._dT_dt_recent = (reading.T_indicated_C - self._prev_T_indicated) / d_t
        self._prev_T_indicated = reading.T_indicated_C
        self._prev_t_s = reading.t_s
        self._last_reading = reading
        return reading

    def _maybe_skip(self, state: str) -> bool:
        return state in self.hooks.skip_states

    def _state_sequence(self) -> tuple[str, ...]:
        if self.hooks.custom_state_sequence:
            return self.hooks.custom_state_sequence
        return self.DEFAULT_SEQUENCE

    # ---------- состояния FSM как simpy-процессы ----------

    def _state_init(self) -> Generator[simpy.events.Event, None, None]:
        self._emit("INIT_START", "INIT", signals={"T": self._last_reading.T_indicated_C if self._last_reading else cfg.to_celsius(cfg.T_AMBIENT)})
        yield self.env.timeout(0.5)
        self._emit("INIT_END", "INIT", params={"device_ready": True})

    def _state_heat(self) -> Generator[simpy.events.Event, None, None]:
        self._emit("HEAT_START", "HEAT")
        last_sample_t = 0.0
        while True:
            r = self._physics_step("HEAT")
            # Sample-event с заданной частотой
            if r.t_s - last_sample_t >= 1.0 / self.params.f_sample_Hz:
                self._emit("SAMPLE", "HEAT", signals={"T": r.T_indicated_C})
                last_sample_t = r.t_s
            # Условие выхода: T >= T_min
            if r.T_indicated_C >= self.params.T_min_C:
                self._emit("HEAT_END", "HEAT", params={"T_reached": r.T_indicated_C})
                break
            yield self.env.timeout(self.params.sim_step_s)

    def _state_hold(self) -> Generator[simpy.events.Event, None, None]:
        self._emit("HOLD_START", "HOLD")
        t_enter = float(self.env.now)
        last_sample_t = 0.0
        # При штатном поведении ждём (стабильность ∧ t ≥ t_hold_min) ИЛИ t ≥ t_hold_max
        # Хуки могут принудительно сократить (TIME_UNDER) или продлить (TIME_OVER)
        force_t = self.hooks.force_t_hold_s
        force_dTdt = self.hooks.force_dTdt_at_exit
        while True:
            r = self._physics_step("HOLD")
            t_held = r.t_s - t_enter
            if r.t_s - last_sample_t >= 1.0 / self.params.f_sample_Hz:
                self._emit("SAMPLE", "HOLD", signals={"T": r.T_indicated_C, "dT_dt": self._dT_dt_recent})
                last_sample_t = r.t_s

            # Принудительный выход (инъекции нарушений)
            if force_t is not None and t_held >= force_t:
                exit_dTdt = force_dTdt if force_dTdt is not None else self._dT_dt_recent
                self._emit(
                    "HOLD_END", "HOLD",
                    params={"t_hold": t_held, "dT_dt": exit_dTdt},
                )
                # Подменить значение dT_dt в показании, если потребовал хук
                if force_dTdt is not None:
                    self._dT_dt_recent = force_dTdt
                break

            # Штатные условия выхода
            stable = abs(self._dT_dt_recent) <= self.params.delta_stable_Cs
            if stable and t_held >= self.params.t_hold_min_s:
                self._emit(
                    "HOLD_END", "HOLD",
                    params={"t_hold": t_held, "dT_dt": self._dT_dt_recent},
                )
                break
            if t_held >= self.params.t_hold_max_s:
                # Штатно достигли максимального HOLD; идём дальше
                self._emit(
                    "HOLD_END", "HOLD",
                    params={"t_hold": t_held, "dT_dt": self._dT_dt_recent},
                )
                break
            yield self.env.timeout(self.params.sim_step_s)

    def _state_measure(self) -> Generator[simpy.events.Event, None, None]:
        self._emit("MEAS_START", "MEASURE")
        target_n = self.hooks.force_n_collected if self.hooks.force_n_collected is not None else self.params.n_min
        meas_period = 1.0 / self.params.f_meas_Hz
        t_last_meas = float(self.env.now) - meas_period  # сразу же сделать первое измерение
        while len(self._measurements_C) < target_n:
            r = self._physics_step("MEASURE")
            if r.t_s - t_last_meas >= meas_period:
                self._measurements_C.append(r.T_indicated_C)
                t_last_meas = r.t_s
                self._emit(
                    "MEAS_TICK", "MEASURE",
                    params={"n": len(self._measurements_C)},
                    signals={"T": r.T_indicated_C},
                )
            yield self.env.timeout(self.params.sim_step_s)
        self._emit(
            "MEAS_END", "MEASURE",
            params={"N_collected": len(self._measurements_C)},
        )

    def _state_post(self) -> Generator[simpy.events.Event, None, None]:
        mean_T = float(np.mean(self._measurements_C)) if self._measurements_C else None
        self._emit("POST_START", "POST", params={"mean_T_C": mean_T})
        yield self.env.timeout(0.5)
        self._emit("POST_END", "POST")

    # ---------- общий driver ----------

    def _driver(self) -> Generator[simpy.events.Event, None, None]:
        self._emit(
            "RUN_START", "INIT",
            params={
                "T_set": self.params.T_set_C,
                "t_hold_min": self.params.t_hold_min_s,
                "N_min": self.params.n_min,
            },
            signals={"T": cfg.to_celsius(cfg.T_AMBIENT)},
        )

        for state in self._state_sequence():
            if self._maybe_skip(state):
                continue
            if state == "INIT":
                yield self.env.process(self._state_init())
            elif state == "HEAT":
                yield self.env.process(self._state_heat())
            elif state == "HOLD":
                yield self.env.process(self._state_hold())
            elif state == "MEASURE":
                yield self.env.process(self._state_measure())
            elif state == "POST":
                yield self.env.process(self._state_post())
            else:
                raise ValueError(f"Unknown state in sequence: {state!r}")

        self._end_state = "POST"
        self._emit(
            "RUN_END", "POST",
            params={
                "run_status": "completed",
                "n_measurements": len(self._measurements_C),
            },
        )

    # ---------- публичный API ----------

    def run(self) -> RunSummary:
        """Запустить весь сценарий и вернуть сводку."""
        self.env.process(self._driver())
        try:
            self.env.run(until=self.params.timeout_s)
        except simpy.exceptions.SimPyException as e:
            self._end_state = "ABORTED"
            self._emit("ERROR", self._end_state, params={"reason": str(e)})

        # Если ушли по timeout
        if self._end_state == "PENDING":
            self._end_state = "TIMEOUT"
            self._emit("ERROR", self._end_state, params={"reason": "timeout"})
            self._emit("RUN_END", self._end_state, params={"run_status": "aborted"})

        mean_T = (
            float(np.mean(self._measurements_C))
            if self._measurements_C
            else None
        )
        return RunSummary(
            run_id=self.run_id,
            t_total_s=float(self.env.now),
            end_state=self._end_state,
            n_measurements=len(self._measurements_C),
            mean_T_C=mean_T,
            measurements_C=list(self._measurements_C),
        )


__all__ = [
    "ScenarioParams",
    "ScenarioHooks",
    "ScenarioRunner",
    "RunSummary",
    "EventSink",
]
