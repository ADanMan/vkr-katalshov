# 05_Эксперименты

Прогоны симулятора + FLV-модуль, расчёт метрик и статистики (Phase 5).

## Структура

- `runs/` — JSONL-логи прогонов и `_metadata.csv` со seed/конфигом.
- `figures/` — графики publication-quality (300 DPI).
- `notebooks/analysis.ipynb` — воспроизводимый анализ.
- `run_all.py` — оркестратор прогонов.
- `analyze.py` — расчёт метрик, статистика, графики.
- `results.xlsx` — сводная таблица.
- `stat_report.md` — текстовый статистический отчёт.

## Метрики

| Группа | Метрики |
|---|---|
| Детекция | TP/FP/TN/FN, TPR/TNR/FPR/FNR |
| Качество | J_timing, K_seq, N_reject, Δbias |
| Производительность | overhead (wall-time, CPU, memory) |

## Статистика

- McNemar test (paired binary).
- Wilcoxon signed-rank / paired t-test.
- Cohen's d (размер эффекта).
- Bootstrap 95% CI (10 000 повторений).

α = 0.05.

## Воспроизводимость

```bash
cd 05_Эксперименты
python run_all.py --stand S1 --n-correct 50 --n-injected 50 --seed-base 1000
python analyze.py --results runs/ --output results.xlsx --figures figures/
```

⚠ Большие JSONL-логи прогонов исключены из git через `.gitignore`. Метаданные и сводные таблицы — коммитятся.
