# FLV — Руководство по использованию

> Модуль `flv` реализует функционально-логическую верификацию (FLV) программных
> моделей измерительных процессов в составе ИИС. Входы: DSL-спецификация
> методики (YAML) + журнал событий прогона (JSONL). Выход: вердикт с
> детализацией нарушений.

---

## Быстрый старт

```python
from pathlib import Path
from flv.dsl import YamlDslAdapter
from flv.adapters import JsonlAdapter
from flv.matchers import SequenceMatcher, TimingMatcher, PredicateMatcher
from flv.verdict import aggregate
from flv.reporter import render_markdown

# 1. Загрузить спецификацию
spec = YamlDslAdapter().load("02_Спецификация/dsl_v1.yaml")

# 2. Загрузить трассу событий
trace = JsonlAdapter().load("05_Эксперименты/runs/S1-20260505-001.jsonl")

# 3. Запустить все матчеры
matchers = [SequenceMatcher(), TimingMatcher(), PredicateMatcher()]
violations = []
for m in matchers:
    violations.extend(m.match(spec, trace))

# 4. Получить вердикт
verdict = aggregate(violations, run_id=trace.run_id, spec_id=spec.id)

# 5. Вывести отчёт
print(render_markdown(verdict))
print("Статус:", verdict.status)   # VerdictStatus.OK или FAIL
```

---

## CLI

```bash
# Из корня 04_FLV/
python -m flv.cli verify \
    --spec   ../../02_Спецификация/dsl_v1.yaml \
    --log    ../../05_Эксперименты/runs/S1-20260505-001.jsonl \
    --output report.md
```

---

## Архитектура модуля

```
flv/
├── core.py          # Типы данных: Spec, Trace, Event, CheckSpec, ViolationSpec
├── dsl/
│   └── yaml_adapter.py   # DSL-адаптер: YAML → Spec (валидация по JSON Schema)
├── adapters/
│   └── jsonl.py          # Event-log адаптер: JSONL → Trace
├── matchers/
│   ├── base.py           # BaseMatcher (ABC)
│   ├── sequence.py       # SequenceMatcher — порядок и полнота состояний
│   ├── timing.py         # TimingMatcher  — временны́е ограничения
│   └── predicate.py      # PredicateMatcher — гарды переходов, predicates, ranges
├── verdict.py       # Violation, VerdictStatus, aggregate()
├── reporter.py      # render_json(), render_markdown(), write_reports()
└── plugins.py       # Plugin discovery (dsl_adapter / event_adapter / matcher)
```

---

## DSL-спецификация (YAML)

Спецификация описывает нормативную модель методики измерения.
Полная схема — `02_Спецификация/flv_dsl.schema.json`.

```yaml
meta:
  id: S1-temp-stabilization-v1
  version: 1.0

process:
  name: temperature_measurement_with_stabilization

parameters:
  T_set:   { type: float, unit: "°C", default: 150 }
  T_min:   { type: float, unit: "°C", default: 50  }
  delta_stable: { type: float, default: 0.02 }
  t_hold_min:   { type: int,   unit: s, default: 300 }
  N_min:        { type: int,            default: 20  }

states:
  - { name: INIT,    required: true }
  - { name: HEAT,    required: true }
  - { name: HOLD,    required: true }
  - { name: MEASURE, required: true }
  - { name: POST,    required: true }

transitions:
  - { id: t1, from: INIT,    to: HEAT,    guard: "device_ready == True" }
  - { id: t2, from: HEAT,    to: HOLD,    guard: "T >= T_min" }
  - { id: t3, from: HOLD,    to: MEASURE, guard: "abs(dT_dt) <= delta_stable",
      time: { min: 300, max: 600 } }
  - { id: t4, from: MEASURE, to: POST,    guard: "N >= N_min" }

checks:
  - { id: c1, kind: sequence, must_include: [INIT,HEAT,HOLD,MEASURE,POST], must_be_in_order: true }
  - { id: c2, kind: timing,   state: HOLD, min_duration: 300, max_duration: 600 }
  - { id: c3, kind: predicate, when: "state == POST", condition: "N_collected >= N_min" }
  - { id: c4, kind: range,    variable: T_set, min: 30, max: 250 }

violations_catalog:
  SEQ_MISS:  { severity: critical, message: "Пропущен обязательный шаг", related_check: c1 }
  TIME_UNDER: { severity: critical, message: "Длительность меньше минимума", related_check: c2 }
  PRED_FAIL: { severity: critical, message: "Нарушен предикат стабилизации", related_check: c3 }
```

### Валидация DSL без загрузки

```bash
python 02_Спецификация/validate.py 02_Спецификация/dsl_v1.yaml
# [OK]  02_Спецификация/dsl_v1.yaml
```

---

## Формат event-log (JSONL)

Каждая строка — одно событие. Схема: `02_Спецификация/event_log.schema.json`.

```jsonl
{"ts":"2026-05-05T10:00:00.000Z","stand_id":"S1","run_id":"S1-20260505-001","seq":0,"state":"INIT","event":"RUN_START","params":{"_ts_rel_s":0.0,"T_set":150},"signals":{"T":24.0}}
{"ts":"2026-05-05T10:02:00.000Z","stand_id":"S1","run_id":"S1-20260505-001","seq":3,"state":"HEAT","event":"HEAT_END","params":{"_ts_rel_s":120.0},"signals":{"T":50.5}}
```

Ключевые поля:
| Поле | Тип | Описание |
|------|-----|----------|
| `ts` | string (ISO-8601) | Абсолютное UTC-время |
| `stand_id` | string | Идентификатор стенда (S1, S2, …) |
| `run_id` | string | `<STAND>-<YYYYMMDD>-<NNN>` |
| `seq` | int | Порядковый номер события в прогоне |
| `state` | string | Состояние FSM в момент события |
| `event` | string | Имя события (RUN_START, HEAT_END, …) |
| `params` | dict | Параметры процесса + `_ts_rel_s` |
| `signals` | dict | Снимок сигналов (T, dT_dt, …) |

---

## Матчеры

### SequenceMatcher
Проверяет коды `SEQ_MISS` и `SEQ_ORDER`.
- `SEQ_MISS` — обязательное состояние из `checks[kind=sequence].must_include` не встречено в трассе.
- `SEQ_ORDER` — состояния встречены, но не в нормативном порядке.

### TimingMatcher
Проверяет коды `TIME_UNDER` и `TIME_OVER`.
- Вычисляет длительность каждого состояния по `_ts_rel_s` первого и последнего события в нём.
- Сравнивает с `checks[kind=timing].{min_duration, max_duration}`.

### PredicateMatcher
Проверяет коды `PRED_FAIL`, `RANGE_MISM`, `N_TOO_LOW`.
- Для каждого фактического перехода `A→B` ищет гард в спецификации и вычисляет его через `simpleeval`.
- Контекст гарда: defaults из `spec.parameters` + params/signals последнего события в состоянии A.
- Поддерживает алиас `N ↔ N_collected`.

---

## Вердикт и отчёт

```python
from flv.verdict import VerdictStatus, aggregate

verdict = aggregate(violations, run_id="S1-20260505-001", spec_id="S1-v1")
verdict.status        # VerdictStatus.OK | VerdictStatus.FAIL
verdict.violations    # tuple[Violation, ...]
verdict.summary       # {"by_matcher": ..., "by_code": ..., "sequence_ok": ...}
```

```python
from flv.reporter import render_json, render_markdown, write_reports

# Markdown-отчёт
md = render_markdown(verdict)

# JSON-отчёт
js = render_json(verdict)

# Сохранить оба
artifacts = write_reports(
    verdict,
    json_path=Path("report.json"),
    markdown_path=Path("report.md"),
)
```

---

## Benchmark

```bash
cd 04_FLV
python benchmarks/bench_matchers.py
```

Ожидаемый overhead при N=1000 событий: < 10 мс суммарно на все матчеры.

---

## Тесты

```bash
cd 04_FLV
pytest tests/ --override-ini="addopts=" -p no:cov -q
# 26 passed
```

Структура тестов:
- `test_sequence_matcher.py` — SEQ_MISS, SEQ_ORDER
- `test_timing_matcher.py` — TIME_UNDER, TIME_OVER
- `test_predicate_matcher.py` — PRED_FAIL, RANGE_MISM, N_TOO_LOW
- `test_yaml_adapter.py` — DSL-загрузка, валидация, семантические проверки
- `test_jsonl_adapter.py` — загрузка event-log, schema-warnings
- `test_verdict.py` — aggregate(), статус
- `test_e2e_pipeline.py` — интеграционный: correct_run → OK; time_under_run → FAIL
