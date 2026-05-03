# 02_Спецификация

Формальная модель и архитектура FLV (выходы Phase 2).

## Артефакты

- `dsl_v1.yaml` — пример полной DSL-спецификации для S1 (термокамера).
- `flv_dsl.schema.json` — JSON Schema для валидации DSL.
- `event_log_format.md` + `event_log.schema.json` — формат логов исполнения.
- `formal_model.md` — Timed FSM с математической нотацией и примером.
- `architecture.mmd` + `architecture.md` — архитектура модуля FLV (Mermaid + пояснения).
- `simulator_arch.md` — архитектура симулятора (вход для Phase 3).
- `violations_catalog.md` — каталог 7 кодов нарушений.
- `validate.py` — скрипт-валидатор DSL по JSON Schema.

## Принципы

- DSL — YAML, минимальный «грамматический» набор: `meta`, `process`, `states`, `parameters`, `transitions`, `checks`, `violations_catalog`.
- Mermaid-диаграммы держим как `*.mmd` исходник + `*.png` рендер 300 DPI (для вставки в ПЗ и презентацию).
- Любое изменение DSL ведёт к обновлению Schema и теста `validate.py`.
