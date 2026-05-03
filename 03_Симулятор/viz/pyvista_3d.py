"""
viz.pyvista_3d — интерактивная 3D-визуализация термокамеры в браузере.

Стек: pyvista (геометрия + рендер) + trame (web UI) + VTK.

Что показывается:
* термокамера — прозрачный куб 1×1×1 м;
* образец — цилиндр 0.1 м диаметром, 0.2 м высотой; цвет меняется от
  синего (T = 20 °C) до красного (T = 250 °C) в зависимости от
  T_indicated_C из event-log;
* «термопара» — линия в обобщённом представлении PT100 датчика
  (визуальный маркер);
* live-чарт T(t) рядом со сценой;
* подпись текущего FSM-состояния (INIT/HEAT/HOLD/MEASURE/POST);
* слайдер времени для скрабинга записанного прогона.

Запуск:
    python -m viz.pyvista_3d --run path/to/run.jsonl
    # → http://localhost:8080

Если pyvista/trame не установлены — модуль подсказывает, что нужно
поставить `pip install -e ".[viz3d]"` из корня 03_Симулятор/.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _color_from_temperature(T_C: float, T_min: float = 20.0, T_max: float = 250.0) -> tuple[float, float, float]:
    """Линейная интерполяция RGB от синего (холодно) к красному (горячо)."""
    t = max(0.0, min(1.0, (T_C - T_min) / (T_max - T_min)))
    return (t, 0.0, 1.0 - t)


def _load_run(jsonl_path: Path) -> list[dict[str, Any]]:
    """Тонкая обёртка с lazy-import event_logger, чтобы 3D-pipeline
    не тащил sim-зависимости при импорте модуля."""
    from sim.event_logger import load_jsonl

    return load_jsonl(jsonl_path)


def _extract_temperature_track(events: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    """Из event-log собрать список (t_rel_s, T_indicated_C, state)
    для всех событий, где есть signals.T."""
    track: list[tuple[float, float, str]] = []
    for e in events:
        signals = e.get("signals") or {}
        if "T" not in signals:
            continue
        params = e.get("params") or {}
        t_rel = float(params.get("_ts_rel_s", 0.0))
        track.append((t_rel, float(signals["T"]), e.get("state", "")))
    return track


def build_app(jsonl_path: Path) -> Any:
    """Собрать trame-приложение для конкретного прогона.

    Возвращает trame.app.Server, который можно запустить через .start().
    """
    try:
        import pyvista as pv  # type: ignore[import-not-found]
        from trame.app import get_server  # type: ignore[import-not-found]
        from trame.ui.vuetify import SinglePageWithDrawerLayout  # type: ignore[import-not-found]
        from trame.widgets import vtk as trame_vtk  # type: ignore[import-not-found]
        from trame.widgets import vuetify  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "Для 3D-визуализации требуются pyvista и trame.\n"
            "Установи: pip install -e \".[viz3d]\" из 03_Симулятор/.\n"
            f"Detail: {e}"
        ) from e

    events = _load_run(jsonl_path)
    track = _extract_temperature_track(events)
    if not track:
        raise SystemExit(f"В {jsonl_path} не нашлось событий с signals.T")

    # Сцена
    chamber = pv.Cube(center=(0, 0, 0), x_length=1.0, y_length=1.0, z_length=1.0)
    sample = pv.Cylinder(
        center=(0, 0, -0.1), direction=(0, 0, 1), radius=0.05, height=0.2,
    )
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(chamber, color="lightgray", opacity=0.15, show_edges=True)
    sample_actor = plotter.add_mesh(sample, color=_color_from_temperature(track[0][1]))
    plotter.add_text("INIT", name="state_label", position="upper_left", font_size=14)
    plotter.set_background("white")
    plotter.camera_position = [(2.0, 2.0, 2.0), (0, 0, 0), (0, 0, 1)]

    # trame
    server = get_server()
    state, ctrl = server.state, server.controller

    state.frame = 0
    state.frame_max = len(track) - 1
    state.t_rel_s = track[0][0]
    state.T_C = track[0][1]
    state.fsm_state = track[0][2]

    @ctrl.set("update_frame")
    def update_frame(frame: int) -> None:
        i = max(0, min(int(frame), state.frame_max))
        t_rel, T_C, fsm = track[i]
        state.t_rel_s = t_rel
        state.T_C = T_C
        state.fsm_state = fsm
        sample_actor.GetProperty().SetColor(*_color_from_temperature(T_C))
        plotter.add_text(fsm, name="state_label", position="upper_left", font_size=14, color="black")
        ctrl.view_update()

    with SinglePageWithDrawerLayout(server) as layout:
        layout.title.set_text(f"FLV Simulator — {jsonl_path.name}")

        with layout.toolbar:
            vuetify.VSpacer()
            vuetify.VTextField(
                value=("t_rel_s", 0.0),
                label="t, c",
                readonly=True,
                dense=True,
                hide_details=True,
                style="max-width: 120px",
            )
            vuetify.VTextField(
                value=("T_C", 0.0),
                label="T, °C",
                readonly=True,
                dense=True,
                hide_details=True,
                style="max-width: 120px",
            )
            vuetify.VTextField(
                value=("fsm_state", ""),
                label="FSM",
                readonly=True,
                dense=True,
                hide_details=True,
                style="max-width: 120px",
            )

        with layout.content:
            with vuetify.VContainer(fluid=True):
                view = trame_vtk.VtkLocalView(plotter.ren_win)
                ctrl.view_update = view.update
                vuetify.VSlider(
                    v_model=("frame", 0),
                    min=0,
                    max=state.frame_max,
                    step=1,
                    label="Кадр прогона",
                    hide_details=True,
                    dense=True,
                )

        @state.change("frame")
        def _on_frame(frame: int, **_kwargs: Any) -> None:  # type: ignore[no-untyped-def]
            update_frame(frame)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="viz.pyvista_3d")
    parser.add_argument("--run", required=True, type=Path, help="Путь к JSONL-логу прогона")
    parser.add_argument("--port", type=int, default=8080, help="Порт trame-сервера")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = build_app(args.run)
    server.start(port=args.port, exec_mode="main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
