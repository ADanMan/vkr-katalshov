"""
experiments.baseline — наивные ad-hoc проверки для парного сравнения с FLV.

Что моделируется. Типовой стиль написания проверок в коде LabVIEW VI
или Python-сценария измерения, когда инженер «по памяти» вписывает
несколько `assert`-ов и `if`-ов прямо в основной поток исполнения,
без формальной модели методики и без полного покрытия всех условий
приёма из ГОСТ Р 8.563-2009.

Контракт baseline'а:

* Принимает на вход тот же event-log JSONL, что и FLV-модуль.
* Возвращает простой `BaselineVerdict` с булевым `passed` и списком
  кодов из частично-известного набора.
* Покрывает 4-5 проверок «на глаз» (длительность HOLD, диапазон
  T_set, число отсчётов, простая последовательность). НЕ проверяет
  предикаты стабилизации, полный порядок переходов, большой каталог
  кодов нарушений — это закрывает FLV.

Это даёт **paired baseline**: на тех же event-log'ах FLV должен
показывать строго лучшее покрытие, что и есть тезис работы.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Hard-coded ad-hoc пороги — точно так, как часто пишут в реальных
# инженерных скриптах: цифры из методики переписали в код вручную.
ADHOC_T_HOLD_MIN = 300.0
ADHOC_T_HOLD_MAX = 600.0
ADHOC_N_MIN = 20
ADHOC_T_SET_MAX = 250.0


@dataclass(frozen=True)
class BaselineFinding:
    """Одна найденная проблема baseline-проверкой."""

    code: str
    message: str


@dataclass(frozen=True)
class BaselineVerdict:
    """Итог baseline-проверки прогона."""

    run_id: str
    passed: bool
    findings: tuple[BaselineFinding, ...] = ()
    elapsed_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "n_findings": len(self.findings),
            "codes": [f.code for f in self.findings],
            "messages": [f.message for f in self.findings],
            "elapsed_s": self.elapsed_s,
        }


# ──────────────────────────────────────────────────────────────────────
# Реализация ad-hoc проверок
# ──────────────────────────────────────────────────────────────────────


def _iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def check_log(log_path: Path | str) -> BaselineVerdict:
    """Прогнать baseline-проверки по одному event-log JSONL.

    Покрывает:
    1. Простая последовательность: должны быть события HOLD_END и
       MEAS_END (без формальной FSM-модели). Это упрощённая версия
       SEQ_MISS и закрывает только два частных случая.
    2. Длительность HOLD: t_hold < 300 → fail (TIME_UNDER аналог).
    3. Длительность HOLD: t_hold > 600 → fail (TIME_OVER аналог).
    4. Число отсчётов: N_collected < 20 → fail.
    5. Уставка T_set из RUN_START в диапазоне [30; 250].

    НЕ проверяется (ниша FLV):
    * Предикаты стабилизации |dT/dt| ≤ δ.
    * Полный порядок переходов FSM (только наличие двух событий).
    * Привязка к пунктам нормативки.
    * Объяснимость вердикта.
    """
    t_start = time.perf_counter()
    path = Path(log_path)
    findings: list[BaselineFinding] = []

    run_id = ""
    has_hold_end = False
    has_meas_end = False
    t_hold: float | None = None
    n_collected: int | None = None
    t_set: float | None = None

    for ev in _iter_jsonl(path):
        if not run_id:
            run_id = str(ev.get("run_id", ""))
        params = ev.get("params") or {}

        if ev.get("event") == "RUN_START" and "T_set" in params:
            t_set = float(params["T_set"])

        if ev.get("event") == "HOLD_END":
            has_hold_end = True
            if "t_hold" in params:
                t_hold = float(params["t_hold"])

        if ev.get("event") == "MEAS_END":
            has_meas_end = True
            if "N_collected" in params:
                n_collected = int(params["N_collected"])

        if ev.get("event") == "POST_END" and "N_collected" in params:
            n_collected = int(params["N_collected"])

    # 1. Последовательность (только две точки)
    if not has_hold_end:
        findings.append(BaselineFinding(
            code="MISSING_HOLD",
            message="В логе отсутствует событие HOLD_END",
        ))
    if not has_meas_end:
        findings.append(BaselineFinding(
            code="MISSING_MEAS",
            message="В логе отсутствует событие MEAS_END",
        ))

    # 2-3. HOLD длительность
    if t_hold is not None:
        if t_hold < ADHOC_T_HOLD_MIN:
            findings.append(BaselineFinding(
                code="HOLD_TOO_SHORT",
                message=f"HOLD = {t_hold:.0f} c < {ADHOC_T_HOLD_MIN:.0f} c",
            ))
        if t_hold > ADHOC_T_HOLD_MAX:
            findings.append(BaselineFinding(
                code="HOLD_TOO_LONG",
                message=f"HOLD = {t_hold:.0f} c > {ADHOC_T_HOLD_MAX:.0f} c",
            ))

    # 4. Число отсчётов
    if n_collected is not None and n_collected < ADHOC_N_MIN:
        findings.append(BaselineFinding(
            code="FEW_SAMPLES",
            message=f"Собрано {n_collected} отсчётов < {ADHOC_N_MIN}",
        ))

    # 5. Диапазон T_set
    if t_set is not None and (t_set < 30 or t_set > ADHOC_T_SET_MAX):
        findings.append(BaselineFinding(
            code="T_SET_BAD",
            message=f"T_set = {t_set:.0f} вне диапазона [30; {ADHOC_T_SET_MAX:.0f}]",
        ))

    elapsed = time.perf_counter() - t_start
    return BaselineVerdict(
        run_id=run_id,
        passed=not findings,
        findings=tuple(findings),
        elapsed_s=elapsed,
    )


__all__ = [
    "BaselineFinding",
    "BaselineVerdict",
    "check_log",
    "ADHOC_T_HOLD_MIN",
    "ADHOC_T_HOLD_MAX",
    "ADHOC_N_MIN",
    "ADHOC_T_SET_MAX",
]
