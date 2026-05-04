"""Тесты Verdict / Violation / aggregate."""

from __future__ import annotations

import pytest

from flv.verdict import (
    Severity,
    Verdict,
    VerdictStatus,
    Violation,
    ViolationLocation,
    aggregate,
)


def _v(code: str, severity: str = "critical", matcher: str = "sequence", seq: int = 0) -> Violation:
    return Violation(
        code=code,
        severity=Severity(severity),
        matcher=matcher,
        location=ViolationLocation(event_seq=seq, ts_rel_s=float(seq)),
    )


@pytest.mark.unit
def test_aggregate_empty_yields_ok() -> None:
    v = aggregate([])
    assert v.status is VerdictStatus.OK
    assert v.critical_count == 0
    assert v.warning_count == 0


@pytest.mark.unit
def test_aggregate_warning_only_yields_ok_with_warnings() -> None:
    v = aggregate([_v("TIME_OVER", "warning", seq=5)])
    assert v.status is VerdictStatus.OK_WITH_WARNINGS


@pytest.mark.unit
def test_aggregate_critical_yields_fail() -> None:
    v = aggregate([_v("TIME_UNDER", "critical", seq=5),
                   _v("PRED_FAIL", "critical", matcher="predicate", seq=5)])
    assert v.status is VerdictStatus.FAIL
    assert v.critical_count == 2


@pytest.mark.unit
def test_aggregate_dedup_same_code_same_seq() -> None:
    """Один и тот же код от двух matcher'ов на одном событии — не дублируется."""
    v = aggregate([
        _v("TIME_UNDER", "critical", matcher="timing", seq=5),
        _v("TIME_UNDER", "critical", matcher="other", seq=5),
    ])
    assert len(v.violations) == 1


@pytest.mark.unit
def test_verdict_to_dict_has_expected_keys() -> None:
    v = aggregate([_v("X", "critical", seq=1)], run_id="R", spec_id="S")
    d = v.to_dict()
    for key in ("run_id", "spec_id", "status", "n_violations", "violations", "summary"):
        assert key in d
    assert d["run_id"] == "R"
    assert d["status"] == "FAIL"
