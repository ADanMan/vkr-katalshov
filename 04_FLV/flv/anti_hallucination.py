"""
flv.anti_hallucination — пост-фильтр LLM-вывода для Роли 3 ADR-002.

Принцип: LLM формирует объяснение вердикта, но **все ключевые цифры
и идентификаторы** в нём должны быть процитированы из исходных
данных (Verdict + DSL + event-log). Если в тексте обнаруживается
число или код, которого нет в источниках — это потенциальная
галлюцинация: возвращается флаг (`has_hallucination=True`) и
санитизированный текст с маркерами `[?]` рядом с подозрительными
фрагментами.

Caller (LlmExplainer) принимает решение:
* при `has_hallucination=False` — публикует объяснение в отчёте;
* при `has_hallucination=True` — заменяет на детерминированный
  fallback-шаблон (или пробует ещё раз с более жёстким промптом).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Числа в тексте: целые и дробные, опц. знак.
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
# Идентификаторы кодов нарушений и т.п. — UPPER_SNAKE_CASE длиной ≥ 4.
_ID_RE = re.compile(r"\b[A-Z][A-Z0-9_]{3,}\b")


@dataclass(frozen=True)
class AntiHallucinationResult:
    """Результат проверки одного фрагмента LLM-вывода."""

    text: str
    sanitized: str
    has_hallucination: bool
    suspicious_numbers: tuple[str, ...]
    suspicious_ids: tuple[str, ...]


def _collect_known_numbers(sources: Iterable[Any]) -> set[str]:
    """Извлечь все числа-якоря из источников."""
    out: set[str] = set()
    for src in sources:
        if src is None:
            continue
        if isinstance(src, (int, float)):
            out.add(_norm_number(src))
        elif isinstance(src, str):
            for m in _NUMBER_RE.finditer(src):
                out.add(_norm_number(m.group(0)))
        elif isinstance(src, dict):
            out.update(_collect_known_numbers(src.values()))
        elif isinstance(src, (list, tuple, set)):
            out.update(_collect_known_numbers(src))
    return out


def _collect_known_ids(sources: Iterable[Any]) -> set[str]:
    out: set[str] = set()
    for src in sources:
        if src is None:
            continue
        if isinstance(src, str):
            for m in _ID_RE.finditer(src):
                out.add(m.group(0))
        elif isinstance(src, dict):
            out.update(_collect_known_ids(src.values()))
        elif isinstance(src, (list, tuple, set)):
            out.update(_collect_known_ids(src))
    return out


def _norm_number(x: int | float | str) -> str:
    """Нормализовать число к строке для сравнения, схлопывая
    представление: 30 / 30.0 / 30,0 → '30.0'."""
    s = str(x).strip().replace(",", ".")
    try:
        f = float(s)
        # Уберём незначащие нули
        if f.is_integer():
            return f"{int(f)}.0"
        return repr(f)
    except ValueError:
        return s


def check(
    text: str,
    *,
    known_sources: Iterable[Any],
    tolerance_rel: float = 0.005,
) -> AntiHallucinationResult:
    """Проверить, что все числа и UPPER-CASE идентификаторы в text
    встречаются среди known_sources.

    Параметры
    ---------
    text : текст LLM-объяснения.
    known_sources : iterable значений-источников (Verdict.to_dict(),
        Spec, фрагмент event-log). Из них рекурсивно собираются все
        числа и идентификаторы.
    tolerance_rel : допуск для совпадения чисел (5e-3 ≈ 0.5 %).
        Это покрывает округления вида 285.4 → 285 в LLM-выводе.

    Возвращает
    ----------
    AntiHallucinationResult.
    """
    known_numbers_str = _collect_known_numbers(list(known_sources))
    known_numbers_f: list[float] = []
    for s in known_numbers_str:
        try:
            known_numbers_f.append(float(s))
        except ValueError:
            pass
    known_ids = _collect_known_ids(list(known_sources))

    suspicious_numbers: list[str] = []
    suspicious_ids: list[str] = []

    sanitized_parts: list[str] = []
    last = 0
    # Пройдёмся по числам и пометим подозрительные [?]
    for m in _NUMBER_RE.finditer(text):
        token = m.group(0)
        try:
            value = float(token.replace(",", "."))
        except ValueError:
            continue
        ok = False
        for known in known_numbers_f:
            if known == 0.0:
                ok = ok or abs(value) < 1e-9
            else:
                ok = ok or abs(value - known) / max(abs(known), 1.0) <= tolerance_rel
            if ok:
                break
        if not ok:
            suspicious_numbers.append(token)
            sanitized_parts.append(text[last : m.start()])
            sanitized_parts.append(f"{token}[?]")
            last = m.end()

    # Останавливаемся на идентификаторах
    sanitized_after_numbers = "".join(sanitized_parts) + text[last:]

    parts: list[str] = []
    last = 0
    for m in _ID_RE.finditer(sanitized_after_numbers):
        ident = m.group(0)
        if ident in known_ids:
            continue
        suspicious_ids.append(ident)
        parts.append(sanitized_after_numbers[last : m.start()])
        parts.append(f"{ident}[?]")
        last = m.end()
    sanitized = "".join(parts) + sanitized_after_numbers[last:]

    has_h = bool(suspicious_numbers or suspicious_ids)
    if has_h:
        logger.info(
            "Anti-hallucination: подозрительных чисел=%d, идентификаторов=%d",
            len(suspicious_numbers), len(suspicious_ids),
        )

    return AntiHallucinationResult(
        text=text,
        sanitized=sanitized,
        has_hallucination=has_h,
        suspicious_numbers=tuple(suspicious_numbers),
        suspicious_ids=tuple(suspicious_ids),
    )


__all__ = ["AntiHallucinationResult", "check"]
