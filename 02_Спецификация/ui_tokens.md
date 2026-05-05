# UI-спецификация: 3D-viewer термокамеры

> **Версия:** 1.0 · **Дата:** 2026-05-05 · **Артефакт фазы:** Phase 3.12 (post-redesign)
> **Применимо к:** `03_Симулятор/viz/pyvista_3d.py`
> **Стек:** Python · PyVista · trame · Vuetify v2 · VTK
> **Цель:** зафиксировать токены, компоненты и поведение интерактивного просмотрщика прогонов до того, как он будет показан комиссии. Этот документ — единственный источник истины для UI; код приводится в соответствие.

## 1. Обзор

3D-viewer — это веб-приложение на trame, открывающееся в браузере по адресу `http://localhost:8080`, которое визуализирует записанный прогон симулятора (event-log JSONL) как 3D-сцену термокамеры с образцом, чей цвет меняется по температуре. Дополнительно — таймлайн прогона с разметкой по FSM-состояниям и метаданные прогона в drawer'е.

Целевая аудитория — комиссия защиты ВКР, на проекторе или по видеосвязи. Задача — за 5 секунд понять, что на экране (термокамера + образец + ход эксперимента во времени), и за 10 секунд — найти момент инъекции нарушения и видимый эффект на сигнал.

**Язык интерфейса:** русский по умолчанию, переключатель `RU / EN` в toolbar. Все лейблы хранятся в одной таблице переводов (см. §15) и подменяются через computed-property `t(key)`. Выбор сохраняется в `localStorage["flv_viewer_lang"]` и восстанавливается между перезагрузками.

## 2. Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  [≡]  Симулятор FLV · s1_correct · seed 42  [t][T][FSM] [RU/EN]│  ← toolbar 64 px
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│ Drawer   │        3D viewport (PyVista plotter_ui)              │
│ (280 px, │                                                      │
│ collap-  │        ┌────────────────────────┐                    │
│ sible)   │        │  [Термокамера, куб]    │   colorbar →       │
│          │        │     [Образец, цил.]    │                    │
│ Параметры│        └────────────────────────┘                    │
│ прогона  │                                                      │
│          │   Легенда: ▭ Термокамера 1×1×1 м                     │
│ scenario │           ◯ Образец Ø100×200 мм                      │
│ seed     │                                                      │
│ ...      │                                                      │
├──────────┴──────────────────────────────────────────────────────┤
│  ⏮ ⏪ ▶/⏸ ⏩ ⏭   ▬▬▬▬▬▬▬▬◉▬▬▬▬   00:00:00 / 00:10:37          │  ← footer 88 px
│  ┌──────┬──────────┬─────────────┬─────────┬──────┐             │
│  │ Подг │  Нагрев  │ Стабилизация│Измерение│Заверш│  ← FSM-полоса │
│  └──────┴──────────┴─────────────┴─────────┴──────┘             │
└─────────────────────────────────────────────────────────────────┘
```

Высоты фиксированы: toolbar — 64 px, footer — 88 px (40 px playback row + 48 px FSM-полоса). Viewport: `calc(100vh - 64px - 88px)`. Drawer — 280 px, открывается по клику на гамбургер.

## 3. Design tokens

### 3.1 Colors

| Token | Hex | Применение | WCAG vs white |
|---|---|---|---|
| `color-bg-app` | `#FFFFFF` | основной фон контейнера | — |
| `color-bg-scene` | `#FFFFFF` | фон 3D-сцены | — |
| `color-bg-toolbar` | `#1976D2` | toolbar background (Vuetify primary) | — |
| `color-bg-footer` | `#FAFAFA` | footer / playback panel | — |
| `color-bg-chip-num` | `#F5F5F5` | chip с числовым значением | — |
| `color-text-primary` | `#212121` | основной текст | 16.1:1 ✅ |
| `color-text-on-toolbar` | `#FFFFFF` | заголовок и иконки на toolbar | 4.7:1 ✅ |
| `color-text-num` | `#212121` | t/T значения в chip'ах | 16.1:1 ✅ |
| `color-accent-T` | `#FFEBEE` | подложка chip'а T (ассоциация с теплом) | text 15.4:1 ✅ |
| `color-edge` | `#212121` | контур цилиндра (silhouette) | 16.1:1 ✅ |

### 3.2 FSM state tokens

Каждое состояние имеет цвет и человекочитаемую подпись. Цвет для chip'а в toolbar и для сегмента FSM-полосы — один и тот же (консистентность).

| State id | RU label | EN label | Token | Hex | White text contrast |
|---|---|---|---|---|---|
| `INIT` | Подготовка | Setup | `color-fsm-init` | `#546E7A` (blue-grey-darken-1) | 5.5:1 ✅ |
| `HEAT` | Нагрев | Heating | `color-fsm-heat` | `#E65100` (orange-darken-4) | 4.6:1 ✅ |
| `HOLD` | Стабилизация | Stabilization | `color-fsm-hold` | `#2E7D32` (green-darken-3) | 5.6:1 ✅ |
| `MEASURE` | Измерение | Measurement | `color-fsm-measure` | `#1976D2` (blue-darken-2) | 4.7:1 ✅ |
| `POST` | Завершение | Wrap-up | `color-fsm-post` | `#616161` (grey-darken-2) | 5.7:1 ✅ |
| `INJECTION` | Инъекция | Injection | `color-fsm-injection` | `#C62828` (red-darken-3) | 6.4:1 ✅ |

Цвета — language-agnostic (одинаковые для ru и en), только текстовые подписи подменяются по `state.lang`.

Маркер инъекции — вертикальная полоса 2 px на FSM-таймлайне + иконка `mdi-alert` (⚠) над ней + tooltip с кодом инъекции (`TIME_UNDER`, `T_SET_BAD`, и т.п.).

### 3.3 Colormap для образца

`plasma` (matplotlib / ColorBrewer). Диапазон `clim=[20, 250]` °C. Colorbar: вертикальный, справа от viewport, title `Температура образца, °C`, 6 делений.

Известная проблема: жёлтый конец plasma на белом фоне даёт 1.5:1 контраст. Митигация — `show_edges=True, edge_color="#212121", line_width=0.5` на цилиндре, силуэт читается всегда.

### 3.4 Typography

| Token | Spec | Применение |
|---|---|---|
| `font-family-base` | `Roboto, -apple-system, sans-serif` | весь UI (Vuetify default) |
| `font-family-mono` | `Roboto Mono, SFMono-Regular, monospace` | числовые значения (t, T, seed, длительность) |
| `font-toolbar-title` | 600, 18 px, line-height 1.2 | заголовок в toolbar |
| `font-chip-num` | 500, 14 px, `tabular-nums` | t, T в chip'ах |
| `font-chip-fsm` | 600, 14 px, uppercase | FSM chip |
| `font-drawer-label` | 400, 12 px, color #757575 | подписи полей в drawer'е |
| `font-drawer-value` | 500, 14 px | значения полей в drawer'е |
| `font-segment-label` | 500, 11 px, white | подписи сегментов FSM-полосы |
| `font-tooltip` | 400, 12 px | tooltip на кнопках |

Для всех чисел — `font-variant-numeric: tabular-nums`, чтобы значения не «прыгали» при обновлении.

### 3.5 Spacing

Базовая шкала Vuetify: `4 px` (xs), `8 px` (sm), `16 px` (md), `24 px` (lg), `32 px` (xl).

| Контекст | Spacing |
|---|---|
| Toolbar padding-x | 16 px |
| Между chip'ами в toolbar | 8 px |
| Drawer внутренние отступы | 16 px |
| Playback кнопки между собой | 4 px |
| Slider `mx` | 16 px |
| FSM-полоса padding-x | 16 px (выравнено со slider'ом) |

### 3.6 Sizes

| Элемент | Размер | Источник |
|---|---|---|
| Toolbar height | 64 px | Vuetify default |
| Footer height | 88 px (40 + 48) | заданное |
| Drawer width | 280 px | Vuetify default |
| Playback button | 44×44 px | WCAG 2.5.5 |
| FSM chip min-width | 96 px | для самой длинной подписи «Стабилизация» |
| Number chip min-width | 88 px (t), 104 px (T) | tabular-nums + units |
| Slider thumb | 16 px (rest), 20 px (active) | Vuetify default |
| Slider track | 4 px | Vuetify default |
| FSM segment min-width | 64 px | чтобы текст-метка читалась |
| Injection marker | 2 px width, 24 px above strip | заметно, не перекрывает |

## 4. Components

### 4.1 Toolbar

```
[≡] {t.app_title} · {scenario_id} · seed {seed}   [chip-t] [chip-T] [chip-FSM] [RU|EN]
```

**Левый край.** Drawer-toggle (`mdi-menu`, 44×44, `:aria-label="t.drawer_open"`) + заголовок `font-toolbar-title` белый. Заголовок не truncate'ится — на узком экране переносится в drawer.

**Правый край.** Три chip'а в горизонтальной линии + языковой переключатель:

- **chip-t** (`v-chip color="#F5F5F5"` text-color `color-text-num`): `{{ t.label_time }} = {{ t_rel_s.toFixed(1) }} {{ t.unit_s }}`
- **chip-T** (`v-chip color="#FFEBEE"` text-color `color-text-num`): `{{ t.label_temp }} = {{ T_C.toFixed(2) }} °C`
- **chip-FSM** (`v-chip :color="fsmColor[fsm_state]"` text-color `white`, dark): `{{ t.fsm[fsm_state] }}`
- **lang-toggle** (`v-btn-toggle v-model="lang" mandatory dense`): два сегмента `RU` / `EN`, `min-width 36 px` каждый, активный — `color="primary"`. `aria-label="t.lang_toggle"`.

Все три chip'а имеют:
- `role="status" aria-live="polite"` — screen-reader зачитывает обновления.
- `:aria-label` с полной подписью (для ru — «Время эксперимента: 75.3 секунд»; для en — «Experiment time: 75.3 seconds»).
- Number chip'ы — моноширинные с `tabular-nums`.
- На узком экране (<960 px) chip'ы переносятся в drawer (через `v-if="$vuetify.breakpoint.smAndDown"`).

Переключение языка — мгновенное, без анимации. После клика lang сохраняется в `state.lang`, который связан с `localStorage` через `@state.change("lang")` callback. Все computed-properties с переводами реактивно пересчитываются.

### 4.2 Drawer

Заголовок: `Параметры прогона`. Содержание — двухколоночная сетка label/value:

| Label | Token | Источник в event-log |
|---|---|---|
| Сценарий | font-mono | `meta.scenario_id` |
| Тип | — | если `meta.injection` есть → `Инъекция: {code}`; иначе `Корректный прогон` |
| Стенд | — | `meta.stand_id` (например `S1 — термокамера PT100`) |
| Seed | font-mono | `meta.seed` |
| Длительность | font-mono | `track[-1].t_rel_s.toFixed(1) + ' с'` |
| Событий | font-mono | `len(events)` |
| Файл | font-mono, ellipsis | `path.name` |
| Версия sim | font-mono | `meta.simulator_version` |

Если drawer открыт — viewport не сдвигается (overlay-режим), чтобы не ломать камеру.

### 4.3 Viewport

3D-сцена через `pyvista.trame.ui.plotter_ui(plotter, mode="trame")`.

**Сцена:**
- `plotter.set_background("#FFFFFF")`.
- Куб камеры: `pv.Cube(1×1×1)`, `color="lightgray"`, `opacity=0.15`, `show_edges=True, line_width=1`.
- Цилиндр-образец: `pv.Cylinder(radius=0.05, height=0.2)`, scalars=`T_C`, `cmap="plasma"`, `clim=[20,250]`, `show_edges=True, edge_color="#212121", line_width=0.5`.
- Colorbar: справа, vertical, title `Температура образца, °C`, 6 ticks.
- Legend: левый-верх, два пункта (`Термокамера 1×1×1 м` / `Образец Ø100×200 мм`).
- HUD-текст FSM (`add_text`) — **удалён**, состояние читается с chip'а в toolbar.
- Камера: `position=[(2,2,2),(0,0,0),(0,0,1)]` + `reset_camera()`.

**Контейнер:**
- `<div role="application" aria-label="3D-визуализация термокамеры с образцом" tabindex="-1">`.
- `tabindex="-1"` — viewport не входит в tab-цепочку (избегаем focus-trap).

### 4.4 Footer

Высота 88 px. Разбита на две строки.

**Верхняя строка (40 px) — playback + slider + counter:**

```
[⏮] [⏪] [▶/⏸] [⏩] [⏭]   ▬▬▬▬▬▬▬◉▬▬▬▬▬▬▬   00:01:15 / 00:10:37
```

| Элемент | Spec |
|---|---|
| Skip-back | `v-btn icon size="large" :aria-label="t.btn_skip_back"` · `mdi-skip-backward` |
| Step-back | `v-btn icon size="large" :aria-label="t.btn_step_back"` · `mdi-step-backward` |
| Play/Pause | `v-btn icon size="large" :aria-label="state.playing ? t.btn_pause : t.btn_play"` · `mdi-play` / `mdi-pause` |
| Step-fwd | `v-btn icon size="large" :aria-label="t.btn_step_fwd"` · `mdi-step-forward` |
| Skip-fwd | `v-btn icon size="large" :aria-label="t.btn_skip_fwd"` · `mdi-skip-forward` |
| Slider | `v-slider :aria-label="t.slider_label"` · `min=0`, `max=t_max`, `step=0.1`, mono-counter `{t_rel_s} / {t_max}` справа |

Все строки берутся из таблицы переводов §13.1, реактивно меняются при переключении `state.lang`.

Все 5 кнопок имеют `tooltip` с человекочитаемой подписью (см. UX-copy раздел).

**Нижняя строка (48 px) — FSM-таймлайн:**

Контейнер `role="img" :aria-label="'Фазы прогона: ' + segments.map(s => s.label).join(', ')"`. Внутри — flex-row сегментов, ширина каждого пропорциональна `(t_end - t_start) / total_duration`. На каждом сегменте:

- background: `fsmColor[state_id]`.
- внутри: `<span class="font-segment-label white--text">{{ fsmHuman[state] }}</span>`, по центру.
- `data-state` attribute для отладки.
- min-width 64 px; если сегмент короче — текст truncate с tooltip с полным названием.

Поверх — вертикальная линия playhead `position:absolute; left: ${t_rel_s/t_max*100}%; width:2px; bg:#FFFFFF; mix-blend-mode:difference`. Маркер инъекции — отдельная `position:absolute; left: ${t_inj/t_max*100}%; width:2px; bg:color-fsm-injection`, с иконкой `mdi-alert` 24 px над полосой.

## 5. States

### 5.1 Playback states

| State | `state.playing` | `state.frame` | UI |
|---|---|---|---|
| Idle | `false` | 0 | play-btn shows ▶, slider at left |
| Playing | `true` | increments | play-btn shows ⏸, slider moves |
| Paused | `false` | last position | play-btn shows ▶, slider at last |
| End | `false` | `frame_max` | play-btn shows ▶, скип-форвард disabled |

**Auto-pause при scrub:** когда пользователь начинает drag слайдера — `state.playing = false`. Без авто-резюма.

### 5.2 Loading state

При первом открытии страницы (event-log парсится, plotter инициализируется): `<v-progress-linear indeterminate>` поверх toolbar + текст «Загрузка прогона…» по центру viewport'а. Скрывается после первого `view.update()`.

### 5.3 Error states

| Сценарий | UI |
|---|---|
| Файл не найден | Перед запуском trame: `SystemExit("Не удалось открыть лог: {path}. Проверьте путь к файлу.")` |
| Лог пуст / нет signals.T | `SystemExit("Лог пуст или не содержит сигнала температуры. Проверьте, что сценарий запускался с включённым sensor-каналом T.")` |
| pyvista/trame не установлены | `SystemExit("Для 3D-визуализации требуются pyvista и trame. Установи: pip install -e \".[viz3d]\" из 03_Симулятор/. Detail: {e}")` |

Все ошибки — на stderr перед стартом сервера, без полу-рабочего UI.

## 6. Interactions

### 6.1 Mouse

| Элемент | Действие | Результат |
|---|---|---|
| 3D viewport | left-drag | вращение камеры |
| 3D viewport | right-drag | pan |
| 3D viewport | wheel | zoom |
| 3D viewport | double-click | reset camera |
| Slider track | click | jump to that time, pause |
| Slider thumb | drag | scrub time, pause-on-scrub |
| Playback button | click | соответствующее действие |
| FSM segment | click | jump to start of that state |
| FSM segment | hover | tooltip с диапазоном `t_start — t_end` |
| Injection marker | hover | tooltip с кодом нарушения |
| Drawer toggle | click | open/close drawer |

### 6.2 Keyboard

| Key | Action | Скоп |
|---|---|---|
| `Tab` / `Shift+Tab` | следующий/предыдущий focusable | весь UI |
| `Space` | toggle play/pause | пока focus не на input |
| `←` / `→` | step ±1 frame | при focus на slider или global |
| `Shift+←` / `Shift+→` | step ±10 frames | global |
| `Home` | jump to start | global |
| `End` | jump to end | global |
| `R` | reset camera | global |
| `Escape` | close drawer (если открыт) | global |
| `Enter` / `Space` на кнопке | activate | стандарт |

Hotkeys реализуются через `@keydown` на корневом `v-app` с проверкой `event.target.tagName !== 'INPUT'`.

### 6.3 Touch (для планшетной демонстрации)

| Жест | Результат |
|---|---|
| 1-finger drag в viewport | rotate |
| 2-finger pinch в viewport | zoom |
| 2-finger drag в viewport | pan |
| Tap на playback btn | activate (44×44 hit area) |
| Tap на slider track | jump |
| Drag по slider | scrub, pause-on-scrub |

## 7. Animation / Motion

| Элемент | Trigger | Animation | Duration | Easing |
|---|---|---|---|---|
| Drawer | toggle | slide left/right | 250 ms | `cubic-bezier(0.4, 0, 0.2, 1)` (Material standard) |
| Chip color (FSM) | state change | crossfade background-color | 150 ms | ease-out |
| Cylinder color | T change | none (instant — это физическая величина) | 0 | — |
| Slider thumb | drag end | snap to current frame | 100 ms | ease-out |
| Play/Pause icon | toggle | crossfade | 100 ms | ease-out |
| Playhead на FSM-strip | playing | linear translation 30 fps | непрерывно | linear |

Auto-play: 1 кадр event-log = `dt_log_s` физического времени. По умолчанию ускорение 10× (1 секунда реального времени = 10 секунд эксперимента). Перерасчёт `playback_interval_ms = dt_log_s * 1000 / 10`.

## 8. Responsive behavior

| Breakpoint | Изменения |
|---|---|
| ≥ 1264 px (Vuetify lg+) | full layout как описано |
| 960—1263 px (md) | drawer overlay (не push), уменьшение spacing'ов |
| 600—959 px (sm) | toolbar chip'ы переезжают в drawer; в toolbar остаётся только title и hamburger |
| < 600 px (xs) | playback row → 2 строки (3 кнопки + 2 кнопки); slider полной ширины во второй строке; FSM-полоса прокручивается горизонтально |
| Zoom 200% | flex-wrap включён везде; viewport гарантированно ≥ 320 px высоты |

## 9. Edge cases

| Случай | Поведение |
|---|---|
| Прогон длиной < 5 событий | Slider всё равно показывается, FSM-полоса свёрнута до 5 минимальных сегментов; warning в drawer'е |
| Все события в одном FSM-state | FSM-полоса — один сегмент полной ширины |
| Инъекция произошла в одну и ту же секунду с переходом FSM | Маркер рисуется поверх границы сегмента, тултип содержит оба события |
| Очень длинный прогон (> 1 ч) | Counter выводится в формате `HH:MM:SS`; play по умолчанию ускорение 50× |
| Имя scenario_id длиннее 24 символов | Truncate с ellipsis в title; полное имя в drawer'е |
| Образец вне [20, 250] °C | Цвет clamp'ится; в toolbar chip-T выделяется warning-рамкой `border: 2px solid #C62828` |

## 10. Accessibility checklist

Сводка из accessibility-review:

- [x] Все цветные элементы дублированы текстом или паттерном (1.4.1).
- [x] Контраст текста ≥ 4.5:1, UI-компонентов ≥ 3:1 (1.4.3, 1.4.11).
- [x] Все интерактивные элементы достижимы клавиатурой (2.1.1).
- [x] Нет focus-trap в 3D-viewport — `tabindex="-1"` (2.1.2).
- [x] Visible focus indicator не отключён (2.4.7).
- [x] Touch-targets ≥ 44×44 (2.5.5).
- [x] ARIA: `role`, `aria-label`, `aria-live="polite"` для динамических chip'ов (4.1.2).
- [x] Auto-play выключен по умолчанию + всегда видимая Pause (2.2.2).
- [x] `aria-valuetext` на slider'е с осмысленным текстом (3.3.2).
- [x] Альтернативный текст для 3D-сцены (1.1.1).

Тестовый план перед фиксацией: VoiceOver на macOS (`Cmd+F5`) пройти по tab-цепочке, проверить, что все интерактивы анонсируются. Проверить навигацию только через клавиатуру (отключить мышь). Проверить контраст при включённом «Increase contrast» в System Settings.

## 11. Implementation notes

**Vuetify v2 specifics:**
- Сервер инициализируется как `get_server(client_type="vue2")` — иначе `TypeError: Server using client_type='vue3' while we expect 'vue2'`.
- `v-chip color="#E65100" dark` — `dark` атрибут включает белый текст; для кастомных hex-цветов это обязательно.
- `v-btn icon size="large"` даёт 48×48 (≥ 44×44 как требуется WCAG).
- `v-slider :aria-valuetext="..."` поддерживается с Vuetify 2.5+.

**PyVista trame:**
- `pv.Plotter(notebook=False)` — обязательно. `off_screen=True` ломает рендер.
- `plotter_ui(plotter, mode="trame")` — современный helper, сам монтирует VtkLocalView.
- Для colorbar: добавить scalar field `sample.point_data["T"] = np.full(sample.n_points, T_C)` и пересчитывать в update_frame.
- Для legend: `plotter.add_legend([("Термокамера 1×1×1 м", "lightgray"), ("Образец Ø100×200 мм", "red")], bcolor="white", border=True)`.

**State binding:**
- Все числа в trame state должны быть JSON-serializable (`float`, не `numpy.float64`). При записи в state — `float(value)`.
- `state.change` callback'и идут в порядке регистрации; для `frame` сначала обновляем values, потом — view.update.
- `aria-live` атрибут лучше ставить на родительский контейнер chip'ов, а не на каждый отдельно — иначе SR зачитает 3 раза при каждом обновлении.

**FSM-полоса (HTML):**
Реализуется через `vuetify.html(content="...")` с шаблоном на Vue:
```html
<div class="fsm-strip" role="img" :aria-label="strip_aria">
  <div v-for="seg in fsm_segments" :key="seg.t_start"
       class="fsm-seg" :style="{ flex: seg.flex, background: seg.color }">
    <span>{{ seg.label }}</span>
  </div>
  <div class="fsm-playhead" :style="{ left: playhead_pct + '%' }"></div>
  <div v-if="injection" class="fsm-injection" :style="{ left: injection.pct + '%' }"
       :title="'Инъекция: ' + injection.code">
    <span class="mdi mdi-alert"></span>
  </div>
</div>
```

`fsm_segments` собирается на старте из event-log: для каждой пары соседних `STATE_ENTER` событий — сегмент с `t_start`, `t_end`, `flex = (t_end - t_start) / total`, `color = fsmColor[state]`, `label = fsmHuman[state]`.

## 12. Out of scope (сознательно отложено)

- Сравнение двух прогонов side-by-side — для Phase 5, отдельный экран.
- Live-streaming во время симуляции — текущая архитектура event-log read-only.
- Экспорт скриншота сцены в PNG — добавим в Phase 7 для слайдов защиты.
- Темная тема — всё проектирование под light, тёмная не нужна на проекторе.
- Локализация — только ru, en — отложено.

## 13. Локализация

Все строки UI хранятся в одной dict-структуре `TRANSLATIONS[lang][key]`. По умолчанию `lang = "ru"`. Переключатель в toolbar меняет `state.lang` → реактивное обновление всех computed-properties.

### 13.1 Полная таблица переводов

| Ключ | RU | EN |
|---|---|---|
| `app_title` | Симулятор FLV | FLV Simulator |
| `lang_toggle` | Язык интерфейса | Interface language |
| `drawer_open` | Параметры прогона | Run parameters |
| `drawer_title` | Параметры прогона | Run parameters |
| `drawer_scenario` | Сценарий | Scenario |
| `drawer_type` | Тип | Type |
| `drawer_type_correct` | Корректный прогон | Valid run |
| `drawer_type_injection` | Инъекция: {code} | Injection: {code} |
| `drawer_stand` | Стенд | Stand |
| `drawer_seed` | Seed | Seed |
| `drawer_duration` | Длительность | Duration |
| `drawer_events` | Событий | Events |
| `drawer_file` | Файл | File |
| `drawer_sim_version` | Версия sim | Simulator version |
| `label_time` | t | t |
| `label_temp` | T | T |
| `unit_s` | c | s |
| `unit_temp` | °C | °C |
| `aria_chip_time` | Время эксперимента: {value} секунд | Experiment time: {value} seconds |
| `aria_chip_temp` | Температура: {value} градусов Цельсия | Temperature: {value} degrees Celsius |
| `aria_chip_fsm` | Состояние: {value} | State: {value} |
| `slider_label` | Время эксперимента | Experiment time |
| `slider_aria_valuetext` | {value} секунд из {max} | {value} of {max} seconds |
| `btn_skip_back` | К началу прогона | To run start |
| `btn_step_back` | Назад на 10 событий | Back 10 events |
| `btn_play` | Воспроизвести | Play |
| `btn_pause` | Пауза | Pause |
| `btn_step_fwd` | Вперёд на 10 событий | Forward 10 events |
| `btn_skip_fwd` | К концу прогона | To run end |
| `aria_play_toggle` | Воспроизведение прогона | Run playback |
| `legend_chamber` | Термокамера 1×1×1 м | Chamber 1×1×1 m |
| `legend_sample` | Образец Ø100×200 мм | Sample Ø100×200 mm |
| `colorbar_title` | Температура образца, °C | Sample temperature, °C |
| `viewport_aria` | 3D-визуализация термокамеры с образцом | 3D visualization of chamber with sample |
| `strip_aria` | Фазы прогона: {labels} | Run phases: {labels} |
| `injection_tooltip` | Инъекция: {code} | Injection: {code} |
| `loading` | Загрузка прогона… | Loading run… |
| `err_file_not_found` | Не удалось открыть лог: {path}. Проверьте путь к файлу. | Could not open log: {path}. Check the file path. |
| `err_no_temp` | Лог пуст или не содержит сигнала температуры. Проверьте, что сценарий запускался с включённым sensor-каналом T. | Log is empty or contains no temperature signal. Verify the scenario was run with the T sensor channel enabled. |
| `err_no_deps` | Для 3D-визуализации требуются pyvista и trame. Установи: pip install -e ".[viz3d]" из 03_Симулятор/. Detail: {e} | 3D visualization requires pyvista and trame. Install: pip install -e ".[viz3d]" from 03_Симулятор/. Detail: {e} |

### 13.2 Перевод FSM-состояний

Используется в chip'ах в toolbar и в подписях сегментов FSM-полосы.

| State id | RU | EN |
|---|---|---|
| `INIT` | Подготовка | Setup |
| `HEAT` | Нагрев | Heating |
| `HOLD` | Стабилизация | Stabilization |
| `MEASURE` | Измерение | Measurement |
| `POST` | Завершение | Wrap-up |
| `INJECTION` | Инъекция | Injection |

### 13.3 Реализация в trame

```python
TRANSLATIONS = {
    "ru": { "app_title": "Симулятор FLV", ... },
    "en": { "app_title": "FLV Simulator", ... },
}

state.lang = "ru"  # default

# В Vue-шаблоне через computed:
# t = computed(() => TRANSLATIONS[state.lang])
# {{ t.app_title }}
# Для строк с подстановкой: t.drawer_type_injection.replace('{code}', code)
```

В trame computed-properties доступны через `state.change` callback, который собирает локализованные строки в одну реактивную карту:

```python
@state.change("lang")
def _on_lang(lang: str, **_kwargs: Any) -> None:
    state.t = TRANSLATIONS[lang]
    state.fsm_humans = {k: TRANSLATIONS[lang]["fsm_" + k.lower()] for k in FSM_STATES}
```

Затем в шаблоне — `{{ t.app_title }}`, `{{ fsm_humans[fsm_state] }}` и т.п.

### 13.4 Правила перевода

- Технические термины (FLV, FSM, JSONL, seed, RUN_START) — без перевода в обоих языках.
- Числовые форматы: `0.0` (точка) одинаково в ru и en (научный стандарт). Разделитель тысяч — пробел, не запятая.
- Единицы — без перевода (`°C`, `Hz`, `Pa`); только секунды: `c` (ru) / `s` (en).
- Knopok labels — повелительное наклонение в обоих языках («Воспроизвести», «Play», не «Воспроизводится» или «Playing»).
- Drawer values — заголовочный регистр для имён собственных, обычный для нарицательных.

### 13.5 QA-чеклист после переключения языка

При переключении `RU → EN` и обратно проверить:

- Все toolbar chip'ы перерендерились.
- FSM-сегменты на полосе перерендерились (включая узкие, где label обрезан).
- Tooltip'ы кнопок обновились.
- Drawer перерендерился.
- Colorbar title обновился (требует перерисовки plotter scene — `plotter.update()`).
- Aria-label'ы обновились (зачитываются screen-reader при следующем фокусе).
- localStorage сохранил выбор.

## 14. References

- WCAG 2.1 AA — https://www.w3.org/WAI/WCAG21/quickref/
- Material Design Guidelines (Vuetify v2 base) — https://m2.material.io/design
- ColorBrewer / matplotlib colormaps — https://matplotlib.org/stable/users/explain/colors/colormaps.html
- Vuetify v2 component docs — https://v2.vuetifyjs.com/en/components
- PyVista Trame integration — https://docs.pyvista.org/api/plotting/trame.html
- ГОСТ 8.417-2002 — единицы величин (правила записи)
- Apple HIG (touch targets) — https://developer.apple.com/design/human-interface-guidelines/buttons

## 15. Журнал

| Дата | Изменение | Автор |
|---|---|---|
| 2026-05-05 | v1.0 — начальная спецификация после design-critique + a11y + ux-copy | Катальшов Д.А. |
| 2026-05-05 | v1.1 — добавлен раздел «Локализация», переключатель RU/EN, таблица переводов всех лейблов | Катальшов Д.А. |
