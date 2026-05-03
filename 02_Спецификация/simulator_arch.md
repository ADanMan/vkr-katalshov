# Архитектура симулятора стенда S1

> Phase 2 → Phase 3. Дата: 2026-05-03. Автор: Катальшов Д.А., К2-81Б. Документ описывает архитектуру Python-симулятора, который генерирует event-log для FLV-модуля. Прямой вход в Phase 3 (реализация).

---

## 1. Назначение

Симулятор воспроизводит работу реального измерительного стенда S1 (термокамера со стабилизацией PT100) и пишет event-log в формате Phase 2 (`event_log_format.md`). Используется как:

1. Источник трасс для Phase 5 (100+ прогонов с инъекциями нарушений).
2. Демонстрация в Phase 7 (запись прогонов на защите).
3. Эталонная проверка FLV-модуля Phase 4 (известные ground-truth трассы).

Принцип: **детерминированность + физическая реалистичность**. При фиксированном seed прогон полностью воспроизводим; при этом физическая модель опирается на ГОСТ 6651-2009 (PT100), типовые параметры лабораторных термокамер, гауссовский шум сенсора, квантование 16-битного АЦП.

---

## 2. Структура пакета

```
03_Симулятор/
├── sim/
│   ├── __init__.py
│   ├── config.py             ← все физические параметры в одном месте
│   ├── thermal_model.py      ← ODE 1-го порядка (теплопередача)
│   ├── sensor.py             ← PT100 + квантование АЦП + шум
│   ├── scenario_runner.py    ← FSM-исполнитель методики
│   ├── injector.py           ← модификации для 7 кодов нарушений
│   └── event_logger.py       ← запись в JSONL по формату Phase 2
├── viz/
│   ├── 3d_view.html          ← Three.js визуализация
│   └── plot_run.py           ← matplotlib-fallback
├── scenarios/
│   ├── s1_correct.yaml       ← эталон
│   ├── s1_seq_miss.yaml
│   ├── s1_seq_order.yaml
│   ├── s1_time_under.yaml
│   ├── s1_time_over.yaml
│   ├── s1_pred_fail.yaml
│   ├── s1_n_too_low.yaml
│   └── s1_range_mism.yaml
├── tests/
│   ├── test_thermal.py
│   ├── test_sensor.py
│   ├── test_runner.py
│   └── test_injector.py
├── cli.py                    ← python -m sim.run --scenario X --inject Y --seed Z
└── pyproject.toml
```

---

## 3. Компоненты

### 3.1 thermal_model.py

ODE 1-го порядка с дискретным шагом dt = 0.1 c:

```
T(t+dt) = T(t) + ((T_set - T(t)) / τ + ξ(t)) · dt
```

где ξ(t) ~ N(0, σ²) — гауссовский шум, σ = 0.05 °C.

Метод интегрирования: явный Эйлер (для скорости) или RK4 (опционально, через флаг).

Параметры:
- τ = 60 с (постоянная времени).
- T_set = 150 °C (уставка).
- σ = 0.05 °C.

### 3.2 sensor.py

**PT100 нелинейная характеристика** (ГОСТ 6651-2009):
```
R(T) = R0 · (1 + α·T + β·T²)
R0 = 100 Ом, α = 3.9083e-3, β = -5.775e-7
```

**АЦП:**
- 16 бит, диапазон 0–500 °C.
- Квантование ≈ 0.0076 °C / бит.
- Шум АЦП: σ_adc = 0.5 LSB ≈ 0.004 °C.
- Дрейф нуля: 1e-3 °C/час.

**Обратная функция R → T:**
```
T = (-α + sqrt(α² - 4β·(1 - R/R0))) / (2β)
```

### 3.3 scenario_runner.py

**FSM-движок**, читающий YAML-сценарий и исполняющий переходы.

Сценарий описывает:
- Какие состояния посещать.
- Гард-условия для переходов.
- Длительности (целевые, не жёсткие).
- Параметры процесса (T_set, t_hold_min, N_min).

Между переходами — цикл `while not transition_guard:` с шагом thermal_model + sensor (10 Гц), писать SAMPLE-события 1 Гц.

### 3.4 injector.py

Модифицирует поведение `scenario_runner.py` для воспроизведения 7 кодов нарушений из `violations_catalog.md`:

| Сценарий | Что делает injector |
|---|---|
| `s1_seq_miss` | пропускает HOLD: переход HEAT → MEASURE напрямую |
| `s1_seq_order` | меняет порядок: MEASURE до HOLD |
| `s1_time_under` | принудительно завершает HOLD через 30 с |
| `s1_time_over` | продлевает HOLD до 720 с |
| `s1_pred_fail` | переход HOLD → MEASURE при `\|dT_dt\| = 0.045` |
| `s1_n_too_low` | завершает MEASURE после 5 отсчётов |
| `s1_range_mism` | устанавливает T_set = 700 °C |

Каждый сценарий — это `correct.yaml` + `inject:` секция с типом и параметрами. Реализация — паттерн `decorator`/`monkey-patch` поверх scenario_runner.

### 3.5 event_logger.py

Пишет JSONL согласно `event_log_format.md` и `event_log.schema.json`. Поведение:

- Atomic line write через `open(... "a", buffering=1)` + `flush()`.
- Опционально — fsync на критичных событиях (`RUN_END`, `ERROR`).
- Поддерживает stdout/stderr-вывод для отладки + файловый.
- `meta.log_format_version = "1.0"` в RUN_START.

### 3.6 viz/3d_view.html

3D-визуализация на Three.js:
- Прозрачный куб (камера) 1×1×1 м.
- Цилиндр (образец) 0.1×0.2 м внутри; цвет от RGB(0, 0, 255) (синий, T=20 °C) к RGB(255, 0, 0) (красный, T=200 °C).
- Линия температуры (live chart D3.js) рядом с 3D-сценой.
- Текст состояния FSM сверху (INIT/HEAT/HOLD/MEASURE/POST).
- Слайдер времени для проигрывания записанного прогона.
- Загрузка прогона из JSONL через `<input type=file>` или fetch URL.

**Fallback (если Three.js «съест» время):** matplotlib FuncAnimation + одна 3D-картинка через pyvista для иллюстрации в ПЗ. Решение принимается на старте Phase 3.

### 3.7 cli.py

```bash
# Запуск эталонного прогона
python -m sim.run --scenario scenarios/s1_correct.yaml --output ../05_Эксперименты/runs/correct-001.jsonl --seed 42

# Прогон с инъекцией
python -m sim.run --scenario scenarios/s1_time_under.yaml --output runs/inj-001.jsonl --seed 42

# Серия прогонов
python -m sim.run --scenario scenarios/s1_correct.yaml --batch 50 --seed-base 1000 --output-dir runs/
```

---

## 4. Воспроизводимость

- **Seed.** Все случайные процессы (шум сенсора, шум АЦП, дрожь таймера) параметризованы единым `--seed`. При одном seed прогон идентичен побайтно.
- **Версионирование.** В каждый event-log пишется `meta.simulator_version` + git-sha сценария.
- **Метаданные прогонов.** `runs/_metadata.csv` — таблица run_id ↔ scenario ↔ seed ↔ timestamp ↔ FLV verdict. Заполняется автоматически в Phase 5.

---

## 5. Параметры по умолчанию (sim/config.py)

```python
# Физика
TAU = 60.0              # постоянная времени, с
T_AMBIENT = 24.0        # начальная (комнатная), °C
SENSOR_NOISE_SIGMA = 0.05  # °C
ADC_BITS = 16
ADC_RANGE = (0.0, 500.0)
ADC_DRIFT_PER_HOUR = 1e-3

# Процесс
T_SET_DEFAULT = 150.0
T_MIN = 50.0
DELTA_STABLE = 0.02     # °C/s
T_HOLD_MIN = 300        # с
T_HOLD_MAX = 600
N_MIN = 20
T_SET_MAX = 250.0       # граница камеры

# Симуляция
DT = 0.1                # шаг интегрирования, с
F_SAMPLE = 1.0          # частота отсчётов SAMPLE-событий, Гц
F_MEAS = 1.0            # частота MEAS_TICK, Гц

# PT100 (ГОСТ 6651-2009)
R0 = 100.0
ALPHA = 3.9083e-3
BETA = -5.775e-7
```

---

## 6. Связь с FLV-модулем

Симулятор и FLV-модуль связаны только через **формат event-log** (`event_log_format.md`). Это позволяет:

1. Проверить FLV на трассах из симулятора (Phase 4-5).
2. Заменить симулятор на реальное LabVIEW VI или Arduino-скетч (demo-track) — FLV-модуль работает одинаково.
3. Использовать другие симуляторы (например, для S2 SCPI — `pyvisa-sim` обёртка) без изменения FLV.

---

## 7. Дальнейшие расширения (post-defense)

- Многоконтурная теплопередача (камера + образец + воздушная прослойка).
- Гистерезис нагревателя с PWM-управлением.
- Имитация EMI-наводок на проводах термопары.
- Линейный дрейф калибровки PT100 (старение).
- Параллельный multi-stand симулятор для распределённых ИИС.

---

## 8. Альтернативный demo-track: Wokwi/Velxio

См. ADR-001. Идея — взять Arduino-скетч, реализующий ту же FSM, запустить в Wokwi (или локальном Velxio), забрать serial-вывод в формате event-log. FLV-модуль проверяет одинаково.

Скрипт-обёртка `03_Симулятор/wokwi_runner.py` (если делаем) — тонкая обвязка вокруг Wokwi-CLI или скрапер serial из браузера.
