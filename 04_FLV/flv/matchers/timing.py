"""
flv.matchers.timing — детерминированный матчер длительностей состояний.

Проверяет временное условие приёма (`formal_model.md` §4.2):
для каждого пребывания в состоянии s длительностью d должно быть
выполнено `t_min ≤ d ≤ t_max`. Источники границ:

* `transitions[].time.{min,max}` — на исходящем переходе из s.
* `checks[kind=timing].{state, min_duration, max_duration}` —
  доп. проверка по состоянию.

Алгоритм:

1. По event-list восстанавливается список «эпох» — пар
   (state, t_enter, t_exit) на основе фактических смен `state`.
2. Для каждой эпохи проверяется t_min/t_max.
3. Эмитятся TIME_UNDER (severity critical) и TIME_OVER (warning).

Также поддерживается явное событие `<STATE>_END` с полем
`params.t_hold` (как пишет 03_Симулятор/scenario_runner) — оно
имеет приоритет над автоматически вычисленной длительностью, что
позволяет инжектору задавать TIME_UNDER/OVER даже если время по
trace получилось нормальным.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..core import Event, Spec, Trace
from ..verdict import Violation, ViolationLocation
from .base import BaseMatcher


class TimingMatcher(BaseMatcher):
    """TIME_UNDER, TIME_OVER."""

    name = "timing"

    def match(self, spec: Spec, trace: Trace) -> Iterable[Violation]:
        # ── 1) Собираем эпохи (state, t_enter, t_exit, exit_event) ────
        epochs: list[tuple[str, float, float, Event]] = []
        if not trace.events:
            return
        cur_state: str | None = None
        t_enter: float = 0.0
        last_event: Event | None = None
        for ev in trace.events:
            s = ev.state
            if cur_state is None:
                cur_state = s
                t_enter = ev.t_rel_s
                last_event = ev
                continue
            if s != cur_state:
                # эпоха заканчивается на предыдущем событии
                epochs.append((cur_state, t_enter, ev.t_rel_s, ev))
                cur_state = s
                t_enter = ev.t_rel_s
            last_event = ev
        # последнюю эпоху до конца трассы
        if cur_state is not None and last_event is not None:
            epochs.append((cur_state, t_enter, last_event.t_rel_s, last_event))

        # Карты лимитов: по transitions (out-edge from состояния) и checks
        out_limits: dict[str, tuple[float | None, float | None, str]] = {}
        for t in spec.transitions:
            out_limits.setdefault(
                t.from_state, (t.time_min_s, t.time_max_s, t.id)
            )
        check_limits: dict[str, tuple[float | None, float | None, str]] = {}
        for c in spec.checks:
            if c.kind == "timing":
                state = c.payload.get("state")
                if state:
                    check_limits[str(state)] = (
                        c.payload.get("min_duration"),
                        c.payload.get("max_duration"),
                        c.id,
                    )

        # Также подхватываем явное t_hold из <STATE>_END.params.t_hold
        explicit_t_hold: dict[str, tuple[float, Event]] = {}
        for ev in trace.events:
            if ev.name.endswith("_END"):
                state_name = ev.name[: -len("_END")]
                t_hold = ev.params.get("t_hold")
                if isinstance(t_hold, (int, float)):
                    explicit_t_hold.setdefault(state_name, (float(t_hold), ev))

        # ── 2) Проверяем каждую эпоху ─────────────────────────────────
        for state, t_enter_v, t_exit_v, exit_event in epochs:
            duration = t_exit_v - t_enter_v
            if state in explicit_t_hold:
                duration, exit_event = explicit_t_hold[state]

            # Берём чек по состоянию, если есть; иначе — limit с out-edge
            if state in check_limits:
                t_min, t_max, ref_id = check_limits[state]
            elif state in out_limits:
                t_min, t_max, ref_id = out_limits[state]
            else:
                continue

            location = ViolationLocation(
                event_seq=exit_event.seq,
                ts_rel_s=exit_event.t_rel_s,
                state=state,
            )

            if t_min is not None and duration < float(t_min):
                yield self._make_violation(
                    spec,
                    code="TIME_UNDER",
                    state=state,
                    expected={"min_duration_s": float(t_min)},
                    actual={"duration_s": float(duration)},
                    location=location,
                    spec_ref=ref_id,
                )
            if t_max is not None and duration > float(t_max):
                yield self._make_violation(
                    spec,
                    code="TIME_OVER",
                    state=state,
                    expected={"max_duration_s": float(t_max)},
                    actual={"duration_s": float(duration)},
                    location=location,
                    spec_ref=ref_id,
                )


__all__ = ["TimingMatcher"]
