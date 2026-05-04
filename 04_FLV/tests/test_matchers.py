"""Тесты matcher'ов на синтетических трассах."""

from __future__ import annotations

from pathlib import Path

import pytest

from flv.adapters import JsonlAdapter
from flv.dsl import YamlDslAdapter
from flv.matchers import PredicateMatcher, SequenceMatcher, TimingMatcher


def _load(spec_path: Path, log_path: Path):
    return YamlDslAdapter().load(spec_path), JsonlAdapter().load(log_path)


@pytest.mark.unit
def test_sequence_matcher_passes_on_correct_run(
    sample_dsl_yaml: Path, correct_run_jsonl: Path
) -> None:
    spec, trace = _load(sample_dsl_yaml, correct_run_jsonl)
    violations = list(SequenceMatcher().match(spec, trace))
    assert violations == []


@pytest.mark.unit
def test_timing_matcher_detects_time_under(
    sample_dsl_yaml: Path, time_under_jsonl: Path
) -> None:
    spec, trace = _load(sample_dsl_yaml, time_under_jsonl)
    violations = list(TimingMatcher().match(spec, trace))
    codes = [v.code for v in violations]
    assert "TIME_UNDER" in codes


@pytest.mark.unit
def test_timing_matcher_clean_on_correct_run(
    sample_dsl_yaml: Path, correct_run_jsonl: Path
) -> None:
    spec, trace = _load(sample_dsl_yaml, correct_run_jsonl)
    violations = list(TimingMatcher().match(spec, trace))
    # На эталонном прогоне HOLD = 330 c — в окне [300; 600], OK
    assert all(v.code != "TIME_UNDER" for v in violations)
    assert all(v.code != "TIME_OVER" for v in violations)


@pytest.mark.unit
def test_predicate_matcher_detects_pred_fail(
    sample_dsl_yaml: Path, time_under_jsonl: Path
) -> None:
    """В time_under фикстуре dT_dt = 0.045 на HOLD_END — больше 0.02."""
    spec, trace = _load(sample_dsl_yaml, time_under_jsonl)
    violations = list(PredicateMatcher().match(spec, trace))
    codes = [v.code for v in violations]
    assert "PRED_FAIL" in codes
