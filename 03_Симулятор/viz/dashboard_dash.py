"""
viz.dashboard_dash — Plotly Dash live-дашборд прогона.

Что показывает:
* live-чарт T(t) — все отсчёты sensor.T_indicated_C во времени;
* индикатор текущего FSM-состояния (большая «плашка» с цветом);
* таблица параметров прогона из RUN_START (T_set, t_hold_min, N_min);
* (после Phase 4 — будет вызывать FLV-модуль и показывать verdict
  + список violations; сейчас — заглушка).

Запуск:
    python -m viz.dashboard_dash --run path/to/run.jsonl
    # → http://127.0.0.1:8050

Если plotly/dash не установлены — модуль подсказывает
`pip install -e ".[dashboard]"` из 03_Симулятор/.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_FSM_COLORS: dict[str, str] = {
    "INIT": "#7e7e7e",
    "HEAT": "#f4b400",
    "HOLD": "#4285f4",
    "MEASURE": "#0f9d58",
    "POST": "#9c27b0",
}


def _load_run(jsonl_path: Path) -> list[dict[str, Any]]:
    """Lazy-import event_logger, чтобы dashboard не тащил sim-зависимости."""
    from sim.event_logger import load_jsonl

    return load_jsonl(jsonl_path)


def _build_temperature_series(
    events: list[dict[str, Any]],
) -> tuple[list[float], list[float], list[str]]:
    """Из event-log собрать списки (t_rel, T, state) для всех событий
    с signals.T."""
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


def _extract_run_meta(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Извлечь метаданные прогона из RUN_START."""
    for e in events:
        if e.get("event") == "RUN_START":
            return {
                "run_id": e.get("run_id", ""),
                "stand_id": e.get("stand_id", ""),
                **(e.get("meta") or {}),
                **(e.get("params") or {}),
            }
    return {}


def build_app(jsonl_path: Path) -> Any:
    """Собрать Dash-приложение для конкретного прогона."""
    try:
        import dash  # type: ignore[import-not-found]
        import plotly.graph_objects as go  # type: ignore[import-not-found]
        from dash import dash_table, dcc, html  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "Для дашборда требуются plotly и dash.\n"
            "Установи: pip install -e \".[dashboard]\" из 03_Симулятор/.\n"
            f"Detail: {e}"
        ) from e

    events = _load_run(jsonl_path)
    ts, Ts, states = _build_temperature_series(events)
    meta = _extract_run_meta(events)
    last_state = states[-1] if states else "—"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=Ts,
            mode="lines",
            name="T_indicated, °C",
            line={"width": 2, "color": "#1f77b4"},
        )
    )
    # Подкрашиваем фон по FSM-состоянию (vrects)
    if states:
        prev = states[0]
        prev_t = ts[0]
        for t, s in zip(ts, states, strict=True):
            if s != prev:
                fig.add_vrect(
                    x0=prev_t,
                    x1=t,
                    fillcolor=_FSM_COLORS.get(prev, "#cccccc"),
                    opacity=0.10,
                    line_width=0,
                    layer="below",
                )
                prev_t = t
                prev = s
        fig.add_vrect(
            x0=prev_t,
            x1=ts[-1] if ts else 0.0,
            fillcolor=_FSM_COLORS.get(prev, "#cccccc"),
            opacity=0.10,
            line_width=0,
            layer="below",
        )

    fig.update_layout(
        xaxis_title="t, с",
        yaxis_title="T, °C",
        margin={"l": 50, "r": 20, "t": 20, "b": 40},
        plot_bgcolor="white",
        height=420,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")

    meta_rows = [{"key": k, "value": str(v)} for k, v in meta.items()]

    app = dash.Dash(__name__, title=f"FLV — {jsonl_path.name}")
    app.layout = html.Div(
        style={"fontFamily": "system-ui, sans-serif", "maxWidth": "1200px", "margin": "auto"},
        children=[
            html.H2(f"FLV Simulator — прогон {meta.get('run_id', jsonl_path.stem)}"),
            html.Div(
                style={"display": "flex", "gap": "16px", "alignItems": "center", "marginBottom": "16px"},
                children=[
                    html.Div(
                        style={
                            "padding": "12px 24px",
                            "borderRadius": "6px",
                            "backgroundColor": _FSM_COLORS.get(last_state, "#cccccc"),
                            "color": "white",
                            "fontWeight": "bold",
                        },
                        children=f"FSM: {last_state}",
                    ),
                    html.Div(
                        style={
                            "padding": "12px 24px",
                            "borderRadius": "6px",
                            "backgroundColor": "#fafafa",
                            "border": "1px solid #ddd",
                        },
                        children=f"Verdict: (FLV не подключён в Phase 3, реализуется в Phase 4)",
                    ),
                ],
            ),
            dcc.Graph(figure=fig, id="temperature-chart"),
            html.H4("Метаданные прогона"),
            dash_table.DataTable(
                data=meta_rows,
                columns=[{"name": "Поле", "id": "key"}, {"name": "Значение", "id": "value"}],
                style_cell={"fontFamily": "monospace", "padding": "6px"},
                style_header={"backgroundColor": "#fafafa", "fontWeight": "bold"},
            ),
        ],
    )
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="viz.dashboard_dash")
    parser.add_argument("--run", required=True, type=Path, help="Путь к JSONL-логу прогона")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = build_app(args.run)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
