# 05_Эксперименты — Phase 5

Экспериментальное исследование метода функционально-логической верификации (FLV).

## Концепция эксперимента

Парное сравнение двух подходов к верификации одного и того же event-log:

* **Baseline** — наивные ad-hoc проверки прямо в коде сценария
  (`assert wait_time >= 300`, `if N < 20: error()`). Имитация типового
  стиля LabVIEW/TestStand-сценариев без формальной модели методики.
* **Proposed (FLV)** — модуль из `04_FLV/` с DSL и тремя матчерами.

Один и тот же event-log проверяется обоими подходами, метрики
сравниваются попарно — это устраняет влияние seed'а на сравнение.

## Дизайн

| Стенд | Корректные | С инъекциями | Всего |
|---|---|---|---|
| S1 (термокамера PT100) | 50 | 50 (по 7 кодам инъекций) | 100 |

Все прогоны — детерминированные при фиксированном seed. Базовый
seed `--seed-base 1000`, каждый прогон получает `seed_base + i`.

## Метрики

**Детекция** (бинарные парные исходы):
TP / FP / TN / FN → TPR, TNR, FPR, FNR, accuracy, F1.

**Качество** (непрерывные):
* `J_timing` — средняя относительная ошибка по критичным временным
  окнам, `mean(|t_fact − t_min| / t_min)`.
* `K_seq` — доля прогонов без нарушений порядка переходов.
* `N_reject` — число заблокированных прогонов в режиме online.
* `Δbias` — смещение результата измерения при нарушении vs корректно.

**Производительность**:
* Wall-time overhead `t_FLV / t_baseline`.
* CPU overhead.
* Память.

## Статистика

* **McNemar test** (paired binary, ГОСТ 8.207-76 п. 5) — сравнение
  частоты детекции между подходами.
* **Wilcoxon signed-rank** (или paired t-test при нормальности
  Shapiro-Wilk) — для непрерывных метрик.
* **Cohen's d** — размер эффекта.
* **Bootstrap 95% CI** (10 000 повторений) — доверительные интервалы.

α = 0,05.

## Использование

```bash
cd 05_Эксперименты
python -m venv .venv && source .venv/bin/activate
pip install -e "../03_Симулятор" -e "../04_FLV" -e ".[notebook,dev]"

# 1) Серии прогонов (≈ 400 event-log'ов в runs/)
exp-run --scenarios all --batch 50 --seed-base 1000 --output-dir runs/

# 2) Расчёт метрик из всех runs/
exp-analyze --runs runs/ --out results.xlsx --metadata runs/_metadata.csv

# 3) Статистическая обработка
exp-stats --results results.xlsx --out stat_report.md

# 4) Публикационные графики
exp-plots --results results.xlsx --out figures/
```

## Воспроизводимость

* `runs/_metadata.csv` — таблица run_id ↔ scenario ↔ seed ↔ verdict.
* В каждый event-log пишется `meta.simulator_version` и seed.
* `results.xlsx` хранит сырые исходы по каждому прогону.
* Jupyter notebook `notebooks/analysis.ipynb` — пошаговое
  воспроизведение всех расчётов из `results.xlsx`.

## Структура

```
05_Эксперименты/
├── pyproject.toml
├── README.md
├── experiments/
│   ├── baseline.py          ad-hoc проверки сценария
│   ├── run_all.py           оркестратор batch-прогонов
│   ├── analyze.py           метрики из event-log + verdict
│   ├── stats.py             статистические тесты
│   └── plots.py             publication-quality фигуры
├── runs/                    JSONL event-log'и (gitignored)
│   └── _metadata.csv        метаданные каждого прогона
├── figures/                 PNG 300 DPI для ПЗ
├── notebooks/
│   └── analysis.ipynb       воспроизводимый ноутбук
├── results.xlsx             сводная таблица прогонов и метрик
└── stat_report.md           отчёт со всеми статистиками
```
