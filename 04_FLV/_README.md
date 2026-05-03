# 04_FLV

Программный модуль функционально-логической верификации (Phase 4).

## Структура

- `flv/` — пакет:
  - `spec_loader.py` — загрузчик DSL из YAML.
  - `log_parser.py` — парсер JSONL event-log.
  - `verdict.py` — агрегатор вердиктов.
  - `reporter.py` — генератор отчётов (Markdown + JSON).
  - `online.py` — (опционально) online-режим (asyncio TCP).
  - `__main__.py` — CLI entry-point.
  - `matchers/`:
    - `base.py` — абстрактный Matcher.
    - `sequence.py` — проверка последовательности.
    - `timing.py` — проверка длительностей.
    - `predicate.py` — проверка предикатов и диапазонов.
- `tests/` — pytest-юниты (цель ≥ 80% покрытия).
- `benchmarks/bench_matchers.py` — бенчмарк overhead (цель < 100 мс на 10 000 событий).
- `docs/` — документация (Markdown).

## Использование (после реализации)

```bash
cd 04_FLV
pip install -e .
flv check --spec ../02_Спецификация/dsl_v1.yaml --log ../05_Эксперименты/runs/run-001.jsonl --report report.md
flv validate --spec ../02_Спецификация/dsl_v1.yaml
```

## Зависимости

`pyproject.toml`: pyyaml, jsonschema, simpleeval, pytest, click (CLI), rich (вывод).
