# 03_Симулятор

Python-симулятор измерительного стенда + 3D-визуализация + каталог сценариев и инъекций нарушений (Phase 3).

## Структура

- `sim/` — модули симулятора:
  - `thermal_model.py` — физическая модель S1 (теплопередача 1-го порядка с шумом и квантованием).
  - `sensor.py` — виртуальный PT100 + АЦП + драйвер.
  - `scenario_runner.py` — FSM-исполнитель сценария.
  - `injector.py` — инжектор нарушений (7 кодов).
  - `event_logger.py` — JSONL-логирование согласно схеме Phase 2.
  - `scpi_mock.py` — (опционально) S2 SCPI-симулятор.
- `viz/` — 3D-визуализация (Three.js HTML или matplotlib-fallback).
- `scenarios/` — YAML-сценарии (эталон + 7 инъекций).
- `tests/` — pytest-юниты на физмодель и инжектор.
- `cli.py` — точка входа: `python -m sim.run --scenario s1_correct.yaml --inject TIME_UNDER --seed 42`.

## Запуск (после реализации)

```bash
cd 03_Симулятор
pip install -r requirements.txt
python -m sim.run --scenario scenarios/s1_correct.yaml --output ../05_Эксперименты/runs/test.jsonl
```

## Принципы

- Симулятор детерминирован при фиксированном seed.
- Все физические параметры (τ, σ, δ, T_min, t_hold_min, N_min) собраны в `sim/config.py`.
- Логи пишутся в формате Phase 2 (JSONL).
