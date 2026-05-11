# FLV-сертификат соответствия

**Run ID:** `S1-20260512-000`  
**Spec ID:** `S1-temp-stabilization-v1`  
**Verdict:** ❌ FAIL  
**Critical:** 6  
**Warnings:** 0  

## Обнаруженные нарушения

| # | Код | Severity | Matcher | State | Expected | Actual | Location |
|---|---|---|---|---|---|---|---|
| 1 | `PRED_FAIL` | critical | predicate | INIT | {"condition":"device_ready == true"} | {"device_ready":true} | seq=3, t=0.50c |
| 2 | `PRED_FAIL` | critical | predicate | HEAT | {"condition":"T >= T_min"} | {"T_min":50} | seq=13, t=9.70c |
| 3 | `TIME_UNDER` | critical | timing | HOLD | {"min_duration_s":300.0} | {"duration_s":30.000000000000313} | seq=44, t=40.00c |
| 4 | `PRED_FAIL` | critical | predicate | HOLD | {"condition":"abs(dT_dt) <= delta_stable"} | {"delta_stable":0.02,"dT_dt":2.0599679560541224} | seq=45, t=40.00c |
| 5 | `N_TOO_LOW` | critical | predicate | POST | {"condition":"N_collected >= N_min"} | {"N_min":20} | seq=69, t=59.80c |
| 6 | `PRED_FAIL` | critical | predicate | POST | {"condition":"abs(dT_dt) <= delta_stable"} | {"delta_stable":0.02} | seq=69, t=59.80c |

## Детализация

### 1. `PRED_FAIL` — Нарушен предикат стабилизации

- Matcher: `predicate`
- Состояние FSM: `INIT`
- DSL-привязка: `t1_init_to_heat`
- Ожидалось: `{"condition":"device_ready == true"}`
- Фактически: `{"device_ready":true}`
- Событие: seq=`3`, t=0.500 c

### 2. `PRED_FAIL` — Нарушен предикат стабилизации

- Matcher: `predicate`
- Состояние FSM: `HEAT`
- DSL-привязка: `t2_heat_to_hold`
- Ожидалось: `{"condition":"T >= T_min"}`
- Фактически: `{"T_min":50}`
- Событие: seq=`13`, t=9.700 c

### 3. `TIME_UNDER` — Длительность состояния меньше нормативного минимума

- Matcher: `timing`
- Состояние FSM: `HOLD`
- DSL-привязка: `c2_hold_duration`
- Ожидалось: `{"min_duration_s":300.0}`
- Фактически: `{"duration_s":30.000000000000313}`
- Событие: seq=`44`, t=40.000 c

### 4. `PRED_FAIL` — Нарушен предикат стабилизации

- Matcher: `predicate`
- Состояние FSM: `HOLD`
- DSL-привязка: `t3_hold_to_measure`
- Ожидалось: `{"condition":"abs(dT_dt) <= delta_stable"}`
- Фактически: `{"delta_stable":0.02,"dT_dt":2.0599679560541224}`
- Событие: seq=`45`, t=40.000 c

### 5. `N_TOO_LOW` — Недостаточное число отсчётов измерения

- Matcher: `predicate`
- Состояние FSM: `POST`
- DSL-привязка: `c4_n_samples`
- Ожидалось: `{"condition":"N_collected >= N_min"}`
- Фактически: `{"N_min":20}`
- Событие: seq=`69`, t=59.800 c

### 6. `PRED_FAIL` — Нарушен предикат стабилизации

- Matcher: `predicate`
- Состояние FSM: `POST`
- DSL-привязка: `c3_stable_predicate`
- Ожидалось: `{"condition":"abs(dT_dt) <= delta_stable"}`
- Фактически: `{"delta_stable":0.02}`
- Событие: seq=`69`, t=59.800 c

## Сводка

- **by_matcher:** `{'predicate': 5, 'timing': 1}`
- **by_code:** `{'PRED_FAIL': 4, 'N_TOO_LOW': 1, 'TIME_UNDER': 1}`
- **sequence_ok:** `True`
- **timing_ok:** `False`
- **predicates_ok:** `False`
- **source_adapter:** `jsonl`
- **dsl_adapter:** `yaml`
- **n_matchers:** `3`

## Объяснение (LLM)

Прогон признан несоответствующим методике: обнаружено 6 критичных нарушений.
- `PRED_FAIL` (critical, predicate): ожидалось {'condition': 'device_ready == true'}, фактически {'device_ready': True}.
- `PRED_FAIL` (critical, predicate): ожидалось {'condition': 'T >= T_min'}, фактически {'T_min': 50}.
- `TIME_UNDER` (critical, timing): ожидалось {'min_duration_s': 300.0}, фактически {'duration_s': 30.000000000000313}.
- `PRED_FAIL` (critical, predicate): ожидалось {'condition': 'abs(dT_dt) <= delta_stable'}, фактически {'delta_stable': 0.02, 'dT_dt': 2.0599679560541224}.
- `N_TOO_LOW` (critical, predicate): ожидалось {'condition': 'N_collected >= N_min'}, фактически {'N_min': 20}.
- `PRED_FAIL` (critical, predicate): ожидалось {'condition': 'abs(dT_dt) <= delta_stable'}, фактически {'delta_stable': 0.02}.

_Объяснение сформировано по детерминированному шаблону (LLM Роль 3 не задействована или отбракована анти-галл фильтром)._

> _Это объяснение сгенерировано LLM (Роль 3 по ADR-002) и является справочным дополнением к формальному вердикту._
