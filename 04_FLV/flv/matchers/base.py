"""
flv.matchers.base — абстрактный матчер.

Контракт matcher'ов в FLV-фреймворке (ADR-004):

* matcher должен реализовывать Protocol `flv.core.Matcher` (имеет
  атрибут `name` и метод `match(spec, trace) -> Iterable[Violation]`);
* matcher детерминирован — для одних и тех же `spec` и `trace`
  результат строго одинаков (ADR-002, Роль 2);
* matcher не модифицирует ни spec, ни trace; работает в read-only;
* matcher изолирован — никаких внешних API/файлов в горячем пути.

`BaseMatcher` — необязательный helper-родитель, который реализует
общие штуки (имя через атрибут класса, удобный helper для построения
Violation). Наследовать его не обязательно, главное — соблюдать
Protocol.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..core import Spec, Trace
from ..verdict import Severity, Violation, ViolationLocation


class BaseMatcher:
    """Базовый класс matcher'а с удобными helper'ами.

    Подкласс должен:
    * задать `name: ClassVar[str]`;
    * реализовать `match(self, spec, trace) -> Iterable[Violation]`.
    """

    name: str = "base"

    def match(self, spec: Spec, trace: Trace) -> Iterable[Violation]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers, общие для всех matcher'ов
    # ------------------------------------------------------------------

    def _make_violation(
        self,
        spec: Spec,
        *,
        code: str,
        state: str = "",
        expected: dict[str, Any] | None = None,
        actual: dict[str, Any] | None = None,
        location: ViolationLocation | None = None,
        spec_ref: str = "",
    ) -> Violation:
        """Собрать `Violation`, опираясь на violations_catalog в DSL —
        оттуда берутся severity, message и (если есть) norm_ref."""
        catalog_entry = spec.violations_catalog.get(code)
        if catalog_entry is None:
            severity = Severity.CRITICAL
            message = code
            norm_ref = ""
        else:
            severity = Severity(catalog_entry.severity)
            message = catalog_entry.message
            norm_ref = ""  # пункт ГОСТ опционален; DSL может расширить позже
        return Violation(
            code=code,
            severity=severity,
            matcher=self.name,
            state=state,
            expected=expected or {},
            actual=actual or {},
            location=location,
            spec_ref=spec_ref,
            norm_ref=norm_ref,
            message=message,
        )


__all__ = ["BaseMatcher"]
