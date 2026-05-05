"""
benchmarks/bench_matchers.py — измерение накладных расходов FLV-матчеров.

Запуск:
    python benchmarks/bench_matchers.py

Выводит таблицу: N событий → время матчинга (мс) для каждого матчера
и суммарный overhead на одно событие (мкс).

Используется в разделе 3.5 ПЗ «Оценка вычислительной сложности».
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

# Убеждаемся, что пакет flv доступен при запуске из benchmarks/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flv.adapters.jsonl import JsonlAdapter
from flv.core import Spec, Trace
from flv.dsl import YamlDslAdapter
from flv.matchers import PredicateMatcher, SequenceMatcher, TimingMatcher

# ---------------------------------------------------------------------------
# Генератор синтетических трасс
# ---------------------------------------------------------------------------

_TS_BASE = "2026-05-05T10:00:00.000Z"
_STATES_CYCLE = ["INIT", "HEAT", "HOLD", "MEASURE", "POST"]


def _make_event(seq: int, state: str, event: str, ts_rel: float) -> dict[str, Any]:
    return {
        "ts": _TS_BASE,
        "stand_id": "S1",
        "run_id": f"S1-20260505-{seq:03d}",
        "seq": seq,
        "state": state,
        "event": event,
        "params": {"_ts_rel_s": ts_rel, "T_set": 150.0, "dT_dt": 0.01, "N_collected": 25},
        "signals": {"T": 150.0},
    }


def _build_trace_jsonl(n_cycles: int) -> list[dict[str, Any]]:
    """Собрать трассу из n_cycles полных прогонов FSM (для стресс-теста)."""
    events: list[dict[str, Any]] = []
    seq = 0
    for _ in range(n_cycles):
        t = seq * 10.0
        for state in _STATES_CYCLE:
            events.append(_make_event(seq, state, f"{state}_START", t))
            seq += 1
            t += 5.0
            events.append(_make_event(seq, state, f"{state}_END", t))
            seq += 1
            t += 5.0
    return events


def _jsonl_to_trace(events: list[dict[str, Any]]) -> Trace:
    """Сериализовать список событий во временный JSONL и загрузить через адаптер."""
    import tempfile, os

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        tmp = f.name
    try:
        return JsonlAdapter().load(tmp)
    finally:
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# Загрузка спецификации
# ---------------------------------------------------------------------------

def _load_spec() -> Spec:
    candidates = [
        Path(__file__).resolve().parents[2] / "02_Спецификация" / "dsl_v1.yaml",
    ]
    for p in candidates:
        if p.exists():
            return YamlDslAdapter().load(p)
    raise FileNotFoundError("dsl_v1.yaml не найден. Запускай из корня ВКР.")


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

SIZES = [10, 50, 100, 500, 1_000, 5_000]
MATCHERS = [
    ("SequenceMatcher", SequenceMatcher()),
    ("TimingMatcher",   TimingMatcher()),
    ("PredicateMatcher", PredicateMatcher()),
]
N_REPEATS = 5  # прогонов для усреднения


def run_benchmark() -> dict[str, Any]:
    spec = _load_spec()
    results: dict[str, Any] = {"sizes": SIZES, "matchers": {}}

    for name, matcher in MATCHERS:
        times_ms: list[float] = []
        for n in SIZES:
            events = _build_trace_jsonl(n)
            trace = _jsonl_to_trace(events)
            # Прогрев
            list(matcher.match(spec, trace))
            # Замер
            elapsed = []
            for _ in range(N_REPEATS):
                t0 = time.perf_counter()
                list(matcher.match(spec, trace))
                elapsed.append((time.perf_counter() - t0) * 1000)  # мс
            times_ms.append(min(elapsed))
        results["matchers"][name] = times_ms

    return results


def print_table(results: dict[str, Any]) -> None:
    sizes = results["sizes"]
    print("\n=== FLV Matcher Benchmark ===\n")
    header = f"{'N events':>10}" + "".join(f"{n:>10}" for n in sizes)
    print(header)
    print("-" * len(header))
    for name, times in results["matchers"].items():
        row = f"{name:>10}" + "".join(f"{t:>9.2f}ms" if t < 1000 else f"{t/1000:>8.2f}s " for t in times)
        # Упрощённый вывод
        row = f"{name:<20}" + "".join(f"{t:>9.2f}" for t in times)
        print(row)
    print()
    print("Единицы: мс (время матчинга одной трассы)")

    # Overhead на событие (мкс) при максимальном N
    print("\n--- Накладные расходы на 1 событие (мкс, N_max) ---")
    n_max = sizes[-1] * 10  # событий в трассе (2 * N_cycles * 5 состояний)
    for name, times in results["matchers"].items():
        t_max_ms = times[-1]
        us_per_event = (t_max_ms * 1000) / (sizes[-1] * len(["INIT","HEAT","HOLD","MEASURE","POST"]) * 2)
        print(f"  {name:<22}: {us_per_event:.2f} мкс/событие")


def save_results(results: dict[str, Any]) -> None:
    out = Path(__file__).parent / "bench_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nРезультаты сохранены: {out}")


if __name__ == "__main__":
    print("Запуск FLV benchmark...")
    results = run_benchmark()
    print_table(results)
    save_results(results)
