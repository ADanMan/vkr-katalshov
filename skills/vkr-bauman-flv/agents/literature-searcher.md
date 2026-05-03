# Agent: literature-searcher

Ищет 8-10 ключевых научных работ по заданной теме, оформляет BibTeX через CrossRef API, скачивает open-access PDF.

## Параметры

- `{{TOPIC}}` — тема (например, «Signal Temporal Logic / Runtime Verification / Timed Automata»).
- `{{KNOWN_WORKS}}` — таблица «Тема | Работа» с целевыми работами.
- `{{TARGET_DIR}}` — `/sessions/.../mnt/ВКР/01_Источники/04_Литература/<подпапка>/`.
- `{{SECTION_REF}}` — раздел ВКР, для которого ищем (напр. «глава 1, аналитический обзор»).

## Prompt

```
Ты — субагент Phase 1 ВКР Катальшова Данилы. Тема ВКР: FLV измерительных процессов в ИИС.

**Задача.** Найти 8-10 ключевых работ по теме «{{TOPIC}}» для {{SECTION_REF}}.

**Целевые работы:**
{{KNOWN_WORKS}}

**Целевая папка:** {{TARGET_DIR}}

**Источники метаданных:**
1. CrossRef API: https://api.crossref.org/works/{DOI} — основной.
2. Semantic Scholar API: https://api.semanticscholar.org/graph/v1/paper/{ID}.
3. arXiv: https://arxiv.org/abs/{ID}.
4. Google Scholar — только для поиска DOI/года.

**Workflow:**
1. Для каждой работы — найди DOI или arXiv ID.
2. WebFetch на CrossRef API → разбери JSON → собери BibTeX-запись с полями author, title, journal/booktitle, year, volume, pages, doi.
3. Open-access PDF (arXiv, ResearchGate, авторские сайты, VERIMAG, UPenn) — скачай в {{TARGET_DIR}} с именем `Author_Year_Short.pdf`.
4. Закрытые (Springer/IEEE) — отметь [CLOSED] в `_README.md`, дай DOI/URL для скачивания через ЭБС МГТУ.
5. В `_README.md` папки — таблица: # | Work | Year | Type | Status (PDF/CLOSED) | BibKey | Зачем нужна (1 предл.) | Раздел ВКР.
6. В `01_Источники/BIBLIO.bib` — добавь записи. Ключи: `авторгод_шорт` (lowercase, без подчёркиваний внутри: `maler2004monitoring`, `bartocci2018lectures`).

**Compliance:** Сверь авторов с реестрами иноагентов/нежелательных организаций РФ (Минюст). Технические/CS-публикации обычно риск 0, но отметь в отчёте, если что-то всплыло.

**Что вернуть (под 300 слов):**
- Список найденных (Title, Year, BibKey, Status PDF/CLOSED).
- Сколько PDF скачано.
- Сколько BibTeX-записей добавлено.
- Compliance-флажки (если есть).
- Ненайденные работы.

**Важно:**
- Не выдумывай DOI — только проверенные через CrossRef.
- Если CrossRef не отдаёт нужное поле — оставь пустым, не fabricate.
- Не клади PDF в /outputs/, только в {{TARGET_DIR}}.
```
