"""
flv.plugins — discovery механизма entry-points для pluggable-фреймворка
(ADR-004).

Используется ядром и CLI: при старте регистрируются все доступные
адаптеры и провайдеры из entry-points текущего окружения, после чего
пользователь может выбирать их по имени через флаги CLI или Python API.

Пример. Установив сторонний пакет `flv-labview-adapter`, мы получаем
автоматическое появление `--source labview` в CLI без изменения ядра.

Использование:

    from flv.plugins import discover

    catalog = discover()
    print(catalog["source_adapter"].keys())   # {'jsonl', 'labview', ...}

    JsonlAdapter = catalog["source_adapter"]["jsonl"]  # тип, не экземпляр
    adapter = JsonlAdapter(path)
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Any

logger = logging.getLogger(__name__)

# Группы entry-points фреймворка (ADR-004)
GROUPS: tuple[str, ...] = (
    "flv.source_adapter",
    "flv.dsl_adapter",
    "flv.matcher",
    "flv.llm_provider",
)


@dataclass(frozen=True)
class PluginRecord:
    """Инвариантная запись о найденном плагине."""

    group: str         # без префикса 'flv.', напр. 'matcher'
    name: str          # имя реализации, напр. 'sequence'
    entry: EntryPoint  # сам entry_point (отложенная загрузка через .load())


def _short_group(full_group: str) -> str:
    """'flv.source_adapter' → 'source_adapter'."""
    return full_group.removeprefix("flv.")


def iter_plugins() -> Iterator[PluginRecord]:
    """Лениво пробежать по всем зарегистрированным плагинам всех
    четырёх групп. Не загружает классы (только метаданные)."""
    for group in GROUPS:
        try:
            eps = entry_points(group=group)
        except TypeError:
            # старая Python <= 3.9 совместимость
            eps = entry_points().get(group, [])
        for ep in eps:
            yield PluginRecord(group=_short_group(group), name=ep.name, entry=ep)


def discover(*, load: bool = True) -> dict[str, dict[str, Any]]:
    """Собрать каталог всех доступных плагинов.

    Параметры
    ---------
    load : bool
        Если True (по умолчанию) — entry_point.load() выполняется
        сразу, и значение в каталоге это уже сам класс/функция.
        Если False — оставляется EntryPoint для отложенной загрузки.

    Возвращает
    ----------
    dict вида:
        {
            "source_adapter": {"jsonl": <class JsonlAdapter>, ...},
            "dsl_adapter":    {"yaml":  <class YamlDslAdapter>, ...},
            "matcher":        {"sequence": ..., "timing": ..., ...},
            "llm_provider":   {"openrouter": ..., "mock": ...},
        }
    """
    catalog: dict[str, dict[str, Any]] = {
        _short_group(g): {} for g in GROUPS
    }
    for record in iter_plugins():
        target = record.entry
        if load:
            try:
                target = record.entry.load()
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Не удалось загрузить плагин %s.%s: %s",
                    record.group, record.name, exc,
                )
                continue
        catalog[record.group][record.name] = target
    return catalog


def get(group: str, name: str) -> Any:
    """Удобный доступ: `flv.plugins.get("matcher", "sequence")`."""
    catalog = discover(load=True)
    if group not in catalog:
        raise KeyError(f"Unknown plugin group: {group!r}. Доступны: {sorted(catalog)}")
    if name not in catalog[group]:
        raise KeyError(
            f"Plugin {group}/{name!r} не найден. "
            f"Установлены: {sorted(catalog[group])}"
        )
    return catalog[group][name]


__all__ = ["discover", "get", "iter_plugins", "PluginRecord", "GROUPS"]
