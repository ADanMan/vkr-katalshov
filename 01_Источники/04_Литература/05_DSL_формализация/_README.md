# 04_Литература / 05_DSL_формализация

Литература по DSL (предметно-ориентированным языкам) и формализации спецификаций — для главы 2 «Метод» (обоснование выбора DSL для нормативной модели измерительного процесса) и главы 3 «Реализация» (раздел про парсер DSL).

## Таблица источников (Phase 1, вторая партия)

| # | Author | Year | Title | Status | BibKey | Зачем нужна / Раздел |
|---|---|---|---|---|---|---|
| 1 | Fowler M. | 2010 | Domain-Specific Languages. Addison-Wesley Professional | CLOSED (книга) | `fowler2010dsl` | Каноническая работа Фаулера по DSL: external vs internal, semantic model. Раздел 2.4 «DSL как нотация эталона». |
| 2 | Voelter M. | 2013 | DSL Engineering: Designing, Implementing and Using Domain-Specific Languages | OPEN (PDF, voelter.de) | `voelter2013dsl` | 558 стр. учебник по проектированию DSL: грамматика, валидация, IDE-интеграция. Раздел 2.4, 3.2. |
| 3 | Mernik M., Heering J., Sloane A.M. | 2005 | When and How to Develop Domain-Specific Languages. ACM CSUR 37(4):316–344 | OPEN (PDF, inkytonik.github.io / DOI 10.1145/1118890.1118892) | `mernik2005when` | Систематический обзор паттернов «когда нужен DSL и как его создавать». Раздел 2.4. |
| 4 | OMG | 2019 | OMG Systems Modeling Language (SysML) Specification, Version 1.6 | CLOSED-WEB (omg.org) | `omg2019sysml` | Стандарт SysML — для контекста про существующие языки моделирования технических систем. Раздел 1.4. |
| 5 | Ботов Д.С. | 2013 | Обзор современных средств создания и поддержки предметно-ориентированных языков программирования. Вестник ЮУрГУ 13(1): 10–15 | OPEN (CC BY, CyberLeninka) | `botov2013dsl` | Российский обзор средств DSL (Xtext, MPS, Spoofax). Раздел 2.4. |
| 6 | Степулёнок Д.О. | 2010 | Модель и методы реализации предметно-ориентированных языков. Компьютерные инструменты в образовании, 4: 21–29 | OPEN (CC BY, CyberLeninka) | `stepulenok2010dsl` | Семантические модели DSL и их реализация. Раздел 2.4 «Архитектура парсера». |
| 7 | Воробьёв А.Ю. | 2014 | Предметно-ориентированный язык программирования для разработки программного обеспечения для тестирования электронных устройств. Математические структуры и моделирование, 4 (32): 147–161 | OPEN (CC BY, CyberLeninka) | `vorobyev2014dsl` | DSL для автоматизированного тестирования электроники — прямой методологический аналог DSL ВКР. Раздел 1.4, 2.4. |

**Итого:** 7 работ. PDF в папке: **5** (Voelter, Mernik, Botov, Stepulenok, Vorobyev). Закрытые: 2 (Fowler 2010 — книга; OMG SysML 1.6 — спецификация в виде PDF на omg.org).

## Закрытые работы — где скачать

| Работа | Метод доступа |
|---|---|
| Fowler «Domain-Specific Languages» (2010) | ISBN 978-0321712943. Addison-Wesley. ЭБС МГТУ; pearson.com. Часть глав в открытом виде на martinfowler.com/books/dsl.html. |
| OMG SysML 1.6 | URL: omg.org/spec/SysML/1.6/PDF — спецификация в открытом доступе как PDF, но требует регистрации. Альтернативно SysML 1.7 (2024) — последняя версия. |

## Что покрыто этой партией для главы 1-3 ВКР

- §1.4 «Существующие языки моделирования технических систем» — `omg2019sysml`, `vorobyev2014dsl`.
- §2.4 «Выбор и обоснование DSL для нормативной модели» — `fowler2010dsl`, `voelter2013dsl`, `mernik2005when`, `botov2013dsl`, `stepulenok2010dsl`.
- §3.2 «Парсер DSL и semantic model» — `voelter2013dsl`, `stepulenok2010dsl`.

## Compliance

- Voelter 2013 — автор официально выложил книгу в свободный доступ на voelter.de с пометкой «Free for personal use».
- Mernik 2005 — авторская копия (Sloane, Macquarie) выложена с разрешения ACM.
- OMG SysML 1.6 — открытая спецификация под собственной OMG-лицензией (свободное некоммерческое использование при сохранении авторства).
- Российские статьи (CyberLeninka) — лицензия CC BY.
- Fowler 2010 — закрытая книга, цитирование по правилу ≤ 15 слов.

## Источники метаданных

- DOI/Crossref для `mernik2005when` (10.1145/1118890.1118892).
- ISBN для `fowler2010dsl` (978-0321712943) и `voelter2013dsl` (978-1481218580 — print; PDF 1.0).
- OMG SysML 1.6 — официальный URL: https://www.omg.org/spec/SysML/1.6/.
- Российские статьи — citation_* meta-теги CyberLeninka (полный список полей в рабочем дампе).
