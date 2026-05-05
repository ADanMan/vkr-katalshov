"""
experiments — пакет экспериментальной части ВКР Катальшова Д.А.,
К2-81Б (Phase 5).

Цель — численно доказать эффективность метода функционально-логической
верификации (FLV) на серии прогонов симулятора стенда S1 в сравнении
с baseline-подходом (наивные ad-hoc проверки в коде сценария).

Состав пакета:

* `baseline.py`   — реализация baseline-проверок для парного сравнения.
* `run_all.py`    — оркестратор батч-прогонов (по 50 прогонов на каждый
                    из 8 сценариев = 400+ event-log'ов).
* `analyze.py`    — расчёт метрик: TPR/TNR/FPR/FNR, J_timing, K_seq,
                    N_reject, overhead, Δbias.
* `stats.py`      — статистическая обработка: McNemar, Wilcoxon,
                    Cohen's d, bootstrap 95% CI (по ГОСТ 8.207-76 +
                    GUM/JCGM 100:2008).
* `plots.py`      — публикационные графики (300 DPI, paper-стиль).

CLI entry-points:

    exp-run --scenarios all --batch 50 --seed-base 1000
    exp-analyze --runs runs/ --out results.xlsx
    exp-stats --results results.xlsx --out stat_report.md
    exp-plots --results results.xlsx --out figures/
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vkr-katalshov-exp")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

__all__ = ["__version__"]
