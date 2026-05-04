# ADR-004 — FLV как pluggable-фреймворк универсальной верификации

> Дата: 2026-05-04. Статус: principal direction. Применяется в Phase 4-7.

## Контекст

В исходной постановке Phase 4 (`02_Спецификация/architecture.md`) модуль FLV
проектировался как самодостаточная программа: один формат event-log
(JSONL), один способ описания методики (YAML-DSL), один matcher pipeline,
один источник трасс (наш Python-симулятор стенда S1). Этот подход работает
для бакалаврской ВКР, но в обсуждении с автором поднят более амбициозный
вопрос: можно ли построить FLV так, чтобы метод универсально подключался к
**разным** ИИС — LabVIEW VI, TestStand, Python-стек, прошивки
микроконтроллеров, SCADA-системы — без переписывания ядра?

Этот ADR фиксирует архитектурное решение: **FLV проектируется как
pluggable-фреймворк** с четырьмя точками расширения. Это даёт работу
больший научный вес (методология + фреймворк масштабируется на любые
ИИС), упрощает потенциальную публикацию и индустриальное применение и
лучше соответствует тому, как реальные runtime-verification-системы
(RTAMT, Breach, MOP) проектируются в академической литературе.

## Решение — четыре точки расширения

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FLV-CORE (стабильное ядро)                   │
│                                                                      │
│   abstract Spec ── abstract Trace ── abstract Matcher ── Verdict     │
│                                                                      │
└────┬───────────────┬──────────────────┬───────────────┬──────────────┘
     │               │                  │               │
     │ DSL adapter   │ Source adapter   │ Matcher       │ LLM provider
     │ (как описан-  │ (откуда трасса)  │ (что прове-   │ (роли 1, 3)
     │  метод)       │                  │  ряем)        │
     ▼               ▼                  ▼               ▼
  flv.dsl.yaml   flv.adapters.jsonl  flv.matchers.    flv.llm.openrouter
  flv.dsl.rtamt  flv.adapters.labview  sequence       flv.llm.anthropic
  (расш.)        flv.adapters.scpi    timing          flv.llm.onprem
                 flv.adapters.serial  predicate       (расш.)
                 flv.adapters.otel    stl (опц.)
```

### 1. Source adapters — откуда берём трассу

**Назначение:** преобразовать поток событий из конкретной ИИС в единый
внутренний формат `Trace` (последовательность типизированных `Event`).

**Контракт:** интерфейс `SourceAdapter` (Protocol) с методом
`iter_events() -> Iterator[Event]`.

**Реализации:**

| Адаптер | Что подключает |
|---|---|
| `flv.adapters.jsonl.JsonlAdapter` | Наш формат JSONL Phase 2 (по умолчанию) |
| `flv.adapters.labview.LabVIEWVIAdapter` | TDMS / TDM-файлы LabVIEW + log из Hook VI |
| `flv.adapters.teststand.TestStandAdapter` | XML-отчёты NI TestStand |
| `flv.adapters.serial.SerialAdapter` | Serial-стрим Arduino/ESP32 (для Wokwi/Velxio) |
| `flv.adapters.scpi.ScpiAdapter` | Команды SCPI/VISA с timestamps |
| `flv.adapters.otel.OpenTelemetryAdapter` | OpenTelemetry-spans из современной observability-стек |

В Phase 4 реализуется только `jsonl`. Остальные — заглушки + примеры
для главы 3 ПЗ как «доказательство переносимости».

### 2. DSL adapters — как описана методика

**Назначение:** загрузить нормативную модель и собрать внутреннее
представление `Spec` (FSM + параметры + checks).

**Контракт:** `DslAdapter.load(path: Path) -> Spec`.

**Реализации:**

| Адаптер | Формат DSL |
|---|---|
| `flv.dsl.yaml.YamlDslAdapter` | Наш YAML по `02_Спецификация/flv_dsl.schema.json` |
| `flv.dsl.rtamt.RtamtAdapter` | STL/MTL-выражения через RTAMT-нотацию |
| `flv.dsl.sysml.SysmlAdapter` | OMG SysML state-machine (заглушка для будущего) |

В Phase 4 реализуется только `yaml`. RTAMT-адаптер — отдельный
расширительный пакет, демонстрационный пример в главе 3 ПЗ.

### 3. Matchers — что проверяем

**Назначение:** на основе `Spec` и `Trace` поднимать `Violation`-объекты.

**Контракт:** `BaseMatcher.match(spec: Spec, trace: Trace) -> Iterable[Violation]`.

**Реализации (встроенные):**

* `flv.matchers.sequence.SequenceMatcher` — SEQ_MISS, SEQ_ORDER.
* `flv.matchers.timing.TimingMatcher` — TIME_UNDER, TIME_OVER.
* `flv.matchers.predicate.PredicateMatcher` — PRED_FAIL, RANGE_MISM, N_TOO_LOW.

**Расширение (опционально):**

* `flv.matchers.stl.StlMatcher` — обёртка над RTAMT для STL-свойств
  непрерывных сигналов. Подключается, если установлен `flv[stl]`.

Сторонние команды могут публиковать новые matcher'ы как отдельные
PyPI-пакеты с записью в `[project.entry-points."flv.matcher"]`.

### 4. LLM providers — Роли 1 и 3

**Назначение:** изолированный API-вызов к LLM с поддержкой нескольких
провайдеров; ядро не зависит от конкретного API.

**Контракт:** `LlmProvider.complete(prompt: str, response_model: type[BaseModel]) -> BaseModel`.

**Реализации:**

| Провайдер | Что обёртывает |
|---|---|
| `flv.llm.openrouter.OpenRouterProvider` | OpenRouter API → 5 моделей (Gemini Flash 3, GPT 5.4, Claude Sonnet 4.6, DeepSeek V4 Flash, Qwen3.6 Flash) |
| `flv.llm.anthropic.AnthropicProvider` | Прямой Claude API (для контрольных бенчмарков) |
| `flv.llm.openai.OpenAIProvider` | Прямой OpenAI API |
| `flv.llm.onprem.LocalLlamaProvider` | Локальная Llama / Yandex GPT (для production-ИИС с ограничением на отправку данных вовне) |

В Phase 4 реализуется `openrouter` как основной + `mock` для тестов.
Остальные — заглушки.

## Plugin-механизм — Python entry-points

Классический Python-механизм через `[project.entry-points]` в
`pyproject.toml`:

```toml
[project.entry-points."flv.matcher"]
sequence = "flv.matchers.sequence:SequenceMatcher"
timing = "flv.matchers.timing:TimingMatcher"
predicate = "flv.matchers.predicate:PredicateMatcher"

[project.entry-points."flv.source_adapter"]
jsonl = "flv.adapters.jsonl:JsonlAdapter"

[project.entry-points."flv.dsl_adapter"]
yaml = "flv.dsl.yaml:YamlDslAdapter"

[project.entry-points."flv.llm_provider"]
openrouter = "flv.llm.openrouter:OpenRouterProvider"
mock = "flv.llm.mock:MockProvider"
```

Сторонний пакет (например, `flv-labview-adapter`) при установке
автоматически становится доступен через `pkg_resources` /
`importlib.metadata.entry_points`. CLI обнаруживает его в реестре и
позволяет указать через флаг `--source labview`.

## Чем работа усиливается

1. **Научно.** Это уже не «один скрипт под один стенд», а универсальный
   метод runtime-верификации измерительных протоколов с механизмом
   расширения. Прямой пункт научной новизны для введения ВКР.

2. **Практически.** Подключение к реальной ИИС лаборатории МГТУ — это
   написание одного адаптера, не переписывание ядра. Это можно
   зафиксировать как «перспективы дальнейших работ» в заключении.

3. **Сравнение с аналогами.** В таблице раздела 1.3 ПЗ FLV получает
   уникальное свойство «pluggable framework», которого нет ни у
   RTAMT (только STL), ни у TestStand SA (только статика), ни у
   UPPAAL (только design-time).

## Совместимость с уже сделанным

Изменения **не затрагивают** Phase 1-3:

* DSL Phase 2 (`flv_dsl.schema.json`) остаётся как контракт между
  YAML-адаптером и ядром.
* Формат event-log JSONL Phase 2 — контракт между JSONL-адаптером и
  ядром.
* Симулятор Phase 3 пишет JSONL — он автоматически интегрируется с
  фреймворком через `JsonlAdapter`, ничего не нужно менять.
* Матчеры Phase 4 рождаются сразу как реализации `BaseMatcher` — не
  переделываются после введения plugin-механизма.

## Стратегия реализации

В Phase 4 делаем core-API (абстрактные классы / Protocols) +
встроенные реализации (jsonl, yaml, sequence, timing, predicate,
openrouter, mock). Stub-адаптеры и расширения (rtamt, labview,
teststand, scpi, serial, otel) — заглушками с docstring и
NotImplementedError; их полноценная реализация — post-defense, в
качестве «демонстрации переносимости» в главе 3.

CLI расширяется флагом `--source` / `--dsl` / `--llm`, по умолчанию
выбирает встроенные реализации.

## Открытые вопросы

* [ ] Стоит ли FLV-фреймворк публиковать как отдельный open-source
  пакет на PyPI после защиты — сейчас архитектура к этому готова, но
  решение принимается после ВКР.
* [ ] Согласовать с научруком позиционирование FLV как фреймворка —
  это меняет акценты в главе 1 (новизна) и заключении (перспективы).

## Ссылки

* Bartocci E. et al. «Lectures on Runtime Verification» (2018) — обзор
  подходов к pluggable RV.
* Python Packaging Authority — entry-points specification.
* RTAMT (Nickovic 2020) — пример pluggable RV для STL.
