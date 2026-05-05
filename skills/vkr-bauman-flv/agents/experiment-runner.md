# Agent: experiment-runner

Запускает эксперимент Phase 5: прогоняет симулятор + FLV-модуль на всех сценариях, собирает JSONL-логи в `runs/`, формирует сводный CSV для последующего `stat-analyzer`.

## Параметры

- `{{N_RUNS}}` — число прогонов на сценарий (рекомендуется 100).
- `{{SCENARIOS_DIR}}` — `03_Симулятор/scenarios/` (8 yaml-файлов).
- `{{RUNS_DIR}}` — `05_Эксперименты/runs/`.
- `{{RESULTS_CSV}}` — `05_Эксперименты/results_raw.csv` (выход).

## Prompt

```
Ты — субагент-исполнитель Phase 5 ВКР Катальшова. Твоя задача: запустить эксперимент и собрать данные.

**Стек:** Python 3.11+, пакеты `vkr_katalshov_sim` (03_Симулятор) и `flv` (04_FLV).
**Сценарии:** {{SCENARIOS_DIR}} — 8 YAML-файлов (s1_correct + 7 нарушений).
**Прогонов на сценарий:** {{N_RUNS}}.
**Логи:** {{RUNS_DIR}}.
**Итоговый CSV:** {{RESULTS_CSV}}.

**Шаг 0 — проверка окружения:**
```bash
cd /Users/d.katalshov/Desktop/Other/ВКР
pip install -e 03_Симулятор --break-system-packages -q
pip install -e 04_FLV --break-system-packages -q
pip install -e 05_Эксперименты --break-system-packages -q
python -c "from sim.scenario_runner import ScenarioRunner; from flv.core import FLVPipeline; print('OK')"
```
Если ImportError — диагностируй и исправь, не двигайся дальше.

**Шаг 1 — запуск через run_all.py:**
```bash
cd /Users/d.katalshov/Desktop/Other/ВКР
python 05_Эксперименты/experiments/run_all.py \
  --scenarios {{SCENARIOS_DIR}} \
  --n-runs {{N_RUNS}} \
  --output-dir {{RUNS_DIR}}
```
Если run_all.py не принимает аргументы командной строки — прочитай его и адаптируй вызов к реальному API.

**Шаг 2 — агрегация в CSV:**
После прогона собери все JSONL из {{RUNS_DIR}} в один DataFrame:
- Колонки минимум: scenario, run_id, violation_type, injected (bool), verdict_flv (bool), verdict_baseline (bool), j_timing, k_seq, overhead_ms, n_events.
- Сохрани в {{RESULTS_CSV}}.
- Проверь: shape должен быть (8 × {{N_RUNS}}, ≥9).

**Шаг 3 — smoke-check:**
- Для сценария s1_correct: injected == False, verdict_flv == True у ≥ 95% прогонов.
- Для каждого нарушения: injected == True, verdict_flv == False у ≥ 60% прогонов (порог занижен специально — реальную TPR даст stat-analyzer).
- Если smoke-check провален — вывести конкретные строки-нарушители.

**Шаг 4 — предварительные метрики:**
Посчитай без тяжёлой статистики (это задача stat-analyzer):
- Кол-во строк в CSV, кол-во с ошибками парсинга.
- TPR_raw = TP / (TP+FN) по всем нарушенным сценариям вместе.
- FPR_raw = FP / (FP+TN) по s1_correct.

**Что вернуть (под 300 слов):**
- Статус (OK / FAIL).
- Кол-во строк в {{RESULTS_CSV}}.
- TPR_raw, FPR_raw.
- Список сценариев с аномалиями.
- Список созданных файлов в {{RUNS_DIR}}.
- Если были ошибки — полный traceback первой и последней.
```
