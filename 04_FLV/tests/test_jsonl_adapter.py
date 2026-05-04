"""Тесты JsonlAdapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flv.adapters import JsonlAdapter


@pytest.mark.unit
def test_jsonl_loads_full_trace(correct_run_jsonl: Path) -> None:
    trace = JsonlAdapter().load(correct_run_jsonl)
    assert trace.run_id == "S1-T-001"
    assert trace.stand_id == "S1"
    assert len(trace) == 10  # 10 событий в фикстуре
    seqs = [ev.seq for ev in trace.events]
    assert seqs == list(range(10))


@pytest.mark.unit
def test_jsonl_stream_yields_events_one_by_one(correct_run_jsonl: Path) -> None:
    events = list(JsonlAdapter().stream(correct_run_jsonl))
    assert len(events) == 10
    # event-объекты иммутабельны (frozen dataclass из core)
    with pytest.raises((AttributeError, TypeError)):  # frozen → cannot assign
        events[0].seq = 99  # type: ignore[misc]


@pytest.mark.unit
def test_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "with_blanks.jsonl"
    p.write_text(
        json.dumps({"ts": "2026-05-04T10:00:00.000Z", "stand_id": "S1",
                    "run_id": "X", "seq": 0, "state": "INIT",
                    "event": "RUN_START", "params": {"_ts_rel_s": 0.0}})
        + "\n\n   \n"
        + json.dumps({"ts": "2026-05-04T10:00:00.500Z", "stand_id": "S1",
                      "run_id": "X", "seq": 1, "state": "INIT",
                      "event": "INIT_END", "params": {"_ts_rel_s": 0.5}}),
        encoding="utf-8",
    )
    trace = JsonlAdapter().load(p)
    assert len(trace) == 2


@pytest.mark.unit
def test_jsonl_strict_mode_raises_on_invalid(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        JsonlAdapter(strict=True).load(p)
