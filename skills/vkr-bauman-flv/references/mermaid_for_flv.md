# Mermaid для FLV — синтаксис и типовые ошибки v11

Все диаграммы в работе генерируются Mermaid и рендерятся в PNG 300 DPI через `scripts/mermaid_to_png.py`. Источник Mermaid (`*.mmd`) — коммитится; PNG — тоже коммитится для воспроизводимости.

## Когда какой тип диаграммы

| Что показываем | Тип Mermaid |
|---|---|
| Архитектура модуля FLV (компоненты + потоки данных) | `flowchart LR` или `flowchart TD` |
| Контур ИИС с FLV (как FLV встраивается) | `flowchart TD` с `subgraph` |
| Состояния процесса измерения (FSM) | `stateDiagram-v2` |
| Последовательность событий (online verification trace) | `sequenceDiagram` |
| План эксперимента (фазы) | `gantt` |
| Сравнение baseline vs FLV | `flowchart TB` с двумя `subgraph` |

## Типовые ошибки v11 (фиксим заранее)

1. **Скобки в подписи узла** — Mermaid интерпретирует `(...)` как форму узла. Если в тексте нужны скобки — экранируй: `Узел["Текст (с скобками)"]` (используй квадратные `[]` или фигурные `{}` как обёртку, а внутри — двойные кавычки).
2. **Reserved words в ID узла** — `end`, `default`, `style` нельзя использовать как ID. Префиксуй: `node_end`, `s_default`.
3. **Символы `o`/`x` в начале ID узла** — Mermaid воспринимает их как стрелки, путается. Префиксуй: `n_oversee`.
4. **Точка с запятой в sequence-метках** — экранируй HTML-сущностью: `Алиса->>Боб: foo&#59; bar`.
5. **Комментарий в Mermaid** — `%%`, и обязательно с новой строки.
6. **`---` в frontmatter** — должен быть на 1-й строке файла, без пустых строк до.
7. **Markdown в подписях** — поддержан с v11. `**жирный**` и `_курсив_` работают.
8. **`linkStyle hex-color` — последний аргумент** — порядок имеет значение в v11.
9. **Стрелка без типа `---` в v11.0-11.4** — баг (рендерит без линии). Используй `-->`.

## Шаблоны под наши диаграммы

### 1. Общая схема FLV (для главы 2)

```mermaid
flowchart TD
    A[Нормативная методика<br/>текстовая] --> B[Формальная модель<br/>FSM/Timed Automata + DSL]
    C[Программный сценарий<br/>в составе ИИС] --> D[Сбор событий<br/>event-log JSONL]
    B --> E{Модуль FLV<br/>верификация}
    D --> E
    E -->|OK| F[Протокол принят]
    E -->|FAIL| G[Блокировка/предупреждение<br/>+ отчёт о нарушениях]
```

### 2. FSM измерительного процесса S1 (для главы 2)

```mermaid
stateDiagram-v2
    [*] --> INIT
    INIT --> HEAT: device_ready
    HEAT --> HOLD: T >= T_min
    HOLD --> MEASURE: |dT/dt| <= delta\nи t_hold >= 300
    MEASURE --> POST: N >= N_min
    POST --> [*]
```

### 3. Архитектура модуля FLV (для главы 3)

```mermaid
flowchart LR
    subgraph Input
        SPEC[DSL spec.yaml]
        LOG[event-log.jsonl]
    end
    subgraph Core
        SL[Spec Loader]
        LP[Log Parser]
        SM[Sequence Matcher]
        TM[Timing Matcher]
        PM[Predicate Matcher]
        VA[Verdict Aggregator]
    end
    subgraph Output
        REP[Markdown report]
        JSN[JSON verdict]
    end
    SPEC --> SL
    LOG --> LP
    SL --> SM
    SL --> TM
    SL --> PM
    LP --> SM
    LP --> TM
    LP --> PM
    SM --> VA
    TM --> VA
    PM --> VA
    VA --> REP
    VA --> JSN
```

### 4. Sequence-диаграмма online-режима (для главы 3)

```mermaid
sequenceDiagram
    participant Sim as Симулятор
    participant Log as Event Logger
    participant FLV as FLV Online
    participant UI as ИИС UI
    Sim->>Log: SET_RANGE_OK
    Log->>FLV: stream event
    FLV->>FLV: incremental match
    Sim->>Log: SETTLE_END (t=25c)
    Log->>FLV: stream event
    FLV->>FLV: TIME_UNDER detected
    FLV->>UI: BLOCK + reason
    UI->>Sim: STOP
```

### 5. Календарный план (для введения)

```mermaid
gantt
    title ВКР Катальшов — этапы
    dateFormat  YYYY-MM-DD
    section Сбор материалов
    Phase 1                :p1, 2026-05-04, 6d
    section Реализация
    Phase 2 спецификация   :p2, after p1, 5d
    Phase 3 симулятор      :p3, 2026-05-11, 8d
    Phase 4 модуль FLV     :p4, 2026-05-18, 7d
    section Эксперимент
    Phase 5 эксперименты   :p5, 2026-05-25, 6d
    section Финал
    Phase 6 ПЗ             :p6, 2026-05-30, 12d
    Phase 7 защита         :p7, 2026-06-15, 7d
```

## Рендер в PNG для вставки в ПЗ

```bash
# Установка mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Рендер одной диаграммы
mmdc -i diagram.mmd -o diagram.png -w 1600 -H 900 --backgroundColor white -s 2

# Через наш скрипт-обёртку
python scripts/mermaid_to_png.py 02_Спецификация/architecture.mmd
```

`-s 2` (scale) даёт ~300 DPI на A4. `--backgroundColor white` обязательно — иначе прозрачный фон в Word плохо смотрится.

## Где искать референсы

- Live-editor для проверки синтаксиса: <https://mermaid.live/>
- Полная документация v11: <https://mermaid.js.org/>
- Awesome-skills/mermaid-syntax-skill: <https://github.com/awesome-skills/mermaid-syntax-skill>
