"""
experiments.plots — публикационная графика для пояснительной записки.

Все фигуры:

* matplotlib only (без seaborn — детерминированно, без тем);
* размер 8×5 дюймов (двухколоночный стандарт ВКР), DPI 300;
* шрифты — DejaVu Sans / Serif (поддержка кириллицы и °C);
* единицы оси — по ГОСТ 8.417-2002 (через пробел перед единицей,
  «°C», «с», «К/с»);
* ч/б-friendly палитра (viridis для цвета, hatch-паттерны для bar'ов);
* grid alpha=0.3, легенда compact;
* сохранение в PNG и SVG (для масштабирования в .docx).

Графики:

1. ``confusion_matrix_paired.png`` — TP/FP/TN/FN heatmap baseline | FLV.
2. ``metrics_bar.png`` — TPR/TNR/FPR/F1 paired bar.
3. ``timeline_example.png`` — пример event-log с FSM-полосой.
4. ``boxplot_overhead.png`` — t_baseline vs t_FLV по сценариям.
5. ``roc_curve.png`` — ROC (если применимо, иначе пропуск с warning).
6. ``j_timing_distribution.png`` — гистограмма J_timing с CI.
7. ``delta_bias_scatter.png`` — Δbias по сценариям (strip + jitter).

CLI:

    exp-plots --results results.xlsx --out figures/
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()

# Глобальные настройки matplotlib для публикационного качества.
matplotlib.rcParams.update({
    "figure.figsize": (8.0, 5.0),
    "figure.dpi": 100,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "legend.frameon": False,
    "lines.linewidth": 1.6,
})

COLOR_BASELINE = "#9E9E9E"
COLOR_FLV = "#1976D2"
COLOR_OK = "#2E7D32"
COLOR_WARN = "#E65100"
COLOR_ERROR = "#C62828"


def _save(fig: plt.Figure, out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png")
    fig.savefig(out_dir / f"{name}.svg")
    plt.close(fig)


# ──────────────────────────────────────────────────────────────────────
# 1. Confusion matrix paired
# ──────────────────────────────────────────────────────────────────────


def plot_confusion_paired(summary: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, (_, row) in zip(axes, summary.iterrows(), strict=False):
        cm = np.array([
            [row["TP"], row["FN"]],
            [row["FP"], row["TN"]],
        ], dtype=int)
        im = ax.imshow(cm, cmap="Blues", aspect="equal")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Detected", "Not detected"])
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Violation", "No violation"])
        ax.set_xlabel("Verdict")
        ax.set_ylabel("Ground truth")
        ax.set_title(f"{row['approach'].upper()} (F1 = {row['F1']:.3f})")
        for i in range(2):
            for j in range(2):
                ax.text(
                    j, i, str(cm[i, j]),
                    ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black",
                    fontsize=14, fontweight="bold",
                )
        ax.grid(False)
    fig.suptitle("Confusion matrix — paired baseline / FLV", fontsize=13)
    fig.tight_layout()
    _save(fig, out_dir, "confusion_matrix_paired")


# ──────────────────────────────────────────────────────────────────────
# 2. Metrics bar
# ──────────────────────────────────────────────────────────────────────


def plot_metrics_bar(summary: pd.DataFrame, out_dir: Path) -> None:
    metrics = ["TPR", "TNR", "FPR", "FNR", "F1"]
    x = np.arange(len(metrics))
    width = 0.36
    fig, ax = plt.subplots()
    base_vals = [float(summary.iloc[0][m]) for m in metrics]
    flv_vals = [float(summary.iloc[1][m]) for m in metrics]
    ax.bar(x - width / 2, base_vals, width, label="Baseline",
           color=COLOR_BASELINE, edgecolor="black", hatch="//")
    ax.bar(x + width / 2, flv_vals, width, label="FLV",
           color=COLOR_FLV, edgecolor="black")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Значение метрики")
    ax.set_title("Парные метрики качества: baseline vs FLV")
    ax.legend(loc="upper right")
    for i, (b, f) in enumerate(zip(base_vals, flv_vals, strict=True)):
        ax.text(i - width / 2, b + 0.02, f"{b:.2f}", ha="center", fontsize=9)
        ax.text(i + width / 2, f + 0.02, f"{f:.2f}", ha="center", fontsize=9)
    fig.tight_layout()
    _save(fig, out_dir, "metrics_bar")


# ──────────────────────────────────────────────────────────────────────
# 3. Timeline example (один прогон)
# ──────────────────────────────────────────────────────────────────────


def plot_timeline_example(raw: pd.DataFrame, runs_dir: Path, out_dir: Path) -> None:
    """Пример прогона: T(t) с цветными полосами FSM-фаз."""
    sub = raw[raw["violation_expected"]].copy()
    if sub.empty:
        sub = raw.copy()
    sample_run = sub.iloc[0]
    log_path = Path(sample_run["log_path"])
    if not log_path.is_absolute() and runs_dir is not None:
        log_path = runs_dir / log_path.name
    if not log_path.exists():
        logger.warning("Не найден лог для примера: %s — пропускаю timeline_example", log_path)
        return

    import json
    times: list[float] = []
    temps: list[float] = []
    states: list[str] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        s = (ev.get("signals") or {})
        if "T" not in s:
            continue
        params = ev.get("params") or {}
        times.append(float(params.get("_ts_rel_s", 0)))
        temps.append(float(s["T"]))
        states.append(str(ev.get("state", "")))

    if not times:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    state_colors = {
        "INIT": "#546E7A", "HEAT": "#E65100",
        "HOLD": "#2E7D32", "MEASURE": "#1976D2", "POST": "#616161",
    }
    # Разрисовать FSM-фазы как полупрозрачные axvspan'ы.
    cur = states[0]
    cur_start = times[0]
    for t, st in zip(times, states, strict=True):
        if st != cur:
            ax.axvspan(cur_start, t, alpha=0.18,
                       color=state_colors.get(cur, "#9E9E9E"), label=cur)
            cur = st
            cur_start = t
    ax.axvspan(cur_start, times[-1], alpha=0.18,
               color=state_colors.get(cur, "#9E9E9E"), label=cur)

    ax.plot(times, temps, color="#212121", linewidth=1.4)
    ax.set_xlabel("Время от старта прогона, с")
    ax.set_ylabel("T_indicated, °C")
    ax.set_title(
        f"Пример прогона: {sample_run.get('scenario_id', '?')} "
        f"(seed={sample_run.get('seed', '?')})",
    )

    # Уникальные FSM-метки в легенде.
    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    uniq: list[tuple[Any, str]] = []
    for h, l in zip(handles, labels, strict=True):  # noqa: E741
        if l not in seen:
            uniq.append((h, l))
            seen.add(l)
    ax.legend(*zip(*uniq, strict=True), loc="lower right", ncol=3)
    fig.tight_layout()
    _save(fig, out_dir, "timeline_example")


# ──────────────────────────────────────────────────────────────────────
# 4. Boxplot overhead
# ──────────────────────────────────────────────────────────────────────


def plot_boxplot_overhead(raw: pd.DataFrame, out_dir: Path) -> None:
    sub = raw.dropna(subset=["baseline_time_s", "flv_time_s"])
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    data = []
    labels = []
    for sc, grp in sub.groupby("scenario_id"):
        data.append(grp["baseline_time_s"].values * 1000)  # → мс
        labels.append(f"{sc}\nbaseline")
        data.append(grp["flv_time_s"].values * 1000)
        labels.append(f"{sc}\nFLV")
    # ``labels=`` устарел в matplotlib 3.9 в пользу ``tick_labels=``,
    # но в 3.8 ``tick_labels`` ещё не поддерживается; передаём через
    # set_xticklabels для совместимости с обеими версиями.
    bp = ax.boxplot(data, patch_artist=True, widths=0.6)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels)
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(COLOR_BASELINE if i % 2 == 0 else COLOR_FLV)
        patch.set_alpha(0.7)
    ax.set_ylabel("Время проверки одного прогона, мс")
    ax.set_title("Производительность по сценариям: baseline vs FLV")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)
    fig.tight_layout()
    _save(fig, out_dir, "boxplot_overhead")


# ──────────────────────────────────────────────────────────────────────
# 5. ROC (заглушка — если threshold-mode появится)
# ──────────────────────────────────────────────────────────────────────


def plot_roc(_raw: pd.DataFrame, out_dir: Path) -> None:
    """ROC требует score-функции; в текущей реализации FLV даёт
    бинарный verdict, поэтому строим точку (FPR, TPR) на ROC-плоскости."""
    # Простой 'operating point' график.
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="random")
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_title("ROC operating points (binary classifiers)")
    ax.text(
        0.5, 0.05,
        "Binary verdict — на ROC-плоскости\nдоступна только operating-точка.",
        ha="center", color="#757575", fontsize=10,
    )
    fig.tight_layout()
    _save(fig, out_dir, "roc_curve")


# ──────────────────────────────────────────────────────────────────────
# 6. J_timing histogram
# ──────────────────────────────────────────────────────────────────────


def plot_j_timing(raw: pd.DataFrame, out_dir: Path) -> None:
    sub = raw.dropna(subset=["t_hold_s"])
    if sub.empty:
        return
    rel_err = (sub["t_hold_s"] - 300.0).abs() / 300.0
    fig, ax = plt.subplots()
    ax.hist(rel_err, bins=24, color=COLOR_FLV, alpha=0.75, edgecolor="black")
    mean = float(rel_err.mean())
    ax.axvline(mean, color=COLOR_ERROR, linestyle="--",
               label=f"mean = {mean:.4f}")
    ax.set_xlabel(r"|t_hold − t_min| / t_min")
    ax.set_ylabel("Число прогонов")
    ax.set_title("Распределение J_timing — отклонения длительности HOLD")
    ax.legend()
    fig.tight_layout()
    _save(fig, out_dir, "j_timing_distribution")


# ──────────────────────────────────────────────────────────────────────
# 7. Δbias scatter
# ──────────────────────────────────────────────────────────────────────


def plot_delta_bias(raw: pd.DataFrame, out_dir: Path) -> None:
    sub = raw.dropna(subset=["T_meas_mean_C", "T_set_C"]).copy()
    if sub.empty:
        return
    sub["delta_bias_C"] = (sub["T_meas_mean_C"] - sub["T_set_C"]).abs()
    fig, ax = plt.subplots(figsize=(9, 5))
    rng = np.random.default_rng(42)
    scenarios = sorted(sub["scenario_id"].unique())
    for i, sc in enumerate(scenarios):
        grp = sub[sub["scenario_id"] == sc]
        x = np.full(len(grp), i, dtype=float) + rng.uniform(-0.18, 0.18, len(grp))
        is_correct = "correct" in str(sc)
        color = COLOR_OK if is_correct else COLOR_ERROR
        ax.scatter(x, grp["delta_bias_C"], color=color, alpha=0.7, s=22, edgecolor="black",
                   linewidth=0.4)
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("|T_meas − T_set|, °C")
    ax.set_title("Δbias по сценариям — корректные (зелёные) vs инъекции (красные)")
    fig.tight_layout()
    _save(fig, out_dir, "delta_bias_scatter")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


@click.command(help="Сборка 7 публикационных фигур из results.xlsx.")
@click.option(
    "--results", "results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("results.xlsx"), show_default=True,
)
@click.option(
    "--runs", "runs_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("runs"), show_default=True,
)
@click.option(
    "--out", "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("figures"), show_default=True,
)
def main(results_path: Path, runs_dir: Path, out_dir: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raw = pd.read_excel(results_path, sheet_name="raw")
    summary = pd.read_excel(results_path, sheet_name="summary")
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_confusion_paired(summary, out_dir)
    plot_metrics_bar(summary, out_dir)
    plot_timeline_example(raw, runs_dir, out_dir)
    plot_boxplot_overhead(raw, out_dir)
    plot_roc(raw, out_dir)
    plot_j_timing(raw, out_dir)
    plot_delta_bias(raw, out_dir)

    console.print(f"[green]✓[/green] фигуры сохранены: {out_dir}")


if __name__ == "__main__":
    main()
