"""Тесты YamlDslAdapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from flv.dsl import YamlDslAdapter


@pytest.mark.unit
def test_yaml_loader_builds_spec_with_all_states(sample_dsl_yaml: Path) -> None:
    spec = YamlDslAdapter().load(sample_dsl_yaml)
    assert spec.states == ("INIT", "HEAT", "HOLD", "MEASURE", "POST")
    assert spec.process_name == "temperature_measurement_test"
    assert "T_min" in spec.parameters
    assert len(spec.transitions) == 4
    assert "TIME_UNDER" in spec.violations_catalog


@pytest.mark.unit
def test_yaml_loader_rejects_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: valid: yaml: ::: %", encoding="utf-8")
    errors = YamlDslAdapter().validate(bad)
    assert errors  # ошибки парсинга


@pytest.mark.unit
def test_yaml_loader_semantic_check_unknown_state(tmp_path: Path) -> None:
    p = tmp_path / "broken.yaml"
    p.write_text(
        """
meta: {id: x, version: 1}
process: {name: x}
states:
  - {name: A, required: true}
  - {name: B, required: true}
transitions:
  - {id: t1, from: A, to: NONEXISTENT}
violations_catalog:
  X:
    severity: critical
    message: "test"
""",
        encoding="utf-8",
    )
    errors = YamlDslAdapter().validate(p)
    # Должна быть ошибка: to='NONEXISTENT' не в states
    assert any("NONEXISTENT" in e for e in errors)


@pytest.mark.unit
def test_violations_catalog_shorthand_string_form(tmp_path: Path) -> None:
    """Поддержка краткой записи code: 'message'."""
    p = tmp_path / "short.yaml"
    p.write_text(
        """
meta: {id: x, version: 1}
process: {name: x}
states:
  - {name: A, required: true}
  - {name: B, required: true}
transitions:
  - {id: t1, from: A, to: B}
violations_catalog:
  CODE_X: "Простое сообщение"
""",
        encoding="utf-8",
    )
    spec = YamlDslAdapter().load(p)
    assert "CODE_X" in spec.violations_catalog
    assert spec.violations_catalog["CODE_X"].message == "Простое сообщение"
    assert spec.violations_catalog["CODE_X"].severity == "critical"
