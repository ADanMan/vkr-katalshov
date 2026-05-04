"""
flv — pluggable-фреймворк функционально-логической верификации
программных моделей измерительных процессов в составе ИИС.

Часть ВКР Катальшова Д.А., К2-81Б, 12.03.01 Приборостроение,
профиль «Информационно-измерительная техника и технологии»,
МФ МГТУ им. Н.Э. Баумана.

Архитектура — `02_Спецификация/architecture.md` и два ADR:

* `99_Артефакты/ADR_002_role_of_LLM.md` — гибридная LLM-формальная
  система с тремя ролями LLM: извлечение DSL из текста, объяснение
  вердикта, опционально LLM-as-judge.
* `99_Артефакты/ADR_004_flv_as_pluggable_framework.md` — четыре точки
  расширения: source_adapter, dsl_adapter, matcher, llm_provider —
  через стандартный python entry-points механизм.

Высокоуровневые типы пакета:

    Spec    — внутреннее представление нормативной модели методики
              (загружается DslAdapter из YAML / RTAMT / SysML / ...)
    Trace   — последовательность типизированных Event'ов от ИИС
              (производится SourceAdapter из JSONL / LabVIEW VI /
              TestStand / SCPI / Serial / OpenTelemetry)
    Matcher — детерминированная проверка одного из условий приёма
              (SequenceMatcher, TimingMatcher, PredicateMatcher,
              опц. StlMatcher через RTAMT)
    Verdict — итоговый результат (OK / OK_WITH_WARNINGS / FAIL)
              + список Violation'ов с привязкой к нормативке.

Ядро фреймворка не зависит от конкретных адаптеров и провайдеров —
они подключаются через `flv.plugins.discover()` (Phase 4.2+).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vkr-katalshov-flv")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

__all__ = ["__version__"]
