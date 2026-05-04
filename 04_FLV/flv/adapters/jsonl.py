"""
flv.adapters.jsonl — source-адаптер для нашего формата event-log в
JSONL (Phase 2, `02_Спецификация/event_log_format.md`).

Контракт: реализует Protocol `flv.core.SourceAdapter`. Поддерживает
два режима:

* `load(path)` — прочитать весь файл сразу, вернуть `Trace`.
* `stream(path)` — генератор `Iterator[Event]` для online-проверки
  без удержания всего лога в памяти.

Каждая строка JSONL валидируется против `event_log.schema.json`.
Если schema не найдена в стандартных локациях — валидация
пропускается с warning.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from ..core import Event, SourceAdapter, Trace

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_NAME = "event_log.schema.json"


def _find_default_schema() -> Path | None:
    """Поиск event_log.schema.json в стандартных локациях."""
    candidates = [
        Path.cwd() / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
        Path.cwd().parent / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
        Path(__file__).resolve().parents[3] / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@dataclass
class JsonlAdapter(SourceAdapter):
    """Адаптер для JSONL event-log Phase 2."""

    schema_path: Path | None = None
    strict: bool = False
    name: str = field(default="jsonl", init=False)

    def __post_init__(self) -> None:
        if self.schema_path is None:
            self.schema_path = _find_default_schema()
        self._schema: dict[str, Any] | None = None
        if self.schema_path and Path(self.schema_path).exists():
            self._schema = json.loads(
                Path(self.schema_path).read_text(encoding="utf-8")
            )
        else:
            logger.warning(
                "event_log.schema.json не найден; валидация JSONL пропускается."
            )

    # ──────────────────────────────────────────────────────────────────

    def load(self, source: Path | str) -> Trace:
        """Прочитать весь файл и вернуть иммутабельный Trace."""
        events: list[Event] = []
        run_id = ""
        stand_id = ""
        meta: dict[str, Any] = {}

        for raw_obj in self._iter_raw(source):
            self._validate_obj(raw_obj)
            ev = self._to_event(raw_obj)
            if ev is None:
                continue
            events.append(ev)
            # Заполняем run-level метаданные из RUN_START
            if raw_obj.get("event") == "RUN_START":
                run_id = raw_obj.get("run_id", run_id)
                stand_id = raw_obj.get("stand_id", stand_id)
                meta.update(raw_obj.get("meta") or {})
            elif not run_id:
                # Если RUN_START не первое событие, всё равно подхватываем
                run_id = raw_obj.get("run_id", run_id)
                stand_id = raw_obj.get("stand_id", stand_id)

        if not events:
            raise ValueError(f"Пустой event-log: {source}")

        return Trace(
            run_id=run_id,
            stand_id=stand_id,
            events=tuple(events),
            meta=meta,
        )

    def stream(self, source: Path | str) -> Iterator[Event]:
        """Стриминг событий по одному (online-режим). Не удерживает
        всю трассу в памяти — пригодится при подключении напрямую к
        TCP-сокету или растущему файлу."""
        for raw_obj in self._iter_raw(source):
            self._validate_obj(raw_obj)
            ev = self._to_event(raw_obj)
            if ev is not None:
                yield ev

    # ──────────────────────────────────────────────────────────────────
    # Внутренние помощники
    # ──────────────────────────────────────────────────────────────────

    def _iter_raw(self, source: Path | str) -> Iterator[dict[str, Any]]:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"event-log не найден: {path}")
        # Используем with для корректного освобождения дескриптора
        # (Python rules → Context Managers для resources).
        with open(path, encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    msg = f"{path}:{line_no} — невалидный JSON: {exc}"
                    if self.strict:
                        raise ValueError(msg) from exc
                    logger.warning("Пропускаю строку: %s", msg)

    def _validate_obj(self, obj: dict[str, Any]) -> None:
        if self._schema is None:
            return
        try:
            jsonschema.Draft7Validator(self._schema).validate(obj)
        except jsonschema.ValidationError as exc:
            msg = (
                f"event {obj.get('seq', '?')} ({obj.get('event', '?')}): "
                f"{exc.message}"
            )
            if self.strict:
                raise ValueError(msg) from exc
            logger.warning("Schema-validation предупреждение: %s", msg)

    @staticmethod
    def _to_event(obj: dict[str, Any]) -> Event | None:
        """Преобразовать JSON-объект в Event ядра."""
        try:
            seq = int(obj["seq"])
            state = str(obj["state"])
            name = str(obj["event"])
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Пропускаю событие без обязательных полей: %s", exc)
            return None

        params = obj.get("params") or {}
        signals = obj.get("signals") or {}
        # _ts_rel_s — секунды от начала прогона; если нет — попробуем 0.0
        t_rel_s = float(params.get("_ts_rel_s", 0.0))
        return Event(
            seq=seq,
            t_rel_s=t_rel_s,
            state=state,
            name=name,
            params=dict(params),
            signals=dict(signals),
        )


__all__ = ["JsonlAdapter"]
