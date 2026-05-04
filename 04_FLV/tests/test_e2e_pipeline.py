"""Интеграционные тесты pipeline'а: spec + trace → verdict + reporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from flv.adapters import JsonlAdapter
from flv.dsl import YamlDslAdapter
from flv.matchers import PredicateMatcher, SequenceMatcher, TimingMatcher
from flv.reporter import render_json, render_markdown, write_reports
from flv.verdict import VerdictStatus, aggregate


def _run_pipeline(spec_path: Path, log_path: Path):
    spec = YamlDslAdapter().load(spec_path)
    trace = JsonlAdapter().load(log_path)
    matchers = [SequenceMatcher(), TimingMatcher(), PredicateMatcher()]
    violations: list = []
    for m in matchers:
        violations.extend(m.match(spec, trace))
    return aggregate(violations, run_id=trace.run_id, spec_id=spec.id), spec, trace


@pytest.mark.integration
def test_correct_run_yields_verdict_ok(
    sample_dsl_yaml: Path, correct_run_jsonl: Path
) -> None:
    verdict, _, _ = _run_pipeline(sample_dsl_yaml, correct_run_jsonl)
    assert verdict.status is VerdictStatus.OK


@pytest.mark.integration
def test_time_under_run_yields_verdict_fail_with_critical_codes(
    sample_dsl_yaml: Path, time_under_jsonl: Path
) -> None:
    verdict, _, _ = _run_pipeline(sample_dsl_yaml, time_under_jsonl)
    assert verdict.status is VerdictStatus.FAIL
    codes = {v.code for v in verdict.violations}
    assert "TIME_UNDER" in codes
    # PRED_FAIL также должен сработать (dT_dt=0.045 > 0.02)
    assert "PRED_FAIL" in codes


@pytest.mark.integration
def test_reports_are_written(
    sample_dsl_yaml: Path, time_under_jsonl: Path, tmp_path: Path
) -> None:
    verdict, _, _ = _run_pipeline(sample_dsl_yaml, time_under_jsonl)
    json_path = tmp_path / "verdict.json"
    md_path = tmp_path / "verdict.md"
    artifacts = write_reports(verdict, json_path=json_path, markdown_path=md_path)
    assert artifacts.json_path == json_path
    assert artifacts.markdown_path == md_path
    assert json_path.exists()
    assert md_path.exists()
    md = md_path.read_text(encoding="utf-8")
    assert "FAIL" in md
    assert "TIME_UNDER" in md


@pytest.mark.integration
def test_reporter_renders_explanation_block(
    sample_dsl_yaml: Path, time_under_jsonl: Path
) -> None:
    verdict, _, _ = _run_pipeline(sample_dsl_yaml, time_under_jsonl)
    md = render_markdown(verdict, explanation="Тестовое объяснение от LLM.")
    assert "Объяснение (LLM)" in md
    assert "Тестовое объяснение" in md
