"""
flv.matchers.predicate — детерминированный матчер предикатов.

Проверяет три кода нарушений из `violations_catalog.md`:

* PRED_FAIL  — гард-условие на переходе или
  `checks[kind=predicate].condition` не выполнено в момент перехода.
* RANGE_MISM — параметр процесса вне диапазона
  (`checks[kind=range]` или `parameters[].{min,max}`).
* N_TOO_LOW  — накопленное число отсчётов меньше требуемого.

Безопасный eval — через библиотеку `simpleeval` с whitelist на имена
переменных. Это закрывает security-требование (PEP 8 + Python rules
security.md): прямой `eval()` под произвольным DSL запрещён.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from simpleeval import EvalWithCompoundTypes, FunctionNotDefined, NameNotDefined

from ..core import Event, Spec, Trace
from ..verdict import Violation, ViolationLocation
from .base import BaseMatcher

logger = logging.getLogger(__name__)


def _abs(x: Any) -> Any:
    return abs(x)


class PredicateMatcher(BaseMatcher):
    """PRED_FAIL, RANGE_MISM, N_TOO_LOW."""

    name = "predicate"

    def match(self, spec: Spec, trace: Trace) -> Iterable[Violation]:
        # ── 1) Гарды на переходах ─────────────────────────────────────
        # Для каждого фактического перехода <STATE_A> → <STATE_B>
        # ищем transitions с from=A,to=B и проверяем guard.
        transitions_index: dict[tuple[str, str], list] = {}
        for t in spec.transitions:
            transitions_index.setdefault((t.from_state, t.to_state), []).append(t)

        prev_state: str | None = None
        prev_event: Event | None = None
        for ev in trace.events:
            s = ev.state
            if prev_state is None:
                prev_state, prev_event = s, ev
                continue
            if s != prev_state:
                # переход prev_state → s в момент ev
                for t in transitions_index.get((prev_state, s), []):
                    if t.guard:
                        ok, ctx = self._eval_predicate(
                            t.guard, ev, prev_event, spec
                        )
                        if not ok:
                            yield self._make_violation(
                                spec,
                                code="PRED_FAIL",
                                state=prev_state,
                                expected={"condition": t.guard},
                                actual=ctx,
                                location=ViolationLocation(
                                    event_seq=ev.seq,
                                    ts_rel_s=ev.t_rel_s,
                                    state=s,
                                ),
                                spec_ref=t.id,
                            )
                prev_state, prev_event = s, ev

        # ── 2) checks[kind=predicate / range] ─────────────────────────
        for c in spec.checks:
            if c.kind == "predicate":
                yield from self._check_predicate(c, spec, trace)
            elif c.kind == "range":
                yield from self._check_range(c, spec, trace)

    # ------------------------------------------------------------------
    # Внутренние помощники
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ctx(
        event: Event,
        prev_event: Event | None,
        spec: Spec,
    ) -> dict[str, Any]:
        """Собрать контекст переменных для simpleeval."""
        ctx: dict[str, Any] = {}
        # Параметры процесса по умолчанию
        for k, v in spec.parameters.items():
            if isinstance(v, dict):
                if "default" in v:
                    ctx[k] = v["default"]
            else:
                ctx[k] = v
        # Из текущего события
        if event is not None:
            ctx.update(event.params)
            ctx.update(event.signals)
        if prev_event is not None:
            for k, v in prev_event.params.items():
                ctx.setdefault(k, v)
        return ctx

    @staticmethod
    def _safe_eval(expr: str, ctx: dict[str, Any]) -> bool | None:
        """Безопасный eval с whitelist. Возвращает None, если
        невозможно вычислить (отсутствуют переменные/функции),
        иначе bool результат."""
        evaluator = EvalWithCompoundTypes(
            names=ctx,
            functions={"abs": _abs, "min": min, "max": max},
        )
        try:
            return bool(evaluator.eval(expr))
        except (NameNotDefined, FunctionNotDefined):
            logger.debug("predicate %r: не все переменные доступны в ctx", expr)
            return None
        except Exception as exc:  # pragma: no cover
            logger.warning("predicate %r не удалось вычислить: %s", expr, exc)
            return None

    def _eval_predicate(
        self,
        expr: str,
        event: Event,
        prev_event: Event | None,
        spec: Spec,
    ) -> tuple[bool, dict[str, Any]]:
        """Вернуть (ok, ctx) — ok=True если условие выполнено, ctx —
        снимок переменных для записи в Violation.actual."""
        ctx = self._build_ctx(event, prev_event, spec)
        result = self._safe_eval(expr, ctx)
        # Если не смогли вычислить — считаем нарушением (контракт:
        # отсутствие данных = недостоверный прогон).
        ok = bool(result) if result is not None else False
        # В Violation.actual кладём только релевантные имена
        # (которые упомянуты в expr) — иначе слишком шумно.
        snapshot = {k: ctx[k] for k in ctx if k in expr}
        return ok, snapshot

    def _check_predicate(self, check, spec: Spec, trace: Trace) -> Iterable[Violation]:
        """checks[kind=predicate]: оценивается на каждом релевантном
        событии. По умолчанию — на последнем событии трассы (как
        для N_collected ≥ N_min на POST_END)."""
        condition = str(check.payload.get("condition", ""))
        if not condition:
            return
        when = check.payload.get("when") or ""

        # Простое правило when: 'state == X' или 'transition(A->B)'
        target_state: str | None = None
        if when.startswith("state ==") or when.startswith("state=="):
            target_state = when.split("==", 1)[1].strip().strip("'\"")

        # Если when пустой или state == X — берём последнее событие в
        # этом состоянии (или последнее в трассе, если state не указан).
        candidate: Event | None = None
        prev_for_candidate: Event | None = None
        prev: Event | None = None
        for ev in trace.events:
            if target_state is None or ev.state == target_state:
                candidate = ev
                prev_for_candidate = prev
            prev = ev

        if candidate is None:
            return

        # Эвристика для N_TOO_LOW
        ctx = self._build_ctx(candidate, prev_for_candidate, spec)
        if "N_collected" not in ctx and "N" in ctx:
            ctx["N_collected"] = ctx["N"]

        evaluator = EvalWithCompoundTypes(
            names=ctx,
            functions={"abs": _abs, "min": min, "max": max},
        )
        try:
            ok = bool(evaluator.eval(condition))
        except (NameNotDefined, FunctionNotDefined):
            ok = False
        except Exception:  # pragma: no cover
            ok = False

        if not ok:
            # Эвристика выбора кода нарушения по содержанию condition
            code = "PRED_FAIL"
            if "N" in condition and ">=" in condition:
                code = "N_TOO_LOW"
            snapshot = {k: ctx[k] for k in ctx if k in condition}
            yield self._make_violation(
                spec,
                code=code,
                state=candidate.state,
                expected={"condition": condition},
                actual=snapshot,
                location=ViolationLocation(
                    event_seq=candidate.seq,
                    ts_rel_s=candidate.t_rel_s,
                    state=candidate.state,
                ),
                spec_ref=check.id,
            )

    def _check_range(self, check, spec: Spec, trace: Trace) -> Iterable[Violation]:
        """checks[kind=range]: значение переменной в [min; max]."""
        var = check.payload.get("variable")
        v_min = check.payload.get("min")
        v_max = check.payload.get("max")
        if not var:
            return

        # Берём значение переменной из RUN_START (как уставку процесса)
        # либо из spec.parameters[var].default
        value = None
        for ev in trace.events:
            if ev.name == "RUN_START" and var in ev.params:
                value = ev.params[var]
                break
        if value is None:
            param = spec.parameters.get(var)
            if isinstance(param, dict):
                value = param.get("default")
            else:
                value = param
        if value is None:
            return

        # Если max ссылается на параметр (например, "T_set_max"),
        # подставим его значение.
        def _resolve(x: Any) -> float | None:
            if isinstance(x, (int, float)):
                return float(x)
            if isinstance(x, str):
                p = spec.parameters.get(x)
                if isinstance(p, dict) and "default" in p:
                    return float(p["default"])
                if isinstance(p, (int, float)):
                    return float(p)
            return None

        lo = _resolve(v_min)
        hi = _resolve(v_max)
        try:
            value_f = float(value)
        except (TypeError, ValueError):
            return

        bad_low = lo is not None and value_f < lo
        bad_high = hi is not None and value_f > hi
        if bad_low or bad_high:
            yield self._make_violation(
                spec,
                code="RANGE_MISM",
                state="",
                expected={"variable": var, "min": lo, "max": hi},
                actual={"value": value_f},
                location=None,
                spec_ref=check.id,
            )


__all__ = ["PredicateMatcher"]
