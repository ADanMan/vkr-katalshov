# 03_Симулятор — стенд S1 (термокамера со стабилизацией PT100)

Python-симулятор измерительного стенда для ВКР Катальшова Д.А., К2-81Б.
Архитектура — `02_Спецификация/simulator_arch.md`. Инженерный стек —
`99_Артефакты/ADR_003_simulator_engineering_stack.md`.

## Установка

```bash
cd 03_Симулятор
python -m venv .venv
source .venv/bin/activate                    # Linux / Mac
pip install -e ".[viz3d,dashboard,plots,dev]"
```

Минимальная установка без интерактивной 3D и дашборда:

```bash
pip install -e .
```

## Быстрый старт

```bash
# Эталонный прогон (без нарушений)
sim run --scenario scenarios/s1_correct.yaml \
        --output ../05_Эксперименты/runs/correct-001.jsonl \
        --seed 42

# Прогон с инъекцией нарушения «недостаточная выдержка»
sim run --scenario scenarios/s1_time_under.yaml \
        --output ../05_Эксперименты/runs/inj-001.jsonl \
        --seed 42

# Серия из 50 прогонов с разными seed
sim run --scenario scenarios/s1_correct.yaml \
        --batch 50 --seed-base 1000 \
        --output-dir ../05_Эксперименты/runs/
```

## Интерактивные view

### 1. 3D-сцена термокамеры (pyvista + trame)

```bash
python -m viz.3d_pyvista --run ../05_Эксперименты/runs/correct-001.jsonl
# открывает http://localhost:8080
```

Куб (камера) с прозрачными стенками, цилиндр-образец, цвет которого
меняется от температуры (синий → красный). Слайдер времени, поворот,
зум. Скриншот — кнопка «Save snapshot» для PNG в ПЗ.

### 2. FLV Dashboard (Plotly Dash)

```bash
python -m viz.dashboard_dash --run ../05_Эксперименты/runs/correct-001.jsonl
# открывает http://127.0.0.1:8050
```

Live-чарт T(t), индикатор текущего FSM-состояния, таблица
обнаруженных FLV-нарушений (после Phase 4 — будет вызывать
FLV-модуль). Полезно как «вживую» демо на защите.

## Структура

```
sim/                  пакет симулятора
├── config.py         все физические параметры через pint
├── thermal_model.py  ODE через scipy.integrate.solve_ivp
├── uncertainty_model.py propagation погрешностей через uncertainties
├── sensor.py         PT100 (ГОСТ 6651) + АЦП
├── control_loop.py   PID через python-control + Bode
├── scenario_runner.py FSM на simpy
├── injector.py       7 типов нарушений
└── event_logger.py   JSONL по формату Phase 2

viz/                  визуализация
├── 3d_pyvista.py     3D-сцена в браузере
├── dashboard_dash.py Plotly Dash
└── plot_static.py    matplotlib + seaborn (для PNG в ПЗ)

scenarios/            YAML-сценарии (эталон + 7 инъекций)
tests/                pytest юниты
cli.py                CLI entry-point
```

## Тесты

```bash
pytest                              # все тесты + coverage
pytest tests/test_thermal.py        # один модуль
pytest --cov=sim --cov-report=html  # HTML-отчёт по покрытию
```

Цель: coverage ≥ 80 % по модулям пакета `sim`.

## Воспроизводимость

* Все случайные процессы (шум сенсора, шум АЦП, внутренние
  флуктуации) параметризованы единым `--seed`.
* В каждый event-log пишется `meta.simulator_version`,
  `meta.scenario_file_sha`, `meta.seed` — повторный запуск с теми
  же параметрами даёт идентичный лог.
* Метаданные прогонов — в `runs/_metadata.csv`.

## Зависимости

См. `pyproject.toml`. Ключевые — scipy, simpy, pint, uncertainties,
control. Опционально — pyvista+trame (3D), plotly+dash (dashboard),
matplotlib+seaborn (статика для ПЗ).
