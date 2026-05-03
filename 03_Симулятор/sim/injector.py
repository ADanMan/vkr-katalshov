"""
sim.injector — инъектор нарушений для проверки FLV-метода.

Каждая инъекция — это набор хуков `ScenarioHooks`, который меняет
поведение `ScenarioRunner` так, чтобы воспроизвести ровно один код
нарушения из каталога Phase 2 (`violations_catalog.md`):

   SEQ_MISS    — пропуск обязательного шага FSM
   SEQ_ORDER   — нарушение порядка переходов
   TIME_UNDER  — недостаточная длительность HOLD
   TIME_OVER   — превышение допустимой длительности HOLD
   PRED_FAIL   — переход HOLD→MEASURE при невыполненном гарде
   N_TOO_LOW   — недобор отсчётов в MEASURE
   RANGE_MISM  — параметр T_set вне допустимого диапазона

Пара (имя_кода, build_hooks_callable) экспортируется через
INJECTIONS — это используется CLI и автоматическим перебором сценариев
в Phase 5.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from . import config as cfg
from .scenario_runner import ScenarioHooks, ScenarioParams


# ----------------------------------------------------------------------
# Типы для injection-функций
# ----------------------------------------------------------------------

InjectionBuilder = Callable[[ScenarioParams], ScenarioHooks]


@dataclass
class InjectionSpec:
    """Описание одной инъекции."""

    code: str                                       # SEQ_MISS, ...
    description: str                                # человеко-читаемое описание
    expected_violation: str                         # код нарушения, который должен поднять FLV
    build_hooks: InjectionBuilder                   # функция, генерирующая хуки


# ----------------------------------------------------------------------
# Builders для каждой инъекции
# ----------------------------------------------------------------------


def _no_injection(params: ScenarioParams) -> ScenarioHooks:
    """Эталонный (correct) сценарий — без модификаций."""
    return ScenarioHooks()


def _seq_miss_drop_hold(params: ScenarioParams) -> ScenarioHooks:
    """SEQ_MISS — пропускаем обязательное состояние HOLD."""
    return ScenarioHooks(skip_states=("HOLD",))


def _seq_order_swap(params: ScenarioParams) -> ScenarioHooks:
    """SEQ_ORDER — MEASURE раньше HOLD.

    Замечание: при таком порядке HOLD после MEASURE не поднимет
    нарушение TIME_UNDER (там ещё нет требования по выдержке), но
    sequence-matcher должен поднять SEQ_ORDER, потому что в DSL
    переход t3_hold_to_measure определён только в направлении
    HOLD → MEASURE.
    """
    return ScenarioHooks(
        custom_state_sequence=("INIT", "HEAT", "MEASURE", "HOLD", "POST"),
    )


def _time_under_force_30s(params: ScenarioParams) -> ScenarioHooks:
    """TIME_UNDER — принудительно завершаем HOLD через 30 c
    (целевой минимум — 300 c)."""
    return ScenarioHooks(force_t_hold_s=30.0)


def _time_over_force_700s(params: ScenarioParams) -> ScenarioHooks:
    """TIME_OVER — продлеваем HOLD до 700 c (целевой максимум — 600 c)."""
    return ScenarioHooks(force_t_hold_s=700.0)


def _pred_fail_dTdt_violation(params: ScenarioParams) -> ScenarioHooks:
    """PRED_FAIL — выходим из HOLD при |dT/dt| = 0.045 °C/s
    (целевой порог — 0.02). Длительность HOLD укорачиваем до
    100 c, чтобы быть уверенным, что переход произойдёт раньше
    стабилизации."""
    return ScenarioHooks(
        force_t_hold_s=100.0,
        force_dTdt_at_exit=0.045,
    )


def _n_too_low_5_samples(params: ScenarioParams) -> ScenarioHooks:
    """N_TOO_LOW — собираем только 5 отсчётов в MEASURE
    (целевой минимум — 20)."""
    return ScenarioHooks(force_n_collected=5)


def _range_mism_700C(params: ScenarioParams) -> ScenarioHooks:
    """RANGE_MISM — устанавливаем T_set = 700 °C (предел камеры — 250)."""
    return ScenarioHooks(override_T_set_C=700.0)


# ----------------------------------------------------------------------
# Реестр всех инъекций
# ----------------------------------------------------------------------

INJECTIONS: dict[str, InjectionSpec] = {
    "NONE": InjectionSpec(
        code="NONE",
        description="Эталонный прогон без нарушений",
        expected_violation="(none)",
        build_hooks=_no_injection,
    ),
    "SEQ_MISS": InjectionSpec(
        code="SEQ_MISS",
        description="Пропуск состояния HOLD",
        expected_violation="SEQ_MISS",
        build_hooks=_seq_miss_drop_hold,
    ),
    "SEQ_ORDER": InjectionSpec(
        code="SEQ_ORDER",
        description="MEASURE раньше HOLD",
        expected_violation="SEQ_ORDER",
        build_hooks=_seq_order_swap,
    ),
    "TIME_UNDER": InjectionSpec(
        code="TIME_UNDER",
        description="HOLD длительностью 30 c вместо ≥ 300 c",
        expected_violation="TIME_UNDER",
        build_hooks=_time_under_force_30s,
    ),
    "TIME_OVER": InjectionSpec(
        code="TIME_OVER",
        description="HOLD длительностью 700 c вместо ≤ 600 c",
        expected_violation="TIME_OVER",
        build_hooks=_time_over_force_700s,
    ),
    "PRED_FAIL": InjectionSpec(
        code="PRED_FAIL",
        description="Переход HOLD→MEASURE при |dT/dt|=0.045 °C/s (порог 0.02)",
        expected_violation="PRED_FAIL",
        build_hooks=_pred_fail_dTdt_violation,
    ),
    "N_TOO_LOW": InjectionSpec(
        code="N_TOO_LOW",
        description="5 отсчётов в MEASURE вместо ≥ 20",
        expected_violation="N_TOO_LOW",
        build_hooks=_n_too_low_5_samples,
    ),
    "RANGE_MISM": InjectionSpec(
        code="RANGE_MISM",
        description="T_set = 700 °C при пределе камеры 250 °C",
        expected_violation="RANGE_MISM",
        build_hooks=_range_mism_700C,
    ),
}


def list_injections() -> list[str]:
    """Список доступных кодов инъекций."""
    return list(INJECTIONS.keys())


def get_injection(code: str) -> InjectionSpec:
    """Получить InjectionSpec по коду; падает, если кода нет."""
    if code not in INJECTIONS:
        raise KeyError(
            f"Unknown injection code: {code!r}. "
            f"Available: {sorted(INJECTIONS.keys())}"
        )
    return INJECTIONS[code]


__all__ = ["InjectionSpec", "INJECTIONS", "list_injections", "get_injection"]
