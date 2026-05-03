# Каталог нарушений FLV

> Phase 2. Дата: 2026-05-03. Автор: Катальшов Д.А., К2-81Б. Документ описывает 7 кодов нарушений, обнаруживаемых FLV-модулем, с примерами событий-нарушителей и привязкой к нормативке. Прямой вход в главу 2 ПЗ (раздел 2.5) и в Phase 3 (каталог инъекций сценариев).

---

## 1. Структура записи нарушения

Каждое обнаруженное нарушение FLV-модулем фиксируется в JSON-структуре:

```json
{
  "code": "TIME_UNDER",
  "severity": "critical",
  "matcher": "timing",
  "state": "HOLD",
  "expected": {"min_duration": 300, "unit": "s"},
  "actual": {"duration": 30, "unit": "s"},
  "location": {"event_seq": 343, "ts": "2026-05-03T11:01:04.700Z"},
  "spec_ref": "transition t3_hold_to_measure",
  "norm_ref": "ГОСТ Р 8.563-2009, п. 4.5"
}
```

Поля:

- `code` — код нарушения из таблицы §2.
- `severity` — `critical` | `warning` | `info`.
- `matcher` — какой matcher обнаружил (`sequence`, `timing`, `predicate`, `range`).
- `state` — состояние, где обнаружено.
- `expected` / `actual` — пара «что требовалось / что наблюдалось» с числами и единицами.
- `location` — указатель на событие в трассе (`event_seq`, `ts`).
- `spec_ref` — идентификатор элемента DSL (transition.id или check.id).
- `norm_ref` — ссылка на пункт нормативного документа (опционально).

---

## 2. Каталог кодов

### 2.1 SEQ_MISS — Пропуск обязательного шага

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `sequence` |
| Какое условие нарушено | §4.1 формальной модели — структурное условие приёма |
| DSL-привязка | `checks[kind=sequence].must_include` |
| Типичный сценарий | Прогон, в котором не было состояния HOLD (пропуск выдержки) |
| Пример проявления в трассе | `RUN_START → INIT_END → HEAT_START → HEAT_END → MEAS_START` (нет HOLD_START / HOLD_END) |
| Поля `expected` / `actual` | `{"required_states": [INIT, HEAT, HOLD, MEASURE, POST]}` / `{"observed_states": [INIT, HEAT, MEASURE, POST]}` |

**Пример отчёта:**

> Состояние HOLD обязательно по DSL-спецификации (s1-temp-stabilization-v1, checks.c1_sequence.must_include). В трассе оно отсутствует. По ГОСТ Р 8.563-2009 (п. 4.5) выдержка перед измерением является обязательной частью методики; пропуск выдержки приводит к недостоверности результата.

### 2.2 SEQ_ORDER — Нарушение порядка переходов

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `sequence` |
| Какое условие нарушено | §4.1 — структурное условие, требование «по 𝒯» |
| DSL-привязка | `transitions[]` |
| Типичный сценарий | MEASURE начат до завершения HOLD; HOLD после POST |
| Пример | `HEAT_END → MEAS_START → HOLD_START` (MEASURE раньше HOLD) |
| Поля | `{"expected_after": "HOLD_END"}` / `{"observed_predecessor": "HEAT_END"}` |

### 2.3 TIME_UNDER — Недостаточная длительность состояния

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `timing` |
| Условие | §4.2 — t_min ≤ d |
| DSL | `transitions[].time.min` или `checks[kind=timing].min_duration` |
| Типичный сценарий | t_hold = 30 с вместо ≥ 300 с |
| Пример | HOLD_START в τ=154.7 с, HOLD_END в τ=184.7 с (длит. 30 с при `min_duration: 300`) |
| Поля | `{"min_duration": 300, "unit": "s"}` / `{"duration": 30, "unit": "s"}` |

### 2.4 TIME_OVER — Превышение допустимой длительности состояния

| Поле | Значение |
|---|---|
| Severity | `warning` |
| Matcher | `timing` |
| Условие | §4.2 — d ≤ t_max |
| DSL | `transitions[].time.max` или `checks[kind=timing].max_duration` |
| Типичный сценарий | HOLD затягивается до 700 с при максимуме 600 |
| Пример | HOLD длительностью 720 с при `max_duration: 600` |
| Поля | `{"max_duration": 600, "unit": "s"}` / `{"duration": 720, "unit": "s"}` |

> Severity = warning (не critical), потому что превышение длительности обычно не делает результат **недостоверным**, но требует внимания: возможно, оборудование работает медленнее ожидаемого, либо превышен бюджет ресурса.

### 2.5 PRED_FAIL — Не выполнен предикат стабилизации/гарда

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `predicate` |
| Условие | §4.3 — p(π ∪ ν) = true в момент перехода |
| DSL | `transitions[].guard`, `checks[kind=predicate].condition` |
| Типичный сценарий | Переход HOLD→MEASURE при |dT/dt| = 0.045 (не ≤ 0.02) |
| Пример | в HOLD_END: `dT_dt = 0.045`, гард `abs(dT_dt) <= 0.02` не выполнен |
| Поля | `{"condition": "abs(dT_dt) <= 0.02"}` / `{"dT_dt": 0.045}` |

### 2.6 N_TOO_LOW — Недостаточное число отсчётов

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `predicate` |
| Условие | §4.3 — `N >= N_min` |
| DSL | `parameters.N_min`, `checks[kind=predicate].condition` с `N_collected >= N_min` |
| Типичный сценарий | В MEASURE собрано 5 отсчётов вместо 20 минимум |
| Пример | 5 событий MEAS_TICK + MEAS_END при `N_min: 20` |
| Поля | `{"N_min": 20}` / `{"N_collected": 5}` |

> Эта проверка прямо ссылается на ГОСТ 8.207-76 (п. 4.1 — обработка результатов прямых измерений с многократными наблюдениями требует n ≥ 4 для применимости статистических методов; для нашей методики устанавливаем более жёсткий минимум N_min = 20).

### 2.7 RANGE_MISM — Параметр процесса вне допустимого диапазона

| Поле | Значение |
|---|---|
| Severity | `critical` |
| Matcher | `range` |
| Условие | значение параметра в [min; max] |
| DSL | `checks[kind=range]`, `parameters[].min/max` |
| Типичный сценарий | T_set = 700 °C при `T_set_max: 250 °C` |
| Пример | в RUN_START: `params.T_set = 700` при `parameters.T_set.max = 250` |
| Поля | `{"variable": "T_set", "max": 250}` / `{"value": 700}` |

> Это нарушение часто катастрофично — выход параметра за границы безопасной работы оборудования. На реальном стенде должна срабатывать аппаратная защита; FLV дополнительно фиксирует факт попытки.

---

## 3. Сводная таблица

| Код | Severity | Matcher | Где сработает на S1 | DSL-якорь |
|---|---|---|---|---|
| SEQ_MISS | critical | sequence | пропуск любого из {INIT, HEAT, HOLD, MEASURE, POST} | c1_sequence.must_include |
| SEQ_ORDER | critical | sequence | MEASURE раньше HOLD; HOLD после POST | t1_init_to_heat … t4_measure_to_post |
| TIME_UNDER | critical | timing | t_hold < 300 с | t3_hold_to_measure.time.min |
| TIME_OVER | warning | timing | t_hold > 600 с | t3_hold_to_measure.time.max |
| PRED_FAIL | critical | predicate | переход HOLD→MEASURE при `\|dT_dt\| > 0.02` | t3_hold_to_measure.guard, c3_stable_predicate |
| N_TOO_LOW | critical | predicate | N_collected < 20 | c4_n_samples |
| RANGE_MISM | critical | range | T_set вне [30; 250] | c5_temperature_range |

---

## 4. Жизненный цикл нарушения в FLV-pipeline

```
1. Matcher (sequence/timing/predicate/range) обнаруживает рассогласование
   между трассой и DSL.
2. Формирует структуру violation (см. §1).
3. Aggregator собирает все violations прогона, группирует по severity.
4. Если есть critical → verdict = FAIL, прогон отвергается.
   Если только warning → verdict = OK_WITH_WARNINGS, прогон принят с
     отметкой.
   Если ничего → verdict = OK.
5. LLM-постпроцессор (Роль 3, см. ADR-002) формирует human-readable
   объяснение с привязкой к ГОСТ.
6. Reporter сериализует verdict в JSON + Markdown.
7. В архив прогона прикрепляется FLV-сертификат с привязкой violations
   к пунктам нормативного документа.
```

---

## 5. Связь с инъекциями Phase 3

Каталог инъекций в Phase 3 (`03_Симулятор/scenarios/`) построен как 1-в-1 соответствие нашему каталогу нарушений. Это даёт прямую возможность проверки покрытия FLV-метода: на каждый код 𝒥 — отдельный сценарий-инъекция, и FLV должен корректно его детектировать.

| Сценарий-инъекция | Код нарушения, который должен сработать |
|---|---|
| `s1_correct.yaml` | (пусто, OK) |
| `s1_seq_miss.yaml` | SEQ_MISS |
| `s1_seq_order.yaml` | SEQ_ORDER |
| `s1_time_under.yaml` | TIME_UNDER |
| `s1_time_over.yaml` | TIME_OVER |
| `s1_pred_fail.yaml` | PRED_FAIL |
| `s1_n_too_low.yaml` | N_TOO_LOW |
| `s1_range_mism.yaml` | RANGE_MISM |

В Phase 5 эта таблица превращается в confusion matrix через метрики TPR/FPR (см. `references/statistical_analysis_flv.md` в скилле).

---

## 6. Принципы расширения каталога

При добавлении новой методики (другой стенд, другой класс измерений) могут потребоваться новые коды нарушений. Принципы:

1. Имя кода — UPPER_SNAKE_CASE.
2. Привязка обязательна к одному из 4 matcher'ов (sequence/timing/predicate/range) или, в крайнем случае, новому matcher'у с обоснованием.
3. Severity выбирается по принципу: «делает ли это нарушение результат измерения недостоверным?» Да → critical; нет → warning.
4. Для каждого нового кода — пример сценария-инъекции и пример события-нарушителя в `event_log_format.md`.
5. Привязка к пункту ГОСТ/МИ (если есть) — обязательна.

Пример новых кодов для будущих стендов:
- `SCPI_NO_OPC` — отсутствие `*OPC?` после команды управления (для S2 SCPI-стенда).
- `SETTLE_BAD` — измерение начато до завершения settling-окна.
- `RANGE_NOT_SET` — измерение начато без установки диапазона `SET_RANGE`.
