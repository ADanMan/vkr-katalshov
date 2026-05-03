# skills/

Кастомные Claude Code-скиллы для проекта.

## vkr-bauman-flv

Полный workflow-скилл для работы над этой ВКР. Покрывает:

- Оформление по ГОСТ 7.32-2017 + ГОСТ 7.0.5-2008.
- Шаблон К4 МФ МГТУ им. Н.Э. Баумана + Положение о ВКРБ.
- Поиск и BibTeX-оформление источников (CrossRef, Semantic Scholar).
- Написание глав в стиле IMRAD под технический отчёт.
- Mermaid-диаграммы для FSM, архитектуры, sequence.
- schemdraw — Python-схемы для электрической части.
- Симулятор стенда (физика теплопередачи, PT100, АЦП, шумы).
- Статистическую обработку (TPR/FPR, McNemar, Wilcoxon, Cohen's d, bootstrap CI).

## Установка скилла в Claude Code / Cowork

### Вариант 1 — Claude Code (CLI)

Скопируй в локальную директорию скиллов Claude Code:

```bash
cp -r vkr-bauman-flv ~/.claude/skills/
# или для конкретного проекта:
cp -r vkr-bauman-flv .claude/skills/
```

### Вариант 2 — собрать .skill-плагин

```bash
python -m skill_creator.scripts.package_skill skills/vkr-bauman-flv
# результат: vkr-bauman-flv.skill в текущей директории
```

Затем в Cowork: «Установить скилл» → выбрать `.skill`-файл.

## Основано на (атрибуция)

- `K-Dense-AI/scientific-agent-skills` (MIT) — паттерны citation-management, scientific-writing, literature-review, statistical-analysis.
- `bahayonghang/academic-writing-skills` (Academic-only) — bib-search-citation, paper-audit.
- `awesome-skills/mermaid-syntax-skill` (MIT) — Mermaid v11 best practices.
- `ifsmirnov/bachelor-diploma` (CC BY 4.0, Юлия Мартынова + AndreyAkinshin) — структура LaTeX-шаблона бакалаврского диплома.
- `cdelker/schemdraw` (MIT) — Python-генерация электрических схем.
- Шаблоны и Положения МФ МГТУ им. Н.Э. Баумана — открытые методические материалы кафедры К4.

При использовании сохраняйте references на оригинальные источники.
