"""
flv.core — стабильное ядро фреймворка: абстрактные типы, на которые
опираются все плагины (ADR-004).

Идея: четыре Protocol-типа (`SourceAdapter`, `DslAdapter`, `Matcher`,
`LlmProvider`) и три value-объекта (`Event`, `Trace`, `Spec`,
`Verdict` — последний в `flv.verdict`). Это контракт, который
встроенные реализации и сторонние пакеты обязаны соблюдать.

Конкретные адаптеры/матчеры/провайдеры — отдельные модули
(`flv.adapters.*`, `flv.dsl.*`, `flv.matchers.*`, `flv.llm.*`),
подключаются через entry-points (см. `flv.plugins`).

Использование сторонним кодом:

    from flv.core import SourceAdapter, Matcher
    from flv.plugins import get

    Source = get("source_adapter", "jsonl")
    source: SourceAdapter = Source(Path("run.jsonl"))

    SeqMatcher = get("matcher", "sequence")
    matcher: Matcher = SeqMatcher()
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


# ──────────────────────────────────────────────────────────────────────
# Value-объекты ядра
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Event:
    """Одно событие исполнения сценария ИИС, нормализованное к
    единому формату ядра.

    Контракт для всех `SourceAdapter`-реализаций:
    выдают объекты этого типа, при этом исходный источник может быть
    любым — JSONL, TDMS, XML TestStand, Serial, OpenTelemetry trace.
    """

    seq: int                                 # порядковый номер в прогоне
    t_rel_s: float                           # секунды от начала прогона
    state: str                               # имя состояния FSM
    name: str                                # имя события (RUN_START, ...)
    params: Mapping[str, Any] = field(default_factory=dict)
    signals: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Trace:
    """Полная трасса прогона. Хранится в памяти как последовательность
    Event'ов, упорядоченных по seq.

    Trace принципиально иммутабельна: matcher'ы не могут менять её,
    только читать.
    """

    run_id: str
    stand_id: str
    events: tuple[Event, ...]
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Event]:
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)


@dataclass(frozen=True)
class TransitionSpec:
    """Один переход в FSM нормативной модели (DSL-адаптер заполняет)."""

    id: str
    from_state: str
    to_state: str
    guard: str | None = None
    time_min_s: float | None = None
    time_max_s: float | None = None
    description: str = ""


@dataclass(frozen=True)
class CheckSpec:
    """Дополнительная проверка (sequence/timing/predicate/range)."""

    id: str
    kind: str                                # 'sequence' | 'timing' | 'predicate' | 'range'
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ViolationSpec:
    """Описание кода нарушения из violations_catalog DSL."""

    code: str                                # 'TIME_UNDER', 'PRED_FAIL', ...
    severity: str                            # 'critical' | 'warning' | 'info'
    message: str
    related_check: str | None = None


@dataclass(frozen=True)
class Spec:
    """Внутреннее представление нормативной модели методики.

    DSL-адаптер строит `Spec` из YAML / STL / SysML / ... — далее
    matcher'ы работают с ним вне зависимости от исходного формата.
    """

    id: str
    process_name: str
    states: tuple[str, ...]
    initial_state: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    transitions: tuple[TransitionSpec, ...] = ()
    checks: tuple[CheckSpec, ...] = ()
    violations_catalog: Mapping[str, ViolationSpec] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# Plugin-протоколы (контракты для расширений)
# ──────────────────────────────────────────────────────────────────────


@runtime_checkable
class SourceAdapter(Protocol):
    """Контракт адаптера источника трасс.

    Реализации (entry-points group `flv.source_adapter`):
    * `jsonl`       — наш формат Phase 2 (встроенный).
    * `labview`     — TDMS + Hook VI (заглушка).
    * `teststand`   — XML отчёты NI TestStand (заглушка).
    * `serial`      — Arduino/ESP32 serial-стрим (заглушка).
    * `scpi`        — лог SCPI-команд (заглушка).
    * `otel`        — OpenTelemetry traces (заглушка).
    """

    def load(self, source: Path | str) -> Trace:
        """Загрузить полную трассу за один проход."""
        ...

    def stream(self, source: Path | str) -> Iterator[Event]:
        """Стриминг событий по одному (для online-режима)."""
        ...


@runtime_checkable
class DslAdapter(Protocol):
    """Контракт адаптера DSL.

    Реализации (entry-points group `flv.dsl_adapter`):
    * `yaml`   — наш YAML по `flv_dsl.schema.json` (встроенный).
    * `rtamt`  — STL/MTL через RTAMT (заглушка).
    * `sysml`  — OMG SysML state-machine (заглушка).
    """

    def load(self, source: Path | str) -> Spec:
        ...

    def validate(self, source: Path | str) -> list[str]:
        """Вернуть список ошибок валидации (пустой если OK)."""
        ...


@runtime_checkable
class Matcher(Protocol):
    """Контракт детерминированного matcher'а.

    Реализации (entry-points group `flv.matcher`):
    * `sequence`   — SEQ_MISS, SEQ_ORDER (встроенный).
    * `timing`     — TIME_UNDER, TIME_OVER (встроенный).
    * `predicate`  — PRED_FAIL, RANGE_MISM, N_TOO_LOW (встроенный).
    * `stl`        — обёртка над RTAMT для STL (опциональный).
    """

    name: str       # имя matcher'а для логирования и отчётов

    def match(self, spec: Spec, trace: Trace) -> Iterable[Any]:
        """Вернуть iterable из flv.verdict.Violation."""
        ...


@runtime_checkable
class LlmProvider(Protocol):
    """Контракт провайдера LLM (Роли 1 и 3 по ADR-002).

    Реализации (entry-points group `flv.llm_provider`):
    * `openrouter` — единая абстракция над 5 моделями (по ADR-002).
    * `mock`       — детерминированный stub для unit-тестов.
    * `anthropic`  — прямой Claude (опциональный).
    * `openai`     — прямой OpenAI (опциональный).
    * `onprem`     — локальные Llama/Yandex GPT (опциональный).
    """

    name: str

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        response_model: type[Any] | None = None,
        temperature: float = 0.0,
    ) -> Any:
        """Запросить LLM. Если задан response_model (pydantic),
        вернуть валидированный объект; иначе — сырой текст."""
        ...


__all__ = [
    "Event", "Trace", "TransitionSpec", "CheckSpec", "ViolationSpec", "Spec",
    "SourceAdapter", "DslAdapter", "Matcher", "LlmProvider",
]
