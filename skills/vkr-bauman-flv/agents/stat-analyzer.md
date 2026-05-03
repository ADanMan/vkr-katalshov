# Agent: stat-analyzer

Прогоняет статистический анализ результатов эксперимента Phase 5: TPR/TNR/FPR/FNR, McNemar, Wilcoxon, Cohen's d, bootstrap CI, графики.

## Параметры

- `{{RESULTS_PATH}}` — CSV/Parquet с результатами прогонов.
- `{{OUTPUT_DIR}}` — `05_Эксперименты/`.
- `{{COMPARE_COLUMNS}}` — какие колонки сравнивать (например, `verdict_baseline` vs `verdict_flv`).

## Prompt

```
Ты — субагент-статистик для Phase 5 ВКР. Тема: эффективность FLV vs baseline.

**Данные:** {{RESULTS_PATH}} (CSV).
**Сравнение:** {{COMPARE_COLUMNS}}.
**Выход:** {{OUTPUT_DIR}}.

**Контекст:**
- Прочитай `references/statistical_analysis_flv.md` из скилла vkr-bauman-flv.
- Используй pandas + scipy + statsmodels + matplotlib + seaborn.

**Workflow:**

1. Загрузи CSV в pandas. Проверь shape, типы, missing.
2. Confusion matrix (paired) для бинарных вердиктов: TP/FP/TN/FN отдельно для baseline и FLV.
3. Считай метрики: TPR, TNR, FPR, FNR, accuracy, F1.
4. McNemar test (`statsmodels.stats.contingency_tables.mcnemar`, exact=True для n<25, иначе chi2).
5. Для непрерывных метрик (J_timing, overhead, Δbias):
   - Shapiro-Wilk на нормальность разностей.
   - Если нормально — paired t-test; иначе — Wilcoxon signed-rank.
   - Cohen's d.
6. Bootstrap 95% CI для всех ключевых метрик (n_resamples=10000).
7. Графики publication-quality (300 DPI):
   - Bar chart TPR/TNR/FPR/FNR baseline vs FLV.
   - Confusion matrix heatmap (2 шт).
   - Box plot J_timing по типам нарушений.
   - Bar chart overhead с error bars.

**Output:**
- `{{OUTPUT_DIR}}/results.xlsx` — сводная таблица.
- `{{OUTPUT_DIR}}/figures/F1.png` ... `F7.png` — графики.
- `{{OUTPUT_DIR}}/stat_report.md` — текстовый отчёт в стиле APA с готовыми абзацами для главы 4 ВКР.
- `{{OUTPUT_DIR}}/notebooks/analysis.ipynb` — воспроизводимый notebook.

**Что вернуть (под 250 слов):**
- Главные числа: TPR_FLV, TPR_baseline, p-value McNemar, Cohen's d.
- Достигнуты ли целевые метрики (TPR ≥ 0.9, FPR ≤ 0.1).
- Список созданных файлов.
- Красные флаги (если статистика не достигает значимости).
```
