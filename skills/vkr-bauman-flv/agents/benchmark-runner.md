# Agent: benchmark-runner

Создаёт и запускает бенчмарки FLV-модуля: замеряет overhead (время верификации на событие), масштабируемость (размер event-log), потребление памяти. Кладёт результаты в `04_FLV/benchmarks/` и формирует таблицу для главы 3 ПЗ.

## Параметры

- `{{BENCHMARK_DIR}}` — `04_FLV/benchmarks/` (выход).
- `{{LOG_SIZES}}` — список размеров event-log для замера, через запятую (напр. `100,500,1000,5000,10000`).

## Prompt

```
Ты — субагент-бенчмаркер FLV-модуля ВКР Катальшова. Твоя задача: измерить производительность FLV и задокументировать её для главы 3 ПЗ.

**Целевой каталог:** {{BENCHMARK_DIR}}
**Размеры event-log:** {{LOG_SIZES}} событий на прогон.

**Шаг 0 — ознакомление с кодом:**
Прочитай:
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/core.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/sequence.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/timing.py
- /Users/d.katalshov/Desktop/Other/ВКР/04_FLV/flv/matchers/predicate.py
- /Users/d.katalshov/Desktop/Other/ВКР/03_Симулятор/scenarios/s1_correct.yaml

Это нужно, чтобы понять реальный API FLV и структуру event-log перед написанием бенчмарков.

**Шаг 1 — создай benchmark_overhead.py:**
Файл: {{BENCHMARK_DIR}}/benchmark_overhead.py

Скрипт должен:
1. Генерировать синтетический event-log нужного размера (N событий в формате, совместимом с jsonl.py adapter).
2. Для каждого N из {{LOG_SIZES}} запускать FLVPipeline на этом логе (через реальный API из core.py).
3. Замерять время: `time.perf_counter()` или `timeit`, 10 повторений, брать median.
4. Замерять память: `tracemalloc`.
5. Считать overhead_per_event_us = total_time_us / N.
6. Сохранять в DataFrame и в {{BENCHMARK_DIR}}/results_overhead.csv.

**Шаг 2 — запусти benchmark_overhead.py:**
```bash
cd /Users/d.katalshov/Desktop/Other/ВКР
pip install -e 04_FLV --break-system-packages -q
python {{BENCHMARK_DIR}}/benchmark_overhead.py
```

**Шаг 3 — создай таблицу для ПЗ:**
Из results_overhead.csv сформируй Markdown-таблицу:
| N событий | Median время, мс | Overhead/событие, мкс | Память, МБ |

Сохрани в {{BENCHMARK_DIR}}/benchmark_table.md.

**Шаг 4 — создай график:**
```python
import matplotlib
matplotlib.use('Agg')
# Линейный график overhead_per_event_us vs N
# Сохранить в {{BENCHMARK_DIR}}/fig_overhead.png (300 DPI)
```

**Целевые показатели (для сравнения):**
- overhead_per_event_us < 500 мкс при N = 1000 → «приемлемо для онлайн-режима»
- overhead_per_event_us < 100 мкс при N = 1000 → «пригодно для RT-режима»

**Что вернуть (под 250 слов):**
- Статус (OK / FAIL).
- Таблица результатов (Markdown, все N).
- Вывод: попадает ли FLV в целевые показатели.
- Список созданных файлов.
- Готовый абзац (~150 слов) для раздела 3.5 ПЗ с цифрами.
```
