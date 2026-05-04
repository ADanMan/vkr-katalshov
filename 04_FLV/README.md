# 04_FLV — модуль функционально-логической верификации

Часть ВКР Катальшова Д.А., К2-81Б. Архитектура — `02_Спецификация/architecture.md`.

## Установка

```bash
cd 04_FLV
python -m venv .venv && source .venv/bin/activate
pip install -e ".[llm,dev]"
```

`.[llm]` — добавляет OpenAI SDK для работы с OpenRouter (роли 1 и 3).
`.[dev]` — pytest, ruff, mypy.

## Использование

```bash
# Извлечь DSL из текста методики (LLM роль 1)
flv extract --text methodology.txt --out spec.yaml --model gpt-5.4

# Валидация DSL (без runtime)
flv validate --spec spec.yaml

# Главное: проверить event-log на соответствие DSL
flv check --spec spec.yaml --log run.jsonl --report verdict.md --json verdict.json

# С LLM-объяснением (роль 3)
flv check --spec spec.yaml --log run.jsonl --report verdict.md --explain --model claude-sonnet-4.6
```

## Поддерживаемые модели через OpenRouter

* `google/gemini-flash-3` — быстрая, дешёвая (Роль 1: extract)
* `openai/gpt-5.4` — баланс цена/качество (Роль 1, 3)
* `anthropic/claude-sonnet-4.6` — точная, для критичных фрагментов
* `deepseek/deepseek-v4-flash` — open-weight альтернатива
* `qwen/qwen3.6-flash` — open-weight, китайская научная база

## Структура

```
flv/
├── __init__.py
├── __main__.py            CLI entry-point
├── spec_loader.py         DSL (YAML) → внутренняя FSM-модель
├── log_parser.py          JSONL event-log → нормализованные события
├── verdict.py             dataclass-структуры Violation/Verdict
├── reporter.py            Markdown + JSON отчёты
├── llm_extractor.py       Роль 1: текст → DSL через OpenRouter
├── llm_explainer.py       Роль 3: verdict → объяснение
├── anti_hallucination.py  Анти-галл фильтр для LLM-вывода
└── matchers/
    ├── __init__.py
    ├── base.py            Абстрактный BaseMatcher
    ├── sequence.py        SEQ_MISS, SEQ_ORDER
    ├── timing.py          TIME_UNDER, TIME_OVER
    └── predicate.py       PRED_FAIL, RANGE_MISM, N_TOO_LOW
```

## Тесты

```bash
pytest                              # все тесты + coverage
pytest -m unit                      # только юниты
pytest -m integration               # интеграционные (на реальных трассах из 03_Симулятор)
```

Цель coverage: ≥ 80 % по модулю `flv`.
