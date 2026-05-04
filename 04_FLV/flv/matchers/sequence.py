"""
flv.matchers.sequence — детерминированный матчер последовательности.

Проверяет два условия по `formal_model.md` §4.1 (структурное
условие приёма):

1. Все обязательные шаги из `checks[kind=sequence].must_include`
   присутствуют в трассе. Нарушение — SEQ_MISS.
2. Порядок переходов состояний в трассе допустим по `transitions`
   из DSL. Нарушение — SEQ_ORDER.

Сложность алгоритма O(n) по числу событий.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..core import Spec, Trace
from ..verdict import Violation, ViolationLocation
from .base import BaseMatcher


class SequenceMatcher(BaseMatcher):
    """SEQ_MISS, SEQ_ORDER."""

    name = "sequence"

    def match(self, spec: Spec, trace: Trace) -> Iterable[Violation]:
        # Восстановим фактическую последовательность ВХОЖДЕНИЙ в состояния
        # как уникальную upper-list по первому появлению.
        observed_states: list[str] = []
        first_event_in_state: dict[str, ViolationLocation] = {}
        for ev in trace.events:
            s = ev.state
            if s and (not observed_states or observed_states[-1] != s):
                if s not in first_event_in_state:
                    first_event_in_state[s] = ViolationLocation(
                        event_seq=ev.seq, ts_rel_s=ev.t_rel_s, state=s
                    )
                if s not in observed_states:
                    observed_states.append(s)
        observed_set = set(observed_states)

        # ── 1) SEQ_MISS — обязательные шаги, которых нет ───────────────
        required: list[str] = []
        check_id = ""
        for c in spec.checks:
            if c.kind == "sequence":
                must = c.payload.get("must_include") or []
                if isinstance(must, list):
                    required.extend(str(x) for x in must)
                check_id = c.id
                break
        for state in required:
            if state not in observed_set:
                yield self._make_violation(
                    spec,
                    code="SEQ_MISS",
                    state=state,
                    expected={"required_states": required},
                    actual={"observed_states": observed_states},
                    location=None,
                    spec_ref=check_id,
                )

        # ── 2) SEQ_ORDER — переходы вне разрешённой пары from→to ──────
        # Соберём множество допустимых переходов
        allowed: set[tuple[str, str]] = {
            (t.from_state, t.to_state) for t in spec.transitions
        }
        # Будем смотреть фактические переходы между смежными
        # ВХОЖДЕНИЯМИ в состояния (по trace).
        prev_state: str | None = None
        prev_event = None
        for ev in trace.events:
            s = ev.state
            if not s:
                continue
            if prev_state is None:
                prev_state, prev_event = s, ev
                continue
            if s != prev_state:
                pair = (prev_state, s)
                if allowed and pair not in allowed:
                    yield self._make_violation(
                        spec,
                        code="SEQ_ORDER",
                        state=s,
                        expected={
                            "expected_transitions": sorted(
                                f"{a}->{b}" for a, b in allowed
                            )
                        },
                        actual={"observed_transition": f"{prev_state}->{s}"},
                        location=ViolationLocation(
                            event_seq=ev.seq, ts_rel_s=ev.t_rel_s, state=s
                        ),
                        spec_ref="",
                    )
                prev_state, prev_event = s, ev


__all__ = ["SequenceMatcher"]
