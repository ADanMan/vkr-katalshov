# 04_Литература / 01_FLV_RV

Литература по Runtime Verification (RV), Signal/Metric Temporal Logic (STL/MTL) и Timed Automata. Эти работы — теоретическая база главы 1 «Аналитический обзор» и главы 2 «Метод» ВКР.

## Таблица источников (Phase 1, первая партия)

| # | Работа | Год | Тип | DOI | Статус PDF | Файл | BibTeX-ключ | Зачем нужна (1 предложение) | Раздел ВКР |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Alur R., Dill D.L. «A Theory of Timed Automata» | 1994 | journal-article (TCS, 4690 цитирований) | 10.1016/0304-3975(94)90010-8 | PDF (UPenn author page) | `Alur_1994_Timed_Automata.pdf` (53 pp) | `alur1994theory` | Каноническая модель Timed Automata — формальная база для DSL Timed FSM в Phase 2. | 1.2 «Формальные модели измерительных процессов»; 2.1 «Timed FSM как эталон» |
| 2 | Maler O., Nickovic D. «Monitoring Temporal Properties of Continuous Signals» | 2004 | book-chapter (FORMATS/FTRTFT 2004, LNCS 3253, 848 цитирований) | 10.1007/978-3-540-30206-3_12 | PDF (VERIMAG author page) | `Maler_2004_Monitoring_STL.pdf` (16 pp) | `maler2004monitoring` | Первичный источник определения STL — основа количественного матчинга в FLV. | 1.3 «STL/MTL: подходы к мониторингу»; 2.3 «Метрические предикаты» |
| 3 | Bartocci E., Falcone Y. (eds.) «Lectures on Runtime Verification» | 2018 | book (LNCS 10457) | 10.1007/978-3-319-75632-5 | CLOSED (Springer LNCS) | — | `bartocci2018lectures` | Главный учебник по RV — справочник по терминологии, алгоритмам, инструментам. | 1.1 «RV как парадигма»; используется во всех главах |
| 4 | Bartocci E., Falcone Y., Francalanza A., Reger G. «Introduction to Runtime Verification» | 2018 | book-chapter (Lectures on RV, гл. 1, стр. 1–33) | 10.1007/978-3-319-75632-5_1 | CLOSED (Springer LNCS; HAL отдаёт обёрточную страницу без файла) | — | `bartocci2018introduction` | Обзорная глава с классификацией RV-подходов — каркас для §1.1 ВКР. | 1.1 «RV: цели, метрики, классификация» |
| 5 | Ničković D., Yamaguchi T. «RTAMT: Online Robustness Monitors from STL» | 2020 | book-chapter (ATVA 2020, LNCS 12302, 51 цитирование) | 10.1007/978-3-030-59152-6_34 | PDF (arXiv 2005.11827) | `Nickovic_2020_RTAMT.pdf` (13 pp) | `nickovic2020rtamt` | Описание актуального open-source инструмента RTAMT — прямой аналог нашего FLV в части STL-мониторинга. | 1.4 «Аналоги и инструменты»; 4.2 «Сравнение с RTAMT» |
| 6 | Deshmukh J.V., Donzé A., Ghosh S., Jin X., Juniwal G., Seshia S.A. «Robust online monitoring of signal temporal logic» | 2017 | journal-article (FMSD 51:5–30, 162 цитирования) | 10.1007/s10703-017-0286-7 | PDF (arXiv 1506.08234, журнальная версия + RV15-конфверсия) | `Deshmukh_2017_Robust_Online_STL.pdf` (17 pp); `Deshmukh_2015_Robust_Online_STL_RV15conf.pdf` (15 pp) | `deshmukh2017robust` | Алгоритмы онлайн-вычисления robustness STL — база для онлайн-режима матчера в Phase 4. | 2.4 «Онлайн-мониторинг»; 3.3 «Алгоритм матчера» |
| 7 | Donzé A. «Breach: A Toolbox for Verification and Parameter Synthesis of Hybrid Systems» | 2010 | book-chapter (CAV 2010, LNCS 6174, 333 цитирования) | 10.1007/978-3-642-14295-6_17 | CLOSED (Springer LNCS; авторская страница не выкладывает) | — | `donze2010breach` | Описание инструмента Breach — второй ключевой аналог FLV для гибридных систем. | 1.4 «Аналоги»; 4.2 «Сравнение» |
| 8 | Donzé A., Maler O. «Robust Satisfaction of Temporal Logic over Real-Valued Signals» | 2010 | book-chapter (FORMATS 2010, LNCS 6246, 491 цитирование) | 10.1007/978-3-642-15297-9_9 | PDF (VERIMAG sensiform.pdf) | `Donze_2010_Robust_Satisfaction.pdf` (16 pp) | `donze2010robust` | Количественная семантика STL (robustness degree) — основа метрик в FLV. | 2.3 «Количественная семантика»; 3.3 «Robustness как метрика отклонения» |
| 9 | Reinbacher T., Függer M., Brauer J. «Runtime verification of embedded real-time systems» | 2014 | journal-article (FMSD 44:203–239, CC-BY 2.0, открытый доступ) | 10.1007/s10703-013-0199-z | PDF (Springer Open) | `Reinbacher_2014_Embedded_RV.pdf` (37 pp) | `reinbacher2014embedded` | Past-time LTL RV для встраиваемых систем (расширение работ по асинхронному hardware) — обоснование low-overhead требований к FLV-модулю. | 1.5 «Embedded RV»; 4.3 «Накладные расходы матчера» |
| 10 | Koymans R. «Specifying real-time properties with metric temporal logic» | 1990 | journal-article (Real-Time Systems 2:255–299, 824 цитирования) | 10.1007/BF01995674 | CLOSED (Springer paywall) | — | `koymans1990specifying` | Классическая статья — введение MTL, исторический контекст для STL. | 1.3 «История MTL/STL» |

**Итого:** 10 работ, BibTeX-записей в `01_Источники/BIBLIO.bib`: 10. PDF скачано: **7 из 10** (Alur 1994, Maler 2004, Nickovic 2020 RTAMT, Deshmukh 2017, Donzé-Maler 2010 Robust Satisfaction, Reinbacher 2014; +дополнительно RV15-конфверсия Deshmukh).

## Статус PDF — детализация

Из 10 работ удалось получить **7 PDF** через open-access источники (авторские страницы VERIMAG и UPenn, arXiv, Springer Open). Остаются **3 закрытых** — нужны через ЭБС МГТУ или Springer-доступ Бауманки:

| Работа | Где искать в ЭБС / альтернатива |
|---|---|
| `bartocci2018lectures` (книга целиком) | Springer Link → MGTU subscription. DOI: 10.1007/978-3-319-75632-5 |
| `bartocci2018introduction` (глава 1 книги) | Springer Link DOI: 10.1007/978-3-319-75632-5_1. HAL hal-01762297 в текущий момент не отдаёт PDF корректно (только HTML-обёртка). Альтернатива: `dl.acm.org/doi/abs/...` |
| `donze2010breach` | Springer Link DOI: 10.1007/978-3-642-14295-6_17 |
| `koymans1990specifying` | Springer Link DOI: 10.1007/BF01995674 |

Имена при ручной докачке (соблюсти конвенцию):

```
Bartocci_2018_Lectures_RV.pdf           ← DOI 10.1007/978-3-319-75632-5  (книга целиком; опционально, не критично)
Bartocci_2018_Introduction_RV.pdf       ← DOI 10.1007/978-3-319-75632-5_1
Donze_2010_Breach.pdf                   ← DOI 10.1007/978-3-642-14295-6_17
Koymans_1990_MTL.pdf                    ← DOI 10.1007/BF01995674
```

Альтернативные точки доступа: arXiv, ResearchGate, авторские страницы (Bartocci TU Wien, Falcone Inria Grenoble, Reger Manchester), Google Scholar → «All versions».

## Замечание о работе #9 (Reinbacher 2014)

В исходном брифе значилось «Past Time LTL Runtime Verification for Asynchronous Hardware». В CrossRef с этой формулировкой найдены **три родственные публикации тех же авторов**:

- Reinbacher, Brauer, Horauer, Steininger, Kowalewski (2011) FMICS — `10.1007/978-3-642-24431-5_5` («Past Time LTL Runtime Verification for Microcontroller Binary Code»).
- Reinbacher, Függer, Brauer (2013) RV — `10.1007/978-3-642-35632-2_13` («Real-Time Runtime Verification on Chip»).
- Reinbacher, Függer, Brauer (2014) FMSD — `10.1007/s10703-013-0199-z` («Runtime verification of embedded real-time systems»).

Точное название «Past Time LTL Runtime Verification for Asynchronous Hardware» в CrossRef отсутствует — вероятно, это рабочее/препринтное название одной из перечисленных работ. **Принято решение** взять журнальную статью FMSD 2014 (`reinbacher2014embedded`) как наиболее полную и единственную с CC-BY 2.0 лицензией; работы 2011 (FMICS) и 2013 (RV) включены в неё как ссылки. Если научрук попросит именно ту формулировку — стоит уточнить и при необходимости заменить на `10.1007/978-3-642-24431-5_5`.

## Что покрыто этой партией для главы 1 ВКР

- §1.1 «Runtime Verification: концепция и место в V&V измерительных систем» — `bartocci2018lectures`, `bartocci2018introduction`.
- §1.2 «Формальные модели измерительных процессов: Timed FSM, гибридные автоматы» — `alur1994theory`.
- §1.3 «Темпоральные логики реального времени: MTL → STL» — `koymans1990specifying`, `maler2004monitoring`, `donze2010robust`.
- §1.4 «Аналоги и open-source инструменты RV для cyber-physical» — `donze2010breach`, `nickovic2020rtamt`, `deshmukh2017robust`.
- §1.5 «Embedded и low-overhead RV» — `reinbacher2014embedded`.

## Что ещё нужно докачать (вторая партия Phase 1, отдельные подзадачи)

- **02_Метрология:** Шишкин «Теоретическая метрология», Кравченко «Информационно-измерительные системы», ГОСТ Р 8.563.
- **03_LabVIEW_TestStand:** документация TestStand SA, VI Analyzer, Requirements Gateway.
- **04_FSM_Timed:** Lee&Seshia «Introduction to Embedded Systems», UPPAAL tutorial.
- **05_DSL_формализация:** Voelter «DSL Engineering», SysML 1.7 specification.

## Источники метаданных

Все DOI и поля (авторы, страницы, год, ISBN, тип) верифицированы через CrossRef API (`https://api.crossref.org/works/<DOI>`) на дату 2026-05-03. Файлы метаданных не сохранены отдельно — итог в `BIBLIO.bib` и в этой таблице.
