# Phase 4 — Реализация модуля FLV

> Срок: 2026-05-18 → 2026-05-24 (7 дней с перекрытием). Зависимости: Phase 2 (DSL/Schema), Phase 3 (формат event-log реально пишется симулятором).

---

## 1. Цель

Реализовать программный модуль `flv`, который принимает DSL-спецификацию + event-log и выдаёт вердикт OK/FAIL с детализированным списком нарушений. Покрытие ≥ 80% по unit-тестам, overhead < 100 мс на 10 000 событий.

---

## 2. Архитектура (повторяем из Phase 2 для контекста)

```
DSL (YAML) ──► Spec Loader ──► Internal FSM Model
                                       │
JSONL (event-log) ──► Log Parser ──► Normalized Events
                                       │
                                       ▼
                          Matcher Pipeline (Sequence → Timing → Predicate)
                                       │
                                       ▼
                              Verdict Aggregator
                                       │
                                       ▼
                            Markdown / JSON Reporter
```

---

## 3. Действия

| # | Действие | Артефакт |
|---|---|---|
| 4.1 | DSL-loader (YAML → internal model) с валидацией по JSON Schema | `04_FLV/flv/spec_loader.py` |
| 4.2 | Парсер event-log (JSONL → normalized event sequence) | `04_FLV/flv/log_parser.py` |
| 4.3 | Sequence matcher (обязательные шаги, порядок переходов) | `04_FLV/flv/matchers/sequence.py` |
| 4.4 | Timing matcher (временные окна, длительности состояний) | `04_FLV/flv/matchers/timing.py` |
| 4.5 | Predicate matcher (булевы условия, диапазоны, число измерений) | `04_FLV/flv/matchers/predicate.py` |
| 4.6 | Aggregator (свод вердиктов от matchers, расчёт OK/FAIL) | `04_FLV/flv/verdict.py` |
| 4.7 | Reporter (Markdown + JSON отчёты) | `04_FLV/flv/reporter.py` |
| 4.8 | CLI: `flv check --spec dsl.yaml --log run.jsonl --report out.md` | `04_FLV/flv/__main__.py` |
| 4.9 | Тесты pytest на каждый matcher + интеграционный тест прогон/вердикт | `04_FLV/tests/` |
| 4.10 | (Опционально) Online-режим — TCP-стрим лога, инкрементальный матчинг | `04_FLV/flv/online.py` |
| 4.11 | Бенчмарк overhead | `04_FLV/benchmarks/bench_matchers.py` |
| 4.12 | Документация модуля (Sphinx или просто Markdown) | `04_FLV/docs/` |

---

## 4. Структура пакета

```
04_FLV/
├── flv/
│   ├── __init__.py
│   ├── __main__.py             ← CLI entry-point
│   ├── spec_loader.py
│   ├── log_parser.py
│   ├── verdict.py
│   ├── reporter.py
│   ├── online.py               ← опционально
│   └── matchers/
│       ├── __init__.py
│       ├── base.py             ← абстрактный Matcher
│       ├── sequence.py
│       ├── timing.py
│       └── predicate.py
├── tests/
│   ├── conftest.py
│   ├── test_sequence.py
│   ├── test_timing.py
│   ├── test_predicate.py
│   └── test_integration.py
├── benchmarks/
│   └── bench_matchers.py
├── docs/
│   └── usage.md
├── pyproject.toml
└── README.md
```

---

## 5. Подробности по matchers

### 5.1 Sequence

- Проверяет: все обязательные состояния посещены, переходы — только из разрешённых пар.
- Алгоритм: `O(n)` обход event-list, в каждом шаге сверка с FSM-таблицей.
- Возвращает: список (`SEQ_MISS`, `SEQ_ORDER`) с фактами «expected vs actual».

### 5.2 Timing

- Проверяет: длительность каждого состояния ∈ [time.min, time.max].
- Алгоритм: парсинг START/END событий, агрегация по state, сверка границ.
- Возвращает: список (`TIME_UNDER`, `TIME_OVER`) с фактами.

### 5.3 Predicate

- Проверяет: булевы условия из guards и checks (e.g. `abs(dT_dt) <= delta`, `N >= N_min`).
- Реализация: безопасный eval (через `simpleeval` или собственный AST-walker).
- Возвращает: список (`PRED_FAIL`, `RANGE_MISM`, `N_TOO_LOW`) с фактами.

### 5.4 Aggregator

- Объединяет результаты matchers в единый Verdict-объект.
- Решение OK/FAIL: FAIL, если есть хотя бы одно нарушение из «обязательной» категории; иначе OK с warning.
- Поддержка приоритетов и подавления повторных одинаковых нарушений.

---

## 6. CLI

```
flv check --spec dsl.yaml --log run.jsonl --report out.md [--json] [--fail-fast]
flv validate --spec dsl.yaml          # только валидация Schema
flv online --spec dsl.yaml --port 9001 # online-режим
```

---

## 7. Тесты

| Тип | Что покрывает |
|---|---|
| `test_spec_loader.py` | Корректные/невалидные DSL, граничные случаи |
| `test_sequence.py` | SEQ_MISS, SEQ_ORDER на синтетических логах |
| `test_timing.py` | TIME_UNDER, TIME_OVER, нулевые длительности |
| `test_predicate.py` | PRED_FAIL, RANGE_MISM, N_TOO_LOW |
| `test_integration.py` | Сцепка всех matchers на реальном логе из Phase 3 |
| `test_reporter.py` | Markdown и JSON отчёты валидны |

Цель: pytest coverage ≥ 80%.

---

## 8. Бенчмарк overhead

Скрипт `bench_matchers.py`:
- Генерирует синтетический лог 10 000 событий.
- Замеряет wall-time прогона matcher pipeline.
- Целевое значение: **< 100 мс**.
- Если медленно — профилируем через `cProfile`, оптимизируем горячие точки.

---

## 9. Online-режим (опционально, если есть время)

- Сервер на `asyncio` принимает JSONL-стрим по TCP.
- Инкрементальный матчинг: по приходу события — обновление состояния FSM, мгновенная проверка.
- При FAIL — отправка обратно по сокету команды на блокировку.
- Для демо хватит docстрок и одного примера.

---

## 10. Критерии завершения

- 100% покрытие 7 типов нарушений (тесты подтверждают).
- На корректном логе из Phase 3 — `verdict: OK`.
- На каждом инжектированном логе — соответствующий код в верном matcher'е.
- Overhead < 100 мс на лог 10 000 событий (бенчмарк прогнан, цифры в `04_FLV/docs/bench_results.md`).
- CLI работает на 4 типах команд из раздела 6.

---

## 11. Риски

| Риск | Меры |
|---|---|
| Регрессии при добавлении STL | STL — отдельный опциональный matcher, не трогает базовые |
| Тесты текут | pytest -x на каждом коммите, GitHub Actions CI (если успеваем настроить) |
| Eval небезопасный | Использовать `simpleeval` или AST-walker с whitelisted nodes |

---

## 12. Чек-лист

- [ ] Создать `04_FLV/` со скелетом пакета.
- [ ] `pyproject.toml` (зависимости: pyyaml, jsonschema, simpleeval, pytest).
- [ ] Реализовать `spec_loader.py` + тесты.
- [ ] Реализовать `log_parser.py` + тесты.
- [ ] Реализовать `matchers/sequence.py` + тесты.
- [ ] Реализовать `matchers/timing.py` + тесты.
- [ ] Реализовать `matchers/predicate.py` + тесты.
- [ ] Реализовать `verdict.py` + `reporter.py`.
- [ ] CLI работает на тестовых логах из Phase 3.
- [ ] Бенчмарк подтверждает overhead < 100 мс.
- [ ] Обновить `ВКР_План.md`.
