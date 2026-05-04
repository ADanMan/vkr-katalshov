"""
flv.verdict — структуры Violation и Verdict, агрегатор вердиктов.

Контракт matcher'ов: возвращают Iterable[Violation]. Verdict
формируется агрегатором из списка violations согласно правилу:

  если есть critical → FAIL
  иначе если есть warning → OK_WITH_WARNINGS
  иначе → OK

См. `02_Спецификация/formal_model.md` §5 и
`02_Спецификация/violations_catalog.md`.

Все структуры — frozen dataclass'ы (immutable); это контрактная
гарантия: matcher не может постфактум подменить vердикт другому
matcher'у. PEP 8 + type annotations всюду.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Категория серьёзности нарушения. Совпадает с DSL-полем
    `violations_catalog.<code>.severity`."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class VerdictStatus(str, Enum):
    """Финальный статус прогона."""

    OK = "OK"
    OK_WITH_WARNINGS = "OK_WITH_WARNINGS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ViolationLocation:
    """Указатель на событие в трассе, где обнаружено нарушение."""

    event_seq: int
    ts_rel_s: float
    state: str = ""


@dataclass(frozen=True)
class Violation:
    """Одно обнаруженное нарушение.

    Структура совпадает с описанием в `02_Спецификация/
    violations_catalog.md` §1.
    """

    code: str                                    # SEQ_MISS, TIME_UNDER, ...
    severity: Severity
    matcher: str                                 # 'sequence' | 'timing' | 'predicate'
    state: str = ""
    expected: Mapping[str, Any] = field(default_factory=dict)
    actual: Mapping[str, Any] = field(default_factory=dict)
    location: ViolationLocation | None = None
    spec_ref: str = ""                           # transition.id или check.id из DSL
    norm_ref: str = ""                           # ссылка на пункт ГОСТ (опционально)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity.value,
            "matcher": self.matcher,
            "state": self.state,
            "expected": dict(self.expected),
            "actual": dict(self.actual),
            "spec_ref": self.spec_ref,
            "norm_ref": self.norm_ref,
            "message": self.message,
        }
        if self.location is not None:
            out["location"] = {
                "event_seq": self.location.event_seq,
                "ts_rel_s": self.location.ts_rel_s,
                "state": self.location.state,
            }
        return out


@dataclass(frozen=True)
class Verdict:
    """Итоговый вердикт по прогону: OK / OK_WITH_WARNINGS / FAIL +
    структурированный список violations + сводка по matcher'ам.
    """

    status: VerdictStatus
    violations: tuple[Violation, ...] = ()
    run_id: str = ""
    spec_id: str = ""
    summary: Mapping[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity is Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity is Severity.WARNING)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "spec_id": self.spec_id,
            "status": self.status.value,
            "n_violations": len(self.violations),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "violations": [v.to_dict() for v in self.violations],
            "summary": dict(self.summary),
        }


# ──────────────────────────────────────────────────────────────────────
# Агрегатор
# ──────────────────────────────────────────────────────────────────────


def aggregate(
    violations: Iterable[Violation],
    *,
    run_id: str = "",
    spec_id: str = "",
    extra_summary: Mapping[str, Any] | None = None,
) -> Verdict:
    """Собрать Verdict из flat-списка violations.

    Сортировка: по event_seq (если есть location), затем по коду.
    Дедуп: если одна и та же пара (code, location.event_seq) возникает
    у двух matcher'ов — оставляем первый, остальные пропускаем.

    Сводка по matcher'ам автоматически считается и кладётся в
    `summary["by_matcher"]`.
    """
    seen: set[tuple[str, int]] = set()
    deduped: list[Violation] = []
    by_matcher: dict[str, int] = {}
    by_code: dict[str, int] = {}

    for v in violations:
        key = (v.code, v.location.event_seq if v.location else -1)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(v)
        by_matcher[v.matcher] = by_matcher.get(v.matcher, 0) + 1
        by_code[v.code] = by_code.get(v.code, 0) + 1

    deduped.sort(
        key=lambda x: (
            x.location.event_seq if x.location else 1 << 30,
            x.code,
        )
    )

    if any(v.severity is Severity.CRITICAL for v in deduped):
        status = VerdictStatus.FAIL
    elif any(v.severity is Severity.WARNING for v in deduped):
        status = VerdictStatus.OK_WITH_WARNINGS
    else:
        status = VerdictStatus.OK

    summary: dict[str, Any] = {
        "by_matcher": by_matcher,
        "by_code": by_code,
        "sequence_ok": all(
            v.matcher != "sequence" or v.severity is not Severity.CRITICAL
            for v in deduped
        ),
        "timing_ok": all(
            v.matcher != "timing" or v.severity is not Severity.CRITICAL
            for v in deduped
        ),
        "predicates_ok": all(
            v.matcher != "predicate" or v.severity is not Severity.CRITICAL
            for v in deduped
        ),
    }
    if extra_summary:
        summary.update(extra_summary)

    return Verdict(
        status=status,
        violations=tuple(deduped),
        run_id=run_id,
        spec_id=spec_id,
        summary=summary,
    )


__all__ = [
    "Severity",
    "VerdictStatus",
    "ViolationLocation",
    "Violation",
    "Verdict",
    "aggregate",
]
