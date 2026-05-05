"""
sim.event_logger — запись событий симулятора в JSONL по формату
Phase 2 (`02_Спецификация/event_log_format.md` + Schema).

Контракт: каждый вызов `write()` сериализует одну строку JSON,
соответствующую `event_log.schema.json`. Логгер сам ведёт счётчик
`seq` и подставляет идентификаторы стенда / прогона.

Используется из `scenario_runner.ScenarioRunner` через интерфейс
EventSink: callable(event, state, params, signals, ts) → None.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import TextIOBase
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

from . import config as cfg

logger = logging.getLogger(__name__)


def _now_iso_ms() -> str:
    """ISO-8601 UTC c миллисекундным разрешением, как требует
    `event_log.schema.json` (паттерн `^\\d{4}-...\\d{3}Z$`)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


@dataclass
class EventLogger:
    """Append-only JSONL-логгер событий симулятора.

    Можно использовать как контекстный менеджер:

        with EventLogger.open("run.jsonl", run_id="S1-20260503-001") as log:
            log.write("RUN_START", "INIT", {"T_set": 150}, {"T": 24.3}, 0.0)
            ...
    """

    path: Path
    run_id: str
    stand_id: str = cfg.STAND_ID
    fsync_on_critical: bool = True
    _seq: int = field(default=0, init=False)
    _stream: TextIOBase | None = field(default=None, init=False, repr=False)

    # Множество событий, после которых форсируем sync на диск
    _CRITICAL_EVENTS = frozenset({"RUN_START", "RUN_END", "ERROR"})

    @classmethod
    def open(
        cls,
        path: str | os.PathLike[str],
        *,
        run_id: str,
        stand_id: str = cfg.STAND_ID,
        fsync_on_critical: bool = True,
    ) -> Self:
        """Открыть логгер и сразу подготовить файловый дескриптор."""
        log = cls(
            path=Path(path),
            run_id=run_id,
            stand_id=stand_id,
            fsync_on_critical=fsync_on_critical,
        )
        log.path.parent.mkdir(parents=True, exist_ok=True)
        # Build new file
        log._stream = open(log.path, "w", encoding="utf-8")  # noqa: SIM115
        logger.info("EventLogger opened: path=%s run_id=%s", log.path, log.run_id)
        return log

    # ----- context manager -----

    def __enter__(self) -> Self:
        if self._stream is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = open(self.path, "w", encoding="utf-8")  # noqa: SIM115
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore[no-untyped-def]
        self.close()

    def close(self) -> None:
        if self._stream is not None:
            self._stream.flush()
            self._stream.close()
            self._stream = None
            logger.info("EventLogger closed: path=%s seq=%d", self.path, self._seq)

    # ----- основной API -----

    def write(
        self,
        event: str,
        state: str,
        params: dict[str, Any] | None,
        signals: dict[str, Any] | None,
        ts: float,
    ) -> None:
        """Записать одну строку события.

        Параметры
        ---------
        event : имя события из каталога Schema (RUN_START, HOLD_END, ...).
        state : текущее состояние FSM (INIT, HEAT, ...).
        params : параметры процесса (t_hold, T_set, и т.п.).
        signals : снимок сигналов (T, dT_dt, и т.п.).
        ts : относительное время от начала прогона, секунды (для отладки).

        Поле `ts` в JSON — всегда абсолютная UTC-метка ISO-8601.
        Относительное время логируется как `params._ts_rel_s`, если
        оно ещё не присутствует в params.
        """
        if self._stream is None:
            raise RuntimeError(f"EventLogger {self.path} is not opened")

        params = dict(params) if params else {}
        signals = dict(signals) if signals else {}

        # Дополнить params относительной временной меткой для
        # последующего восстановления длительности состояний.
        params.setdefault("_ts_rel_s", float(ts))

        # На RUN_START подмешиваем мета-информацию о версии формата
        meta: dict[str, Any] | None = None
        if event == "RUN_START":
            meta = {
                "log_format_version": cfg.LOG_FORMAT_VERSION,
                "simulator_version": cfg.SIMULATOR_VERSION,
            }

        entry: dict[str, Any] = {
            "ts": _now_iso_ms(),
            "stand_id": self.stand_id,
            "run_id": self.run_id,
            "seq": self._seq,
            "state": state,
            "event": event,
        }
        if params:
            entry["params"] = params
        if signals:
            entry["signals"] = signals
        if meta:
            entry["meta"] = meta

        # Atomic line write: одна строка целиком за один write().
        # ensure_ascii=False, чтобы не разъезжалось utf-8 в diagnostic
        # текстах ("без \\u…"); separators убирает лишние пробелы.
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        self._stream.write(line + "\n")

        if event in self._CRITICAL_EVENTS:
            self._stream.flush()
            if self.fsync_on_critical:
                # На некоторых FS (virtiofs / NFS) fsync может бросить;
                # это не должно ронять прогон.
                try:
                    os.fsync(self._stream.fileno())
                except OSError as e:  # pragma: no cover
                    logger.warning("fsync failed for %s: %s", self.path, e)

        self._seq += 1


# ----------------------------------------------------------------------
# Удобный helper: загрузка JSONL обратно в список словарей
# ----------------------------------------------------------------------


def load_jsonl(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Прочитать .jsonl файл целиком и вернуть список словарей.
    Используется тестами и `viz.dashboard_dash` для воспроизведения
    прогона.
    """
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


__all__ = ["EventLogger", "load_jsonl"]
