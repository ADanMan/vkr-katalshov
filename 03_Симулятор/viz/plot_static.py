"""
viz.plot_static — статические публикационные графики через
matplotlib + seaborn.

Используется для PNG-иллюстраций в ПЗ (300 DPI, paper-стиль,
TNR-совместимые шрифты). Каждая функция принимает event-log одного
прогона (или несколько прогонов) и сохраняет файл по указанному
пути.

Ничего не возвращает в графический интерфейс (off-screen рендер).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _setup_publication_style() -> None:
    """Применить paper-стиль для всех графиков модуля.

    Семейство шрифтов 'serif' с Times-фоллбэком — соответствует
    Times New Roman из Word ВКР (визуально неотличимо при наличии
    шрифта в системе)."""
    import matplotlib  # type: ignore[import-not-found]
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    import seaborn as sns  # type: ignore[import-not-found]

    sns.set_theme(context="paper", style="whitegrid", palette="colorblind")
    matplotlib.rcParams.update(
        {
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Times", "serif"],
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
        }
    )
    return plt


def _load_run(jsonl_path: Path) -> list[dict[str, Any]]:
    from sim.event_logger import load_jsonl

    return load_jsonl(jsonl_path)


def _series_from_run(events: list[dict[str, Any]]) -> tuple[list[float], list[float], list[str]]:
    ts: list[float] = []
    Ts: list[float] = []
    states: list[str] = []
    for e in events:
        signals = e.get("signals") or {}
        if "T" not in signals:
            continue
        params = e.get("params") or {}
        ts.append(float(params.get("_ts_rel_s", 0.0)))
        Ts.append(float(signals["T"]))
        states.append(str(e.get("state", "")))
    return ts, Ts, states


# ----------------------------------------------------------------------
# Публичные функции — каждая сохраняет один график
# ----------------------------------------------------------------------


def plot_run_temperature(jsonl_path: Path, output_png: Path) -> Path:
    """T(t) одного прогона со штриховкой FSM-состояний.

    Подходит для ПЗ как «Рисунок N — Профиль температуры эталонного
    прогона стенда S1».
    """
    plt = _setup_publication_style()
    events = _load_run(jsonl_path)
    ts, Ts, states = _series_from_run(events)

    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.plot(ts, Ts, linewidth=1.2, color="black")

    # FSM-полосы
    if states:
        prev = states[0]
        prev_t = ts[0]
        colors = {
            "INIT": "#bdbdbd",
            "HEAT": "#fdd49e",
            "HOLD": "#bdd7e7",
            "MEASURE": "#a1d99b",
            "POST": "#dadaeb",
        }
        for t, s in zip(ts, states, strict=True):
            if s != prev:
                ax.axvspan(prev_t, t, alpha=0.35, color=colors.get(prev, "#cccccc"), linewidth=0)
                prev_t, prev = t, s
        ax.axvspan(prev_t, ts[-1] if ts else 0.0, alpha=0.35, color=colors.get(prev, "#cccccc"), linewidth=0)
        # Легенда состояний
        from matplotlib.patches import Patch  # type: ignore[import-not-found]

        seen = []
        for s in states:
            if s not in seen:
                seen.append(s)
        handles = [Patch(facecolor=colors.get(s, "#cccccc"), alpha=0.35, label=s) for s in seen]
        ax.legend(handles=handles, loc="lower right", framealpha=0.9, ncol=len(seen))

    ax.set_xlabel("Время, с")
    ax.set_ylabel("Температура, °C")
    ax.set_title(f"Профиль температуры — {jsonl_path.stem}")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png)
    plt.close(fig)
    logger.info("saved %s", output_png)
    return output_png


def plot_runs_overlay(
    jsonl_paths: Iterable[Path],
    output_png: Path,
    title: str | None = None,
) -> Path:
    """Несколько прогонов на одном графике T(t) — для иллюстрации
    разброса при batch-прогоне с разными seed."""
    plt = _setup_publication_style()
    fig, ax = plt.subplots(figsize=(7.5, 4.0))

    paths = list(jsonl_paths)
    for path in paths:
        events = _load_run(path)
        ts, Ts, _states = _series_from_run(events)
        ax.plot(ts, Ts, linewidth=0.9, alpha=0.6, label=path.stem)

    if len(paths) <= 8:
        ax.legend(loc="lower right", fontsize=8, ncol=2)
    ax.set_xlabel("Время, с")
    ax.set_ylabel("Температура, °C")
    ax.set_title(title or f"Профили температуры — {len(paths)} прогонов")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png)
    plt.close(fig)
    logger.info("saved %s (%d runs)", output_png, len(paths))
    return output_png


def plot_pid_step_response(output_png: Path, duration_s: float = 600.0) -> Path:
    """Step-response замкнутого контура PID·G — для главы 2 ПЗ.

    Использует sim.control_loop.step_response().
    """
    plt = _setup_publication_style()

    from sim.control_loop import step_response

    t, y = step_response(duration_s=duration_s)

    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.plot(t, y, linewidth=1.4, color="black", label="T_out(t)")
    ax.axhline(1.0, color="#888", linestyle="--", linewidth=0.8, label="setpoint")
    ax.set_xlabel("Время, с")
    ax.set_ylabel("Нормированный отклик")
    ax.set_title("Переходная характеристика замкнутого PID-контура")
    ax.legend(loc="lower right")
    fig.savefig(output_png)
    plt.close(fig)
    logger.info("saved %s", output_png)
    return output_png


def plot_pid_bode(output_png: Path) -> Path:
    """Bode-диаграмма разомкнутой системы C(s)·G(s) — для главы 2."""
    plt = _setup_publication_style()

    from sim.control_loop import bode_data

    omega, mag_db, phase_deg = bode_data()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 5.5), sharex=True)
    ax1.semilogx(omega, mag_db, color="black", linewidth=1.2)
    ax1.axhline(0.0, color="#888", linestyle="--", linewidth=0.6)
    ax1.set_ylabel("|G(jω)|, дБ")
    ax1.set_title("Диаграмма Боде разомкнутой системы C(s)·G(s)")

    ax2.semilogx(omega, phase_deg, color="black", linewidth=1.2)
    ax2.axhline(-180.0, color="#888", linestyle="--", linewidth=0.6)
    ax2.set_ylabel("∠G(jω), °")
    ax2.set_xlabel("ω, рад/с")

    fig.savefig(output_png)
    plt.close(fig)
    logger.info("saved %s", output_png)
    return output_png


__all__ = [
    "plot_run_temperature",
    "plot_runs_overlay",
    "plot_pid_step_response",
    "plot_pid_bode",
]
