# 04_Литература / 03_LabVIEW_TestStand

Материалы по экосистеме National Instruments (LabVIEW, TestStand, VI Analyzer) — для главы 1 «Аналитический обзор» (раздел про текущие промышленные подходы к V&V измерительных процессов) и главы 4 «Сравнение с аналогами» ВКР.

## Таблица источников (Phase 1, вторая партия)

| # | Author | Year | Title | Status | BibKey | Зачем нужна / Раздел |
|---|---|---|---|---|---|---|
| 1 | National Instruments | 2020 | LabVIEW VI Analyzer Toolkit User Guide (NI Manual 373631D) | OPEN (PDF) | `ni2020vianalyzer` | Описание инструментария статического анализа VI — прямой аналог нашего sequence-matcher для LabVIEW кода. Раздел 1.4 «Аналоги», 4.2 «Сравнение». |
| 2 | National Instruments | 2024 | NI TestStand Sequence Analyzer (online docs) | CLOSED-WEB | `ni2024teststandsa` | Архивная wiki/онлайн-документация по правилам Sequence Analyzer (категории нарушений и тесты). Подтверждает существование промышленного аналога с близким набором проверок. Раздел 1.4. |
| 3 | Travis J., Kring J. | 2006 | LabVIEW for Everyone: Graphical Programming Made Easy and Fun (3rd ed.) | CLOSED (книга) | `travis2006labview` | Базовый учебник по LabVIEW, цитируется во введении к главе 1. |
| 4 | Bitter R., Mohiuddin T., Nawrocki M. | 2007 | LabVIEW: Advanced Programming Techniques (2nd ed.), CRC Press | CLOSED (книга) | `bitter2007labview` | Архитектурные паттерны LabVIEW (state machine, queued-message handler) — обоснование выбора FSM как формализма для DSL. Раздел 2.1. |
| 5 | Симонов П.И., Кубанков Ю.А., Игнатова В.Н. | 2019 | Automation of measurements of signals of aircraft transponders in information measuring stands on the basis of standard VPP and SDR technologies. T-Comm 13(2): 70–75 | OPEN (CC BY) | `simonov2019labview` | Российский пример применения LabVIEW в ИИС с использованием SDR — показывает, что в РФ-практике LabVIEW остаётся доминирующей средой ИИС. Раздел 1.1. |
| 6 | Манонина И.В. | 2012 | Применение программы LabVIEW для изучения вопросов поверки измерительных приборов. T-Comm 8 | OPEN (CC BY) | `manonina2012labview` | Применение LabVIEW для автоматизации поверки СИ — связь с темой ВКР по верификации методики. Раздел 1.2. |
| 7 | Popoola S., Zhao X., Gray J. | 2021 | Evolution of Bad Smells in LabVIEW Graphical Models. JOT 20(1):1, DOI 10.5381/jot.2021.20.1.a1 | OPEN (PDF, jot.fm) | `popoola2021badsmells` | Полуавтоматический анализ 81 LabVIEW-модели из 10 GitHub-репо: 7 типов «bad smells», которые компилятор LabVIEW не отлавливает (Wire Tunnel Crossing, Long Wire, Cluttered Block Diagram и др.). Прямой эмпирический пример семантического разрыва в LabVIEW. PDF: `Popoola_2021_Bad_Smells_LabVIEW.pdf`. Раздел 1.4 / §1.5. |
| 8 | Zhao X., Rai G., Popoola S., Gray J. | 2024 | Ask or tell: An empirical study on modeling challenges from LabVIEW community. J. Comput. Languages 80:101284, DOI 10.1016/j.cola.2024.101284 | CLOSED (Elsevier) | `zhao2024labview` | ML-анализ 162 000+ постов на forums.ni.com + опрос 60+ инженеров. Главный класс трудностей в LabVIEW — coding practice. Свидетельство массовости семантических ошибок. Раздел §1.5. |

**Итого:** 8 работ. PDF в папке: **6** (NI VI Analyzer User Guide, Симонов 2019, Манонина 2012, Popoola 2021 — добавлено в этой партии, плюс закрытые две книги Travis/Kring и Bitter et al. — по ISBN через ЭБС МГТУ; Zhao 2024 — через Elsevier ЭБС МГТУ).

## Закрытые работы — где скачать

| Работа | Метод доступа |
|---|---|
| Travis & Kring «LabVIEW for Everyone» 3-е изд. (2006) | ISBN 978-0131856721. Prentice Hall. ЭБС МГТУ — поиск по ISBN. |
| Bitter, Mohiuddin, Nawrocki «LabVIEW: Advanced Programming Techniques» 2-е изд. (2007) | ISBN 978-0849333255. CRC Press. ЭБС МГТУ; Internet Archive (archive.org/details/labview-advanced-programming-techniques-second-edition-resource-cd) — для контрольной сверки страниц. |
| NI «What Is NI TestStand?», «TestStand Sequence Analyzer» (онлайн) | ni.com/white-paper/4808/en, ni.com/docs/en-US/bundle/teststand/page/teststand-sequence-analyzer.html. На дату обращения 2026-05-05 страницы доступны без логина. Архивные снимки делать через web.archive.org перед сдачей ПЗ. |

## Что покрыто этой партией для главы 1 ВКР

- §1.1 «Промышленная практика V&V измерительного ПО в РФ» — `simonov2019labview`, `manonina2012labview`, `korgin2013primenenie` (из 02_Метрология).
- §1.4 «Аналоги: NI экосистема» — `ni2020vianalyzer`, `ni2024teststandsa`, `popoola2021labview`.
- §2.1 «Выбор формализма (FSM, queued-message handler)» — `bitter2007labview`.
- Введение и §1.0 — `travis2006labview` как базовый источник определений.

## Compliance

- NI white papers и manuals — публикуются NI в свободном доступе, копии для научного цитирования допустимы.
- Книги CRC Press, Prentice Hall — закрытый доступ; используем только цитаты ≤ 15 слов (по правилу copyright protection ВКР).
- Российские статьи (CyberLeninka) — лицензия CC BY (открытый доступ).

## Источники метаданных

- DOI/Crossref для `mernik2005`, `behrmann2004`: `https://api.crossref.org/works/<DOI>` (см. рабочие заметки).
- ISBN для книг — sверены по `worldcat.org` и официальным карточкам издательств.
- Российские статьи — citation_* meta-теги CyberLeninka.
