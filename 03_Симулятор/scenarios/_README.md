# scenarios/ — каталог YAML-сценариев симулятора S1

Каждый файл описывает один прогон. Эталон + 7 инъекций — по одной
на каждый код нарушения из `02_Спецификация/violations_catalog.md`.

Формат сценария (общий):

```yaml
id: <уникальный идентификатор>            # совпадает с именем файла без .yaml
description: <человеко-читаемое описание>
based_on: dsl_v1.yaml                      # ссылка на DSL Phase 2
inject:
  code: NONE | SEQ_MISS | SEQ_ORDER | TIME_UNDER | TIME_OVER |
        PRED_FAIL | N_TOO_LOW | RANGE_MISM
expected_violation: <тот же код или (none) для NONE>
overrides:
  # Любые поля ScenarioParams могут быть переопределены здесь.
  # Например:
  # T_set_C: 200
  # n_min: 50
```

CLI читает сценарий, прокидывает overrides в ScenarioParams и
поднимает соответствующий InjectionSpec из `sim.injector.INJECTIONS`.

## Файлы

| Файл | Код | Что воспроизводит |
|---|---|---|
| `s1_correct.yaml` | NONE | Эталонный прогон без нарушений |
| `s1_seq_miss.yaml` | SEQ_MISS | Пропуск состояния HOLD |
| `s1_seq_order.yaml` | SEQ_ORDER | MEASURE раньше HOLD |
| `s1_time_under.yaml` | TIME_UNDER | HOLD = 30 c (норматив ≥ 300 c) |
| `s1_time_over.yaml` | TIME_OVER | HOLD = 700 c (норматив ≤ 600 c) |
| `s1_pred_fail.yaml` | PRED_FAIL | Выход из HOLD при `\|dT/dt\| = 0.045` |
| `s1_n_too_low.yaml` | N_TOO_LOW | 5 отсчётов в MEASURE (норматив ≥ 20) |
| `s1_range_mism.yaml` | RANGE_MISM | T_set = 700 °C (предел камеры 250 °C) |
