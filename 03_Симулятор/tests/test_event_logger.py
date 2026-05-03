"""Тесты `sim.event_logger.EventLogger` и `load_jsonl`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.event_logger import EventLogger, load_jsonl


@pytest.mark.unit
def test_event_logger_writes_one_line_per_event(tmp_path: Path) -> None:
    p = tmp_path / "out.jsonl"
    with EventLogger.open(p, run_id="S1-T-001") as log:
        log.write("RUN_START", "INIT", {"T_set": 150}, {"T": 24.3}, 0.0)
        log.write("INIT_END", "INIT", {"device_ready": True}, None, 0.5)
        log.write("RUN_END", "POST", {"run_status": "completed"}, None, 30.0)

    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert [e["seq"] for e in parsed] == [0, 1, 2]
    assert parsed[0]["event"] == "RUN_START"
    assert parsed[0]["meta"]["log_format_version"]


@pytest.mark.unit
def test_event_logger_seq_is_monotonic(tmp_path: Path) -> None:
    p = tmp_path / "out.jsonl"
    with EventLogger.open(p, run_id="S1-T-002") as log:
        for i in range(50):
            log.write("SAMPLE", "HOLD", {"_ts_rel_s": float(i)}, {"T": 100.0 + i}, float(i))
    events = load_jsonl(p)
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(50))


@pytest.mark.unit
def test_event_logger_iso_timestamp_format(tmp_path: Path) -> None:
    """ts должно соответствовать regex Schema: YYYY-MM-DDTHH:MM:SS.sssZ."""
    p = tmp_path / "out.jsonl"
    with EventLogger.open(p, run_id="S1-T-003") as log:
        log.write("RUN_START", "INIT", None, None, 0.0)
    events = load_jsonl(p)
    ts = events[0]["ts"]
    # Простая проверка структуры
    assert ts.endswith("Z")
    assert "T" in ts
    assert ts[-5:-1].isdigit() or ts[-5] == "."  # есть миллисекунды


@pytest.mark.unit
def test_event_logger_raises_after_close(tmp_path: Path) -> None:
    p = tmp_path / "out.jsonl"
    log = EventLogger.open(p, run_id="S1-T-004")
    log.write("RUN_START", "INIT", None, None, 0.0)
    log.close()
    with pytest.raises(RuntimeError):
        log.write("RUN_END", "POST", None, None, 1.0)


@pytest.mark.unit
def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "out.jsonl"
    p.write_text(
        '{"a": 1}\n\n{"b": 2}\n   \n{"c": 3}\n', encoding="utf-8"
    )
    events = load_jsonl(p)
    assert events == [{"a": 1}, {"b": 2}, {"c": 3}]


@pytest.mark.unit
def test_event_logger_critical_events_flush(tmp_path: Path) -> None:
    """После RUN_START данные должны быть на диске сразу (flush+fsync)."""
    p = tmp_path / "out.jsonl"
    log = EventLogger.open(p, run_id="S1-T-005")
    log.write("RUN_START", "INIT", None, None, 0.0)
    # Файл должен содержать строку даже без close()
    content = p.read_text(encoding="utf-8")
    assert "RUN_START" in content
    log.close()
