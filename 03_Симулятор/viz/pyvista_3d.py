"""
viz.pyvista_3d — интерактивная 3D-визуализация термокамеры в браузере.

Стек: pyvista (геометрия + рендер) + trame (web UI) + Vuetify v2 + VTK.

UI-спецификация — см. ``02_Спецификация/ui_tokens.md`` v1.1. Этот модуль
является эталонной реализацией спеки и должен оставаться с ней
согласованным. Любые изменения UI начинаются с правки спеки.

Что показывается:

* термокамера — прозрачный куб 1×1×1 м (`color="lightgray"`, `opacity=0.15`);
* образец — цилиндр Ø100×200 мм; цвет берётся из colormap `plasma`
  по сигналу T_indicated_C (clim=[20, 250] °C);
* colorbar справа от viewport'а;
* легенда с подписями объектов сцены;
* toolbar — заголовок, три chip'а (t / T / FSM), переключатель языка
  RU/EN;
* drawer — метаданные прогона (scenario_id, тип, стенд, seed,
  длительность, число событий, файл, версия sim);
* footer — playback-контролы (skip-back / step-back / play-pause /
  step-fwd / skip-fwd) + slider + цветной FSM-таймлайн с подписями
  фаз и маркером инъекции (если есть).

Запуск:

    python -m viz.pyvista_3d --run path/to/run.jsonl
    # → http://localhost:8080
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Константы UI (соответствуют ui_tokens.md §3)
# ──────────────────────────────────────────────────────────────────────

# Цвета FSM-состояний — language-agnostic, тексты подменяются по lang.
# Все коды дают контраст белого текста ≥ 4.5:1 (WCAG AA).
FSM_COLORS: dict[str, str] = {
    "INIT": "#546E7A",     # blue-grey-darken-1
    "HEAT": "#E65100",     # orange-darken-4
    "HOLD": "#2E7D32",     # green-darken-3
    "MEASURE": "#1976D2",  # blue-darken-2
    "POST": "#616161",     # grey-darken-2
}
INJECTION_COLOR = "#C62828"  # red-darken-3
DEFAULT_FSM_COLOR = "#9E9E9E"

# Диапазон colormap'а для образца — соответствует физическому диапазону
# методики (T_min уставки 30 °C, T_max 250 °C по ГОСТ Р 8.563-2014).
CMAP_NAME = "plasma"
CMAP_CLIM = (20.0, 250.0)


# ──────────────────────────────────────────────────────────────────────
# Локализация (ui_tokens.md §13)
# ──────────────────────────────────────────────────────────────────────

TRANSLATIONS: dict[str, dict[str, Any]] = {
    "ru": {
        "app_title": "Симулятор FLV",
        "lang_toggle": "Язык интерфейса",
        "drawer_open": "Параметры прогона",
        "drawer_title": "Параметры прогона",
        "drawer_scenario": "Сценарий",
        "drawer_type": "Тип",
        "drawer_type_correct": "Корректный прогон",
        "drawer_type_injection": "Инъекция: {code}",
        "drawer_stand": "Стенд",
        "drawer_seed": "Seed",
        "drawer_duration": "Длительность",
        "drawer_events": "Событий",
        "drawer_file": "Файл",
        "drawer_sim_version": "Версия sim",
        "label_time": "t",
        "label_temp": "T",
        "unit_s": "c",
        "slider_label": "Время эксперимента",
        "btn_skip_back": "К началу прогона",
        "btn_step_back": "Назад на 10 событий",
        "btn_play": "Воспроизвести",
        "btn_pause": "Пауза",
        "btn_step_fwd": "Вперёд на 10 событий",
        "btn_skip_fwd": "К концу прогона",
        "fsm": {
            "INIT": "Подготовка",
            "HEAT": "Нагрев",
            "HOLD": "Стабилизация",
            "MEASURE": "Измерение",
            "POST": "Завершение",
        },
        "fsm_injection": "Инъекция",
        "loading": "Загрузка прогона…",
    },
    "en": {
        "app_title": "FLV Simulator",
        "lang_toggle": "Interface language",
        "drawer_open": "Run parameters",
        "drawer_title": "Run parameters",
        "drawer_scenario": "Scenario",
        "drawer_type": "Type",
        "drawer_type_correct": "Valid run",
        "drawer_type_injection": "Injection: {code}",
        "drawer_stand": "Stand",
        "drawer_seed": "Seed",
        "drawer_duration": "Duration",
        "drawer_events": "Events",
        "drawer_file": "File",
        "drawer_sim_version": "Simulator version",
        "label_time": "t",
        "label_temp": "T",
        "unit_s": "s",
        "slider_label": "Experiment time",
        "btn_skip_back": "To run start",
        "btn_step_back": "Back 10 events",
        "btn_play": "Play",
        "btn_pause": "Pause",
        "btn_step_fwd": "Forward 10 events",
        "btn_skip_fwd": "To run end",
        "fsm": {
            "INIT": "Setup",
            "HEAT": "Heating",
            "HOLD": "Stabilization",
            "MEASURE": "Measurement",
            "POST": "Wrap-up",
        },
        "fsm_injection": "Injection",
        "loading": "Loading run…",
    },
}


# ──────────────────────────────────────────────────────────────────────
# Helpers — парсинг event-log'а
# ──────────────────────────────────────────────────────────────────────


def _load_run(jsonl_path: Path) -> list[dict[str, Any]]:
    """Lazy-import event_logger, чтобы 3D-pipeline не тащил sim-зависимости
    при импорте модуля."""
    from sim.event_logger import load_jsonl

    return load_jsonl(jsonl_path)


def _t_of(event: dict[str, Any]) -> float:
    params = event.get("params") or {}
    return float(params.get("_ts_rel_s", 0.0))


def _extract_temperature_track(
    events: list[dict[str, Any]],
) -> list[tuple[float, float, str]]:
    """Из event-log собрать (t_rel_s, T_indicated_C, state) для всех
    событий, где есть signals.T. Это «кадры», по которым скрабит slider."""
    track: list[tuple[float, float, str]] = []
    for e in events:
        signals = e.get("signals") or {}
        if "T" not in signals:
            continue
        track.append((_t_of(e), float(signals["T"]), str(e.get("state", ""))))
    return track


def _compute_fsm_segments(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Свернуть последовательность событий в сегменты по FSM-состоянию.

    Каждый сегмент: ``{state, t_start, t_end, duration_s}``. Используется
    для рисования FSM-таймлайна в footer'е.
    """
    if not events:
        return []
    segments: list[dict[str, Any]] = []
    cur_state = str(events[0].get("state", "INIT"))
    cur_start = _t_of(events[0])
    last_t = cur_start
    for e in events[1:]:
        s = str(e.get("state", cur_state))
        t = _t_of(e)
        last_t = t
        if s != cur_state:
            segments.append({
                "state": cur_state,
                "t_start": cur_start,
                "t_end": t,
                "duration_s": t - cur_start,
            })
            cur_state = s
            cur_start = t
    # Финальный сегмент — до последнего события.
    segments.append({
        "state": cur_state,
        "t_start": cur_start,
        "t_end": last_t,
        "duration_s": last_t - cur_start,
    })
    return [s for s in segments if s["duration_s"] > 0]


def _detect_injection(
    scenario_id: str,
    filename: str,
) -> dict[str, Any] | None:
    """Определить, был ли прогон с инъекцией, по имени сценария.

    Конвенция (см. ``03_Симулятор/scenarios/``): ``s1_correct`` — без
    инъекции; ``s1_<code>`` (например, ``s1_time_under``) — с инъекцией
    ``<code>``. Возвращаем code в верхнем регистре.
    """
    source = (scenario_id or filename or "").lower()
    m = re.match(r"s\d+_([a-z_]+)", source)
    if not m:
        return None
    code_lower = m.group(1)
    if code_lower in {"correct", "ok", "valid", "baseline"}:
        return None
    return {"code": code_lower.upper().replace("_", "_")}


def _extract_metadata(
    events: list[dict[str, Any]],
    jsonl_path: Path,
) -> dict[str, Any]:
    """Собрать метаданные прогона из event-log + имени файла."""
    meta: dict[str, Any] = {
        "scenario_id": "",
        "stand_id": "",
        "seed": None,
        "duration_s": 0.0,
        "n_events": len(events),
        "filename": jsonl_path.name,
        "sim_version": "",
    }
    if not events:
        return meta

    first = events[0]
    meta["stand_id"] = str(first.get("stand_id", ""))
    # run_id обычно содержит scenario_id; конвенция: "s1_correct-001"
    run_id = str(first.get("run_id", ""))
    if "-" in run_id:
        meta["scenario_id"] = run_id.rsplit("-", 1)[0]
    else:
        meta["scenario_id"] = run_id

    # meta-блок есть только на RUN_START
    for e in events[:5]:  # достаточно посмотреть начало
        m = e.get("meta") or {}
        if "simulator_version" in m and not meta["sim_version"]:
            meta["sim_version"] = str(m["simulator_version"])

    # Seed конвенция: имя файла "scenario-NNN.jsonl" → 1000 + NNN, либо из run_id хвоста.
    fname_match = re.search(r"-(\d+)\.jsonl$", jsonl_path.name)
    if fname_match:
        meta["seed"] = int(fname_match.group(1))

    # Длительность — от первого до последнего ts_rel_s.
    meta["duration_s"] = _t_of(events[-1]) - _t_of(events[0])
    return meta


# ──────────────────────────────────────────────────────────────────────
# CSS (ui_tokens.md §4.4 + §3)
# ──────────────────────────────────────────────────────────────────────

CSS_GLOBAL = """
.fsm-strip {
    position: relative;
    display: flex;
    height: 28px;
    width: 100%;
    overflow: visible;
    border-radius: 4px;
    margin: 8px 16px 0;
    box-sizing: border-box;
}
.fsm-seg {
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-family: 'Roboto', sans-serif;
    font-size: 11px;
    font-weight: 500;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    padding: 0 6px;
    min-width: 0;
}
.fsm-seg:first-child { border-radius: 4px 0 0 4px; }
.fsm-seg:last-child { border-radius: 0 4px 4px 0; }
.fsm-playhead {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 2px;
    background: #FFFFFF;
    mix-blend-mode: difference;
    pointer-events: none;
    z-index: 5;
}
.fsm-injection-marker {
    position: absolute;
    top: -10px;
    bottom: -2px;
    width: 2px;
    background: #C62828;
    z-index: 4;
    pointer-events: none;
}
.fsm-injection-marker::before {
    content: "⚠";
    position: absolute;
    top: -16px;
    left: -7px;
    color: #C62828;
    font-size: 14px;
    font-weight: bold;
}
.flv-num-chip {
    font-family: 'Roboto Mono', SFMono-Regular, monospace !important;
    font-variant-numeric: tabular-nums;
}
.flv-counter {
    font-family: 'Roboto Mono', SFMono-Regular, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    color: #424242;
    white-space: nowrap;
}
.flv-drawer-label {
    font-size: 12px;
    color: #757575;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 12px;
}
.flv-drawer-value {
    font-size: 14px;
    color: #212121;
    font-weight: 500;
    word-break: break-all;
}
.flv-drawer-value.mono {
    font-family: 'Roboto Mono', SFMono-Regular, monospace;
    font-variant-numeric: tabular-nums;
}
"""


# ──────────────────────────────────────────────────────────────────────
# Сборка trame-приложения
# ──────────────────────────────────────────────────────────────────────


def build_app(jsonl_path: Path) -> Any:  # noqa: PLR0915 — единая фабрика приложения
    """Собрать trame-приложение для конкретного прогона.

    Возвращает trame.app.Server, который запускается через ``server.start()``.
    """
    try:
        import numpy as np  # type: ignore[import-not-found]
        import pyvista as pv  # type: ignore[import-not-found]
        from pyvista.trame.ui import plotter_ui  # type: ignore[import-not-found]
        from trame.app import get_server  # type: ignore[import-not-found]
        from trame.ui.vuetify import SinglePageWithDrawerLayout  # type: ignore[import-not-found]
        from trame.widgets import html as trame_html  # type: ignore[import-not-found]
        from trame.widgets import vuetify  # type: ignore[import-not-found]
    except ImportError as e:
        raise SystemExit(
            "Для 3D-визуализации требуются pyvista, numpy и trame.\n"
            "Установи: pip install -e \".[viz3d]\" из 03_Симулятор/.\n"
            f"Detail: {e}"
        ) from e

    # ───── Парсинг прогона ──────────────────────────────────────────
    events = _load_run(jsonl_path)
    track = _extract_temperature_track(events)
    if not track:
        raise SystemExit(
            f"Лог пуст или не содержит сигнала температуры: {jsonl_path}. "
            "Проверьте, что сценарий запускался с включённым sensor-каналом T."
        )

    raw_segments = _compute_fsm_segments(events)
    metadata = _extract_metadata(events, jsonl_path)
    injection = _detect_injection(metadata["scenario_id"], jsonl_path.name)

    # ───── 3D-сцена ────────────────────────────────────────────────
    chamber = pv.Cube(
        center=(0, 0, 0), x_length=1.0, y_length=1.0, z_length=1.0,
    )
    sample = pv.Cylinder(
        center=(0, 0, -0.1), direction=(0, 0, 1), radius=0.05, height=0.2,
    )
    # Скаляр T для colormap'а — равен текущей T_C на всех точках.
    sample.point_data["T"] = np.full(sample.n_points, track[0][1], dtype=float)

    plotter = pv.Plotter(notebook=False)
    plotter.set_background("#FFFFFF")
    plotter.add_mesh(
        chamber, color="lightgray", opacity=0.15, show_edges=True,
    )
    plotter.add_mesh(
        sample,
        scalars="T",
        cmap=CMAP_NAME,
        clim=list(CMAP_CLIM),
        show_edges=True,
        edge_color="#212121",
        line_width=0.5,
        scalar_bar_args={
            "title": "T, °C",
            "n_labels": 6,
            "title_font_size": 14,
            "label_font_size": 12,
            "color": "black",
            "vertical": True,
        },
    )
    plotter.add_legend(
        [
            ["Chamber 1×1×1 m", "lightgray"],
            ["Sample Ø100×200 mm", FSM_COLORS["MEASURE"]],
        ],
        bcolor="white",
        border=True,
        size=(0.22, 0.10),
        loc="upper left",
    )
    plotter.camera_position = [(2.0, 2.0, 2.0), (0, 0, 0), (0, 0, 1)]
    plotter.reset_camera()

    # ───── trame server ────────────────────────────────────────────
    server = get_server(client_type="vue2")
    state, ctrl = server.state, server.controller

    # State init.
    initial_lang = "ru"
    state.lang = initial_lang
    state.t = TRANSLATIONS[initial_lang]
    state.frame = 0
    state.frame_max = max(0, len(track) - 1)
    state.t_rel_s = float(track[0][0])
    state.T_C = float(track[0][1])
    state.fsm_state = str(track[0][2]) or "INIT"
    state.fsm_human = TRANSLATIONS[initial_lang]["fsm"].get(state.fsm_state, state.fsm_state)
    state.fsm_color = FSM_COLORS.get(state.fsm_state, DEFAULT_FSM_COLOR)
    state.playing = False

    # Метаданные → state (для drawer'а).
    state.meta_scenario = metadata["scenario_id"] or "—"
    state.meta_stand = metadata["stand_id"] or "—"
    state.meta_seed = str(metadata["seed"]) if metadata["seed"] is not None else "—"
    state.meta_duration = f"{metadata['duration_s']:.1f}"
    state.meta_n_events = str(metadata["n_events"])
    state.meta_filename = metadata["filename"]
    state.meta_sim_version = metadata["sim_version"] or "—"

    # FSM-сегменты для таймлайна (плюс flex-доли и cumulative percent).
    total_duration = max(1e-9, sum(s["duration_s"] for s in raw_segments))

    def _build_segments_for_state(lang: str) -> list[dict[str, Any]]:
        humans = TRANSLATIONS[lang]["fsm"]
        out: list[dict[str, Any]] = []
        for seg in raw_segments:
            out.append({
                "state": seg["state"],
                "label": humans.get(seg["state"], seg["state"]),
                "color": FSM_COLORS.get(seg["state"], DEFAULT_FSM_COLOR),
                "flex": seg["duration_s"] / total_duration,
                "t_start": round(seg["t_start"], 2),
                "t_end": round(seg["t_end"], 2),
            })
        return out

    state.fsm_segments = _build_segments_for_state(initial_lang)
    # Marker инъекции: проценты по таймлайну. Если инъекция есть,
    # привязываем её к началу первого сегмента, отличного от INIT/HEAT
    # (для всех s1_*-сценариев это HOLD/MEASURE).
    if injection:
        attach_seg = next(
            (s for s in raw_segments if s["state"] in {"HOLD", "MEASURE"}),
            raw_segments[0] if raw_segments else None,
        )
        if attach_seg:
            t_inj = attach_seg["t_start"]
            inj_pct = (t_inj - raw_segments[0]["t_start"]) / total_duration * 100.0
        else:
            inj_pct = 0.0
        state.injection = {"code": injection["code"], "pct": inj_pct}
    else:
        state.injection = None

    # Counter для footer'а («00:01:15 / 00:10:37»).
    def _fmt_time(seconds: float) -> str:
        s = int(round(seconds))
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    state.counter_now = _fmt_time(state.t_rel_s)
    state.counter_max = _fmt_time(track[-1][0])

    # ───── Контроллеры ─────────────────────────────────────────────

    def _apply_frame(frame: int) -> None:
        i = max(0, min(int(frame), state.frame_max))
        t_rel, T_C, fsm = track[i]
        state.t_rel_s = float(t_rel)
        state.T_C = float(T_C)
        state.fsm_state = str(fsm)
        state.fsm_human = TRANSLATIONS[state.lang]["fsm"].get(fsm, fsm)
        state.fsm_color = FSM_COLORS.get(fsm, DEFAULT_FSM_COLOR)
        state.counter_now = _fmt_time(t_rel)
        # Обновить scalar-поле образца — pyvista пересчитает цвет
        # через lookup table (cmap=plasma). Модифицируем in-place, потом
        # явно зовём Modified() — этим пайплайн VTK помечается dirty.
        sample.point_data["T"][:] = float(T_C)
        sample.Modified()
        ctrl.view_update()

    @ctrl.set("update_frame")
    def update_frame(frame: int) -> None:
        _apply_frame(frame)

    @ctrl.set("toggle_play")
    def toggle_play() -> None:
        state.playing = not state.playing

    @ctrl.set("seek_start")
    def seek_start() -> None:
        state.playing = False
        state.frame = 0

    @ctrl.set("seek_end")
    def seek_end() -> None:
        state.playing = False
        state.frame = state.frame_max

    @ctrl.set("step_back")
    def step_back() -> None:
        state.playing = False
        state.frame = max(0, int(state.frame) - 10)

    @ctrl.set("step_fwd")
    def step_fwd() -> None:
        state.playing = False
        state.frame = min(state.frame_max, int(state.frame) + 10)

    @ctrl.set("seek_segment")
    def seek_segment(t_start: float) -> None:
        state.playing = False
        # Найти первый кадр в track с t_rel >= t_start.
        for idx, (t_rel, _, _) in enumerate(track):
            if t_rel >= t_start:
                state.frame = idx
                return
        state.frame = state.frame_max

    # Auto-play loop. 10× ускорение: 1 секунда реального времени = 10
    # секунд эксперимента. Шаг между кадрами в track задаётся симулятором
    # (обычно dt_log = 1 c), значит интервал 100 мс между frame++.
    play_interval_ms = 100

    async def _play_loop() -> None:  # noqa: RUF029 — long-running task
        while True:
            await asyncio.sleep(play_interval_ms / 1000.0)
            if state.playing:
                if int(state.frame) >= state.frame_max:
                    state.playing = False
                else:
                    with state:
                        state.frame = int(state.frame) + 1

    # Lazy-старт play-loop'а: запускаем асинхронную задачу при первом
    # переключении state.playing → True. К этому моменту trame-сервер
    # уже стартовал и asyncio loop работает.
    _play_task: dict[str, Any] = {"task": None}

    def _ensure_play_task() -> None:
        if _play_task["task"] is not None:
            return
        try:
            _play_task["task"] = asyncio.create_task(_play_loop())
        except RuntimeError:
            logger.warning(
                "Auto-play отключён: asyncio loop недоступен; "
                "используйте step-кнопки",
            )

    # ───── Layout ──────────────────────────────────────────────────
    with SinglePageWithDrawerLayout(server) as layout:
        # Глобальные стили (добавляются в DOM в составе v-app).
        trame_html.Style(CSS_GLOBAL)

        layout.title.set_text(f"{TRANSLATIONS[initial_lang]['app_title']}")

        # ── Toolbar ────────────────────────────────────────────────
        with layout.toolbar:
            vuetify.VSpacer()

            # Chip t.
            vuetify.VChip(
                children=[
                    "{{ t.label_time }} = {{ t_rel_s.toFixed(1) }} {{ t.unit_s }}",
                ],
                color="#F5F5F5",
                text_color="#212121",
                small=True,
                classes="flv-num-chip mr-2",
                role="status",
                aria_live="polite",
            )
            # Chip T.
            vuetify.VChip(
                children=[
                    "{{ t.label_temp }} = {{ T_C.toFixed(2) }} °C",
                ],
                color="#FFEBEE",
                text_color="#212121",
                small=True,
                classes="flv-num-chip mr-2",
                role="status",
                aria_live="polite",
            )
            # Chip FSM.
            vuetify.VChip(
                children=["{{ fsm_human }}"],
                color=("fsm_color",),
                text_color="white",
                dark=True,
                small=True,
                classes="mr-2",
                role="status",
                aria_live="polite",
                style="min-width:96px; justify-content:center;",
            )

            # Lang toggle (RU / EN).
            with vuetify.VBtnToggle(
                v_model=("lang", initial_lang),
                mandatory=True,
                dense=True,
                rounded=True,
                background_color="primary",
                aria_label=("t.lang_toggle",),
            ):
                vuetify.VBtn(
                    children=["RU"],
                    value="ru",
                    small=True,
                    style="min-width:36px;",
                )
                vuetify.VBtn(
                    children=["EN"],
                    value="en",
                    small=True,
                    style="min-width:36px;",
                )

        # ── Drawer (метаданные прогона) ────────────────────────────
        with layout.drawer:
            with vuetify.VContainer(fluid=True, classes="pa-4"):
                vuetify.VSubheader(children=["{{ t.drawer_title }}"])

                # Сценарий
                trame_html.Div(
                    children=["{{ t.drawer_scenario }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_scenario }}"],
                    classes="flv-drawer-value mono",
                )

                # Тип
                trame_html.Div(
                    children=["{{ t.drawer_type }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=[
                        "{{ injection ? "
                        "t.drawer_type_injection.replace('{code}', injection.code) "
                        ": t.drawer_type_correct }}",
                    ],
                    classes="flv-drawer-value",
                )

                # Стенд
                trame_html.Div(
                    children=["{{ t.drawer_stand }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_stand }}"],
                    classes="flv-drawer-value",
                )

                # Seed
                trame_html.Div(
                    children=["{{ t.drawer_seed }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_seed }}"],
                    classes="flv-drawer-value mono",
                )

                # Длительность
                trame_html.Div(
                    children=["{{ t.drawer_duration }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=[
                        "{{ meta_duration }} {{ t.unit_s }}",
                    ],
                    classes="flv-drawer-value mono",
                )

                # Событий
                trame_html.Div(
                    children=["{{ t.drawer_events }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_n_events }}"],
                    classes="flv-drawer-value mono",
                )

                # Файл
                trame_html.Div(
                    children=["{{ t.drawer_file }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_filename }}"],
                    classes="flv-drawer-value mono",
                )

                # Версия sim
                trame_html.Div(
                    children=["{{ t.drawer_sim_version }}"],
                    classes="flv-drawer-label",
                )
                trame_html.Div(
                    children=["{{ meta_sim_version }}"],
                    classes="flv-drawer-value mono",
                )

        # ── Content (3D viewport) ──────────────────────────────────
        with layout.content:
            with vuetify.VContainer(
                fluid=True,
                classes="pa-0",
                style=(
                    "position: relative; "
                    "height: calc(100vh - 64px - 88px); "
                    "overflow: hidden;"
                ),
                role="application",
                aria_label=("'3D viewport'",),
                tabindex="-1",
            ):
                view = plotter_ui(plotter, mode="trame")
                ctrl.view_update = view.update

            # ── Footer ─────────────────────────────────────────────
            with vuetify.VFooter(
                app=True,
                inset=True,
                color="#FAFAFA",
                style="height: 88px; padding: 0; flex-direction: column;",
            ):
                # Верхний ряд: playback + slider + counter.
                with vuetify.VRow(
                    align="center",
                    no_gutters=True,
                    classes="px-4",
                    style="width:100%; height:40px;",
                ):
                    # Skip-back.
                    with vuetify.VBtn(
                        icon=True,
                        large=True,
                        click=ctrl.seek_start,
                        aria_label=("t.btn_skip_back",),
                    ):
                        vuetify.VIcon(children=["mdi-skip-backward"])
                    # Step-back.
                    with vuetify.VBtn(
                        icon=True,
                        large=True,
                        click=ctrl.step_back,
                        aria_label=("t.btn_step_back",),
                    ):
                        vuetify.VIcon(children=["mdi-step-backward"])
                    # Play / Pause.
                    with vuetify.VBtn(
                        icon=True,
                        large=True,
                        click=ctrl.toggle_play,
                        aria_label=("playing ? t.btn_pause : t.btn_play",),
                    ):
                        vuetify.VIcon(
                            children=["{{ playing ? 'mdi-pause' : 'mdi-play' }}"],
                        )
                    # Step-fwd.
                    with vuetify.VBtn(
                        icon=True,
                        large=True,
                        click=ctrl.step_fwd,
                        aria_label=("t.btn_step_fwd",),
                    ):
                        vuetify.VIcon(children=["mdi-step-forward"])
                    # Skip-fwd.
                    with vuetify.VBtn(
                        icon=True,
                        large=True,
                        click=ctrl.seek_end,
                        aria_label=("t.btn_skip_fwd",),
                    ):
                        vuetify.VIcon(children=["mdi-skip-forward"])

                    # Slider.
                    vuetify.VSlider(
                        v_model=("frame", 0),
                        min=0,
                        max=state.frame_max,
                        step=1,
                        hide_details=True,
                        dense=True,
                        classes="mx-4",
                        aria_label=("t.slider_label",),
                        aria_valuetext=(
                            "t_rel_s.toFixed(1) + ' ' + t.unit_s",
                        ),
                    )

                    # Counter.
                    trame_html.Div(
                        children=[
                            "{{ counter_now }} / {{ counter_max }}",
                        ],
                        classes="flv-counter",
                    )

                # Нижний ряд: FSM-таймлайн.
                with trame_html.Div(
                    classes="fsm-strip",
                    role="img",
                    aria_label=(
                        "'FSM timeline: ' + fsm_segments.map(s => s.label).join(', ')",
                    ),
                ):
                    with trame_html.Div(
                        v_for="seg in fsm_segments",
                        key="seg.t_start",
                        classes="fsm-seg",
                        style=(
                            "`flex: ${seg.flex} 1 0; "
                            "background-color: ${seg.color};`",
                        ),
                        click=("seek_segment(seg.t_start)",),
                        title=(
                            "`${seg.label}: ${seg.t_start}–${seg.t_end} ` + t.unit_s",
                        ),
                    ):
                        trame_html.Span(children=["{{ seg.label }}"])

                    # Playhead.
                    trame_html.Div(
                        classes="fsm-playhead",
                        style=(
                            "`left: ${(t_rel_s / "
                            f"{max(track[-1][0], 1e-9)}"
                            ") * 100}%;`",
                        ),
                    )
                    # Injection marker.
                    with trame_html.Div(
                        v_if="injection",
                        classes="fsm-injection-marker",
                        style=("`left: ${injection.pct}%;`",),
                        title=(
                            "t.drawer_type_injection.replace('{code}', injection.code)",
                        ),
                    ):
                        pass

        # ── State change callbacks ─────────────────────────────────
        @state.change("frame")
        def _on_frame(frame: int, **_kwargs: Any) -> None:  # type: ignore[no-untyped-def]
            update_frame(frame)

        @state.change("lang")
        def _on_lang(lang: str, **_kwargs: Any) -> None:  # type: ignore[no-untyped-def]
            if lang not in TRANSLATIONS:
                lang = "ru"
            state.t = TRANSLATIONS[lang]
            state.fsm_segments = _build_segments_for_state(lang)
            state.fsm_human = TRANSLATIONS[lang]["fsm"].get(state.fsm_state, state.fsm_state)
            # Заголовок Vuetify-layout'а — обновить нельзя реактивно
            # (layout.title.set_text() работает только при сборке);
            # игнорируем, так как app_title виден в title-баре, и его
            # обновление — побочный эффект.

        @state.change("playing")
        def _on_playing(playing: bool, **_kwargs: Any) -> None:  # type: ignore[no-untyped-def]
            if playing:
                _ensure_play_task()

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="viz.pyvista_3d")
    parser.add_argument(
        "--run", required=True, type=Path,
        help="Путь к JSONL-логу прогона",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Порт trame-сервера",
    )
    args = parser.parse_args(argv)

    if not args.run.exists():
        raise SystemExit(
            f"Не удалось открыть лог: {args.run}. Проверьте путь к файлу."
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = build_app(args.run)
    server.start(port=args.port, exec_mode="main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
