"""Тесты anti_hallucination."""

from __future__ import annotations

import pytest

from flv import anti_hallucination as ah


@pytest.mark.unit
def test_no_hallucination_when_numbers_in_sources() -> None:
    text = "Значение 30 секунд при норме 300 секунд."
    result = ah.check(text, known_sources=[{"actual": 30, "expected": 300}])
    assert not result.has_hallucination
    assert result.suspicious_numbers == ()


@pytest.mark.unit
def test_detects_unknown_number() -> None:
    text = "Какое-то 999 не из источников."
    result = ah.check(text, known_sources=[{"actual": 30}])
    assert result.has_hallucination
    assert "999" in result.suspicious_numbers
    assert "999[?]" in result.sanitized


@pytest.mark.unit
def test_tolerance_for_rounded_numbers() -> None:
    """LLM мог округлить 285.4 до 285 — не считаем галлюцинацией."""
    text = "Длительность 285 c."
    result = ah.check(text, known_sources=[{"t_hold": 285.4}])
    assert not result.has_hallucination


@pytest.mark.unit
def test_detects_unknown_uppercase_id() -> None:
    text = "Это нарушение типа FAKE_CODE."
    result = ah.check(text, known_sources=["TIME_UNDER PRED_FAIL"])
    assert result.has_hallucination
    assert "FAKE_CODE" in result.suspicious_ids


@pytest.mark.unit
def test_known_id_passes() -> None:
    text = "Нарушение TIME_UNDER зафиксировано."
    result = ah.check(text, known_sources=[{"code": "TIME_UNDER"}])
    assert not result.has_hallucination
