# Архитектура модуля FLV

> Phase 2. Дата: 2026-05-03. Автор: Катальшов Д.А., К2-81Б. Документ описывает программную архитектуру FLV-модуля: компоненты, потоки данных, технические границы. Сопровождается Mermaid-диаграммой `architecture.mmd`. Прямой вход в главу 3 ПЗ и Phase 4 (реализация).

---

## 1. Контекст

Архитектура FLV отражает три ключевых принципа, зафиксированных в ADR-002:

1. **LLM на двух хорошо отграниченных шагах** (роли 1 и 3) — там, где LLM объективно сильнее формальных методов (текст ↔ структура).
2. **Детерминированный matcher** в ядре — там, где требуется юридически воспроизводимый вердикт.
3. **Human-in-the-loop** между ролью 1 и ядром — инженер несёт ответственность за корректность нормативной модели.

См. также `positioning.md` про то, куда модуль встраивается в ИИС.

---

## 2. Высокоуровневая диаграмма

Полная диаграмма — в `architecture.mmd`. Кратко на словах:

```
[Текст методики] ─→ [LLM-extractor] ─→ [Schema valid] ─→ [HITL] ─→ [DSL утв.]
                                                                       │
                                                                       ▼
[Сценарий ИИС] ─→ [Контроллер + Hook] ─→ [event-log.jsonl] ─→ [Log Parser]
                                                                       │
                                                                       ▼
                                              [Sequence + Timing + Predicate Matcher]
                                                                       │
                                                                       ▼
                                                            [Verdict Aggregator]
                                                                       │
                                                                       ▼
                                                  [LLM-explainer + анти-галл фильтр]
                                                                       │
                                                                       ▼
                                                       [FLV-сертификат, архив]
```

---

## 3. Компоненты

### 3.1 LLM-extractor (Роль 1)

**Назначение:** парсит текст методики и формирует YAML-черновик DSL.

**Вход:** фрагмент текста методики (ГОСТ/МИ/ТУ).
**Выход:** YAML-документ с полями `meta`, `process`, `parameters`, `states`, `transitions`, `checks`, `violations_catalog`.

**Реализация (`04_FLV/flv/llm_extractor.py`, Phase 4):**
- API-клиент к **OpenRouter** (https://openrouter.ai) — единая абстракция над моделями. SDK — `openai` (OpenRouter совместим с OpenAI API). Поддерживаемые модели: Gemini Flash 3, GPT 5.4, Claude Sonnet 4.6, DeepSeek V4 Flash, Qwen3.6 Flash; выбор через параметр `model_id`.
- Промпт-шаблон в `02_Спецификация/llm_prompts/role_1_extract_dsl.md` (Phase 2.5, опционально).
- Few-shot examples — известные методики из `01_Источники/03_МГТУ/`.
- Retry на ошибке Schema-валидации (макс 2 попытки, иначе — fallback на ручной ввод).

**Зависимости:** `anthropic`/`openai`/`requests`, `pyyaml`, `jsonschema`.

### 3.2 Schema validator

**Назначение:** проверяет соответствие YAML формату DSL.

**Реализация:** `02_Спецификация/validate.py` (Phase 2). JSON Schema `flv_dsl.schema.json` + семантические проверки (from/to в states, related_check в check ids).

**Поведение:** valid → пропускает в HITL; invalid → возвращает ошибки в LLM-extractor для retry.

### 3.3 Human-in-the-loop (HITL)

**Назначение:** инженер просматривает черновик DSL, утверждает или редактирует.

**Реализация:** в простейшем случае — текстовый редактор + git-commit (DSL коммитится в `02_Спецификация/dsl_<methodology>.yaml`). Для UI-флоу — будущее расширение (Phase 6+).

**Юридическое значение:** именно подпись инженера фиксирует ответственность за корректность модели. LLM черновик не имеет силы без HITL-утверждения.

### 3.4 Spec Loader

**Назначение:** парсит утверждённый DSL и строит внутреннюю FSM-модель.

**Вход:** YAML-файл DSL.
**Выход:** объект FSM-модели в памяти (структуры данных Python: `States`, `Transitions`, `Parameters`, `Checks`, `ViolationsCatalog`).

**Реализация:** `04_FLV/flv/spec_loader.py` (Phase 4). Использует `pyyaml` + повторно `validate.py` для контроля на этапе загрузки.

### 3.5 Контроллер сценария + Hook

**Назначение:** исполняет программный сценарий измерения; параллельно пишет event-log.

**Где живёт:** в составе ИИС, не в FLV. **FLV предоставляет только спецификацию формата** event-log (см. `event_log_format.md`).

**Интеграция:**
- LabVIEW: VI «FLV Hook Logger.vi» с Producer-Consumer паттерном; пишет JSONL в файл или TCP-стрим.
- TestStand: Custom Step Type «FLV Log Event».
- Python: декоратор / контекст-менеджер `@flv_log` оборачивает функции состояний FSM.
- Arduino (для demo-track Wokwi/Velxio): функция `flv_log_event(state, event, params)` пишет в Serial.

### 3.6 Log Parser

**Назначение:** читает JSONL построчно, валидирует по `event_log.schema.json`, нормализует время.

**Вход:** путь к `.jsonl`-файлу или поток.
**Выход:** упорядоченный список событий с относительным временем (от RUN_START в секундах).

**Реализация:** `04_FLV/flv/log_parser.py` (Phase 4).

### 3.7 Matcher pipeline

Три matcher'а работают параллельно (или последовательно — для предсказуемости порядка нарушений в отчёте).

**Sequence Matcher** (`04_FLV/flv/matchers/sequence.py`):
- Реконструирует фактическую последовательность переходов состояний.
- Проверяет `checks[kind=sequence].must_include` и порядок по `transitions`.
- Поднимает SEQ_MISS, SEQ_ORDER.
- Сложность: O(n).

**Timing Matcher** (`04_FLV/flv/matchers/timing.py`):
- Считает фактическую длительность каждого состояния по `<STATE>_START`/`<STATE>_END`.
- Сверяет с `transitions[].time` и `checks[kind=timing]`.
- Поднимает TIME_UNDER, TIME_OVER.
- Сложность: O(n).

**Predicate Matcher** (`04_FLV/flv/matchers/predicate.py`):
- В моменты переходов вычисляет гард-условия и checks-предикаты.
- Использует safe-eval (рекомендуется `simpleeval` или AST-walker с whitelist).
- Поднимает PRED_FAIL, N_TOO_LOW, RANGE_MISM.
- Сложность: O(n × m), где m — число активных предикатов в данный момент.

### 3.8 Verdict Aggregator

**Назначение:** собирает violations от всех matcher'ов; формирует общий вердикт.

**Реализация:** `04_FLV/flv/verdict.py` (Phase 4).

**Логика:**
- Если есть critical → FAIL.
- Иначе если есть warning → OK_WITH_WARNINGS.
- Иначе → OK.

Дополнительно: дедупликация повторяющихся violations, сортировка по `event_seq`.

### 3.9 LLM-explainer (Роль 3)

**Назначение:** превращает машинно-читаемый verdict в человеко-читаемое объяснение со ссылками на пункты нормативки.

**Вход:** verdict (JSON) + DSL + соответствующий фрагмент event-log + текст методики.
**Выход:** Markdown-фрагмент с объяснением.

**Реализация:** `04_FLV/flv/llm_explainer.py` (Phase 4). Промпт-шаблон в `02_Спецификация/llm_prompts/role_3_explain_verdict.md` (опционально).

**Защита от галлюцинаций:**
- Все числовые факты обязаны быть процитированы из verdict / event-log (анти-галл фильтр на уровне regex или structured-output).
- Если объяснение содержит число, не присутствующее во входных данных — fallback на детерминированный шаблон.

### 3.10 Анти-галл фильтр

**Назначение:** проверяет, что LLM-объяснение не содержит выдуманных фактов.

**Реализация:** `04_FLV/flv/anti_hallucination.py` (Phase 4).

**Алгоритм:**
1. Извлечь все числа и идентификаторы из объяснения.
2. Сопоставить с числами из verdict, event-log, DSL.
3. Если находится якорь, не подтверждённый источниками — поднять флаг и заменить объяснение на детерминированный шаблон.

### 3.11 Reporter

**Назначение:** формирует финальный FLV-сертификат — машинно-читаемый JSON и Markdown-приложение.

**Реализация:** `04_FLV/flv/reporter.py` (Phase 4).

**Выход:**
- `verdict.json` — структурированный вердикт + violations.
- `verdict.md` — отчёт с объяснениями.
- (опционально) PDF-сертификат через pandoc для архива.

---

## 4. Интерфейсы и контракты

### 4.1 CLI

```bash
# Извлечь DSL из текста методики
flv extract --text methodology.txt --out spec.yaml

# Валидация DSL
flv validate --spec spec.yaml

# Полная проверка лога
flv check --spec spec.yaml --log run.jsonl --report verdict.md --json verdict.json

# Online-режим (post-defense)
flv online --spec spec.yaml --port 9001
```

### 4.2 Python API

```python
from flv import FLV

flv = FLV.load_spec("dsl_v1.yaml")
verdict = flv.check_log("run.jsonl")
print(verdict.summary())  # OK / FAIL + список violations
flv.report(verdict, output="verdict.md")
```

### 4.3 Server API (post-defense, опционально)

REST/gRPC сервис для интеграции с ИИС:
- `POST /spec` — загрузить DSL.
- `POST /check` — отправить event-log, получить verdict.
- `POST /event` — потоковое поступление событий (online mode).

---

## 5. Зависимости

### 5.1 Python

```toml
[project]
dependencies = [
  "pyyaml>=6.0",
  "jsonschema>=4.0",
  "simpleeval>=0.9",
  "click>=8.1",
  "rich>=13.0",
  "openai>=1.0",       # SDK совместим с OpenRouter API; используется для LLM-extractor / explainer
  "pydantic>=2.0",     # для structured output LLM
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov", "ruff", "mypy"]
docs = ["sphinx", "sphinx-rtd-theme"]
```

### 5.2 Внешние

- LLM-провайдер: **OpenRouter** как единая абстракция; для эксперимента Phase 5 фиксируется пятёрка моделей: Gemini Flash 3, GPT 5.4, Claude Sonnet 4.6, DeepSeek V4 Flash, Qwen3.6 Flash. Версии моделей замораживаются на дату старта Phase 5 и логируются.
- (опционально) pandoc для PDF-отчётов.

---

## 6. Тесты

См. план Phase 4. Цель: pytest coverage ≥ 80%.

| Уровень | Что покрывает |
|---|---|
| Unit | Каждый matcher отдельно на синтетических логах. |
| Integration | Полная связка spec_loader → log_parser → matchers → aggregator → reporter. |
| LLM (опц.) | Качество извлечения DSL на 5-7 эталонных методиках (precision/recall ≥ 0.85). |
| Bench | overhead < 100 мс на 10 000 событий. |

---

## 7. Безопасность и устойчивость

- **Eval-инъекции:** в predicate matcher используется `simpleeval` или AST-walker с whitelist; запрещены вызовы функций, импорты, атрибуты dunder.
- **Размер event-log:** ограничен (по умолчанию 1 GB / прогон). Защита от DoS через большие логи.
- **LLM availability:** при недоступности LLM Роль 1 fallback на ручной ввод DSL; Роль 3 fallback на детерминированный шаблон объяснения.
- **Воспроизводимость:** matcher pipeline детерминирован при фиксированных DSL и event-log. LLM-роли логируют seed/temperature/version модели.

---

## 8. Развёртывание

| Уровень | Состав |
|---|---|
| **Локальная разработка** | Python venv + pip install -e .; LLM через API; пример прогона с симулятором Phase 3. |
| **Лабораторное использование** | Docker-контейнер с FLV-CLI; интеграция через файловый интерфейс с LabVIEW Hook Logger. |
| **Production-ИИС (post-defense)** | gRPC-сервис; OpenRouter с резервом on-prem-моделей; шифрование event-log; tamper-proof архив. |

---

## 9. Связь с фазами проекта

| Файл | Реализация в фазе |
|---|---|
| `02_Спецификация/dsl_v1.yaml` | Phase 2 (готово) |
| `02_Спецификация/flv_dsl.schema.json` | Phase 2 (готово) |
| `02_Спецификация/event_log_format.md` + Schema | Phase 2 (готово) |
| `02_Спецификация/formal_model.md` | Phase 2 (готово) |
| `02_Спецификация/violations_catalog.md` | Phase 2 (готово) |
| `02_Спецификация/architecture.md` (этот файл) | Phase 2 (готово) |
| `02_Спецификация/llm_prompts/role_*.md` | Phase 2.5 (по необходимости) |
| `04_FLV/flv/spec_loader.py` | Phase 4 |
| `04_FLV/flv/log_parser.py` | Phase 4 |
| `04_FLV/flv/matchers/{sequence,timing,predicate}.py` | Phase 4 |
| `04_FLV/flv/verdict.py` | Phase 4 |
| `04_FLV/flv/llm_extractor.py` | Phase 4 |
| `04_FLV/flv/llm_explainer.py` | Phase 4 |
| `04_FLV/flv/anti_hallucination.py` | Phase 4 |
| `04_FLV/flv/reporter.py` | Phase 4 |
| `04_FLV/flv/__main__.py` (CLI) | Phase 4 |
