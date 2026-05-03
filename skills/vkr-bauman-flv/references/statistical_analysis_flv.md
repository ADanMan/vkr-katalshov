# Статистическая обработка эксперимента FLV

Применяется в Phase 5 (главы 4 ПЗ). Цель — статистически значимо доказать преимущество FLV перед baseline.

## Дизайн эксперимента

- Парный (paired): на каждом сценарии прогоняется и baseline, и FLV.
- N прогонов на стенд: 100 на S1 (50 корректных + 50 с инъекциями), 60 на S2.
- Семя seed фиксировано: симулятор детерминирован.

## Метрики детекции (бинарные)

Confusion matrix:

|  | Прогон С нарушением | Прогон БЕЗ нарушения |
|---|---|---|
| Детектировано | TP (истинно-положительные) | FP (ложно-положительные) |
| Не детектировано | FN (ложно-отрицательные) | TN (истинно-отрицательные) |

Метрики:

- TPR (sensitivity, recall) = TP / (TP + FN). Цель ≥ 0.90.
- TNR (specificity) = TN / (TN + FP). Цель ≥ 0.90.
- FPR = 1 - TNR = FP / (FP + TN). Цель ≤ 0.10.
- FNR = 1 - TPR = FN / (FN + TP). Цель ≤ 0.10.
- Accuracy = (TP + TN) / total.
- F1 = 2*TP / (2*TP + FP + FN).

## Метрики качества (непрерывные)

- **J_timing** = mean(|t_fact - t_spec_min| / t_spec_min) по всем критичным временным окнам.
- **K_seq** — доля прогонов без нарушения порядка переходов.
- **N_reject** — число заблокированных «плохих» прогонов в режиме online.
- **Δbias** — смещение результата измерения T при нарушении vs корректно.

## Метрики производительности

- **Wall-time overhead**: t_FLV / t_baseline.
- **CPU overhead**: cpu_time_FLV / cpu_time_baseline.
- **Memory peak**: пиковое потребление, МБ.

## Статистические тесты

### Бинарные исходы (детекция)

**McNemar test** — для парных бинарных данных. Сравниваем, как часто baseline и FLV дают разный вердикт на одном и том же прогоне.

```python
from statsmodels.stats.contingency_tables import mcnemar
table = [[a, b],   # обе верны
         [c, d]]   # FLV верн., baseline неверн. (b); baseline верн., FLV неверн. (c)
result = mcnemar(table, exact=True)
# result.pvalue
```

α = 0.05. Если p < 0.05 — есть статистически значимая разница.

### Непрерывные метрики (J_timing, overhead)

**Wilcoxon signed-rank test** — для парных данных без предположения о нормальности.

```python
from scipy.stats import wilcoxon
stat, p = wilcoxon(baseline_J_timing, flv_J_timing)
```

Альтернатива при нормальности: paired t-test.

**Проверка нормальности** — Shapiro-Wilk:

```python
from scipy.stats import shapiro
stat, p = shapiro(differences)
# p > 0.05 → нормальные → t-test; иначе → Wilcoxon
```

### Размер эффекта

**Cohen's d** для непрерывных:

```python
import numpy as np
d = (np.mean(flv) - np.mean(baseline)) / np.std(np.concatenate([flv, baseline]))
# |d| < 0.2 — малый эффект
# 0.2 ≤ |d| < 0.5 — средний
# 0.5 ≤ |d| < 0.8 — большой
# |d| ≥ 0.8 — очень большой
```

Для бинарных — **odds ratio** или **относительный риск**.

### 95% CI через bootstrap

```python
from scipy.stats import bootstrap
res = bootstrap((data,), np.mean, confidence_level=0.95, n_resamples=10000, method='percentile')
# res.confidence_interval.low, res.confidence_interval.high
```

## Графики publication-quality

| # | Тип | Что показывает |
|---|---|---|
| F1 | Bar chart | TPR/TNR/FPR/FNR — baseline vs FLV |
| F2 | Confusion matrix (2×) | Тепловые карты для baseline и FLV |
| F3 | Box plot | J_timing для каждого типа нарушения |
| F4 | Time-series | T(t) корректно vs с TIME_UNDER, FSM-состояния поверх |
| F5 | Bar chart с error bars | Overhead FLV vs baseline (мс) |
| F6 | Scatter | N_reject vs тип нарушения |
| F7 | Stacked bar | Распределение детектированных кодов нарушений |

Стиль:
- 300 DPI (savefig dpi=300).
- TNR-совместимый шрифт, минимум 10 pt.
- Цветовая палитра — colorblind-safe (например, `seaborn-colorblind`).
- Размер figsize = (8, 5) для bar/line, (8, 8) для confusion matrix.
- Сохранение в PNG для Word + PDF для backup.

## Шаблоны APA-отчётов (для главы 4)

«Прогон baseline-метода детектировал {TP_b}/{N_inj} нарушений (TPR = {TPR_b:.2f}), что значимо ниже результата FLV-метода: {TP_f}/{N_inj} (TPR = {TPR_f:.2f}). Разница статистически значима (McNemar χ² = {chi2:.2f}, p = {p:.3f}). Размер эффекта по Cohen's d = {d:.2f} ({'большой' if abs(d) >= 0.8 else 'средний'}).»

## Воспроизводимость

- Каждый расчёт — в Jupyter Notebook `05_Эксперименты/notebooks/analysis.ipynb`.
- Seeds, версии библиотек — в `requirements.txt`.
- В заключении notebook'а — `requirements freeze` для будущей воспроизводимости.

## Чек-лист перед сдачей главы 4

- [ ] N ≥ 100 на S1 (или мотивированное обоснование меньшего объёма).
- [ ] Все 7 кодов нарушений представлены в инъекциях.
- [ ] Парные метрики на одних и тех же seed'ах.
- [ ] McNemar test для бинарных, Wilcoxon/t-test для непрерывных.
- [ ] Cohen's d рассчитан для каждой непрерывной метрики.
- [ ] 95% CI через bootstrap.
- [ ] Все графики в формате publication-quality (300 DPI, минимум 10 pt шрифт).
- [ ] Threats to validity описаны (см. Wohlin et al., 2012, для шаблона).

## Источники

- Cohen J. (1988). Statistical Power Analysis for the Behavioral Sciences.
- McNemar Q. (1947). Note on the sampling error of the difference between correlated proportions.
- Wohlin C. et al. (2012). Experimentation in Software Engineering — для threats to validity.
