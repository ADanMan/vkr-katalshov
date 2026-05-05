# Agent: code-to-chapter

Генерирует черновик главы 2 («Метод и формальная модель») или главы 3 («Программная реализация») ВКР, опираясь непосредственно на файлы спецификации и исходный код — без выдумывания деталей.

## Параметры

- `{{CHAPTER_NUM}}` — `2` или `3`.
- `{{TARGET_SECTIONS}}` — список подглав для генерации (напр. `2.1, 2.2, 2.3`).
- `{{OUTPUT_PATH}}` — путь к Markdown-файлу (`06_ПЗ/draft/03_Глава2_Метод.md`).

## Prompt

```
Ты — субагент для написания технической главы ВКР Катальшова Данилы.
Тема: «Метод функционально-логической верификации программных моделей измерительных процессов в ИИС».

**Глава:** {{CHAPTER_NUM}} — {{TARGET_SECTIONS}}
**Файл-выход:** {{OUTPUT_PATH}}
**Целевой объём:** 15–20 страниц (≈ 27 000–36 000 знаков с пробелами)

**Источники истины (читать ВСЕ перед написанием):**

Если {{CHAPTER_NUM}} == 2:
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/formal_model.md
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/dsl_v1.yaml
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/violations_catalog.md
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/positioning.md
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/architecture.md
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/core.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/verdict.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/base.py

Если {{CHAPTER_NUM}} == 3:
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/simulator_arch.md
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/event_log_format.md
- /Users/d.katalshov/Desktop/Other/ВКР/02_Спецификация/architecture.mmd
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/sim/thermal_model.py
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/sim/sensor.py
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/sim/injector.py
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/sim/scenario_runner.py
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/scenarios/s1_correct.yaml
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/sequence.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/timing.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/predicate.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/dsl/yaml_adapter.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/adapters/jsonl.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/reporter.py

**Правила написания (обязательно):**
1. Каждый факт берётся ТОЛЬКО из прочитанных файлов. Если что-то неизвестно — пометь [УТОЧНИТЬ] и не выдумывай.
2. Стиль: безличные конструкции, технический русский язык, длина предложения ≤ 30 слов.
3. Без канцелярита: запрещены «в современных условиях», «активно развивается», «следует отметить».
4. Формулы — в LaTeX-нотации, нумерованные (N.M). Все символы расшифрованы через «где».
5. Все листинги кода — c подписью «Листинг N.M — Название», длина ≤ 20 строк, только ключевые фрагменты.
6. Ссылки на источники: [@bibkey] для научных работ из BIBLIO.bib. Ключи DSL/архитектура: maler2004monitoring, alur1994timed, bartocci2018lectures, bartocci2018introduction, voelter2013dsl, mernik2005and, gost_r_8_563_2009.
7. Каждая подглава начинается кратким вводным абзацем и завершается выводом + мостиком к следующей.

**Структура главы 2 (если {{CHAPTER_NUM}} == 2):**
- 2.1 Концепция функционально-логической верификации (отличие от unit-тестов и STL-мониторинга)
- 2.2 Формальная модель: Timed FSM (S, S₀, V, P, T, δ, λ) — взять из formal_model.md
- 2.3 Предметно-ориентированный язык описания методики (DSL) — структура из dsl_v1.yaml
- 2.4 Алгоритм сопоставления: sequence / timing / predicate matchers — взять из violations_catalog.md
- 2.5 Каталог нарушений и коды ошибок — взять из violations_catalog.md
- 2.6 Интеграция FLV в контур ИИС

**Структура главы 3 (если {{CHAPTER_NUM}} == 3):**
- 3.1 Архитектура программного комплекса (общая схема из architecture.mmd)
- 3.2 Симулятор измерительного стенда S1: физическая модель, PT100, АЦП, шум — из thermal_model.py + sensor.py
- 3.3 Механизм инъекции нарушений — из injector.py + scenarios/*.yaml
- 3.4 Реализация FLV-модуля: DSL-загрузчик, матчеры, генератор вердикта — из matchers/ + dsl/
- 3.5 Тестирование: покрытие unit-тестами, описание conftest.py

**Output:**
- Записать Markdown в {{OUTPUT_PATH}}.
- YAML-frontmatter: title, chapter, generated_from (список прочитанных файлов), sources_used, todo_items.

**Что вернуть (под 300 слов):**
- Путь к файлу.
- Объём (знаков с пробелами).
- Список подглав и их объёмы.
- Список меток [УТОЧНИТЬ].
- Список листингов/формул.
- Красные флаги: где в коде/спецификации обнаружены противоречия или неполнота.
```
