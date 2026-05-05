# 04_Литература / 04_FSM_Timed

Литература по конечным автоматам, тайм-автоматам, гибридным автоматам и автоматному программированию — для главы 2 «Метод» (формализация эталона как Timed FSM) и главы 1 «Аналитический обзор» (раздел про теоретическую базу).

## Таблица источников (Phase 1, вторая партия)

| # | Author | Year | Title | Status | BibKey | Зачем нужна / Раздел |
|---|---|---|---|---|---|---|
| 1 | Alur R., Dill D.L. | 1994 | A Theory of Timed Automata. TCS 126(2):183–235 | OPEN (PDF в `01_FLV_RV/`) | `alur1994theory` | Канон Timed Automata. **Уже добавлено в `01_FLV_RV/`** — здесь не дублируется, ссылка из BIBLIO работает. Раздел 2.1. |
| 2 | Behrmann G., David A., Larsen K.G. | 2004 | A Tutorial on Uppaal. SFM-RT 2004, LNCS 3185:200–236 | OPEN (PDF, uppaal.org) | `behrmann2004uppaal` | Описание Uppaal как промышленной реализации тайм-автоматов — близкий аналог нашему DSL+матчеру. Раздел 1.4. |
| 3 | Baier C., Katoen J.-P. | 2008 | Principles of Model Checking. MIT Press | CLOSED (книга) | `baier2008principles` | Учебник по model checking — терминология (LTS, traces, fairness), используется в §2.1, 2.3. |
| 4 | Lee E.A., Seshia S.A. | 2017 | Introduction to Embedded Systems: A Cyber-Physical Systems Approach (2nd ed.) MIT Press | OPEN (PDF, авторская страница ptolemy.berkeley.edu) | `lee2017embedded` | Стандартный учебник по CPS. Раздел 3 «FSM в моделировании», 6 «Continuous-Discrete» — формальная база DSL. Разделы 1.2, 2.1. |
| 5 | Henzinger T.A. | 1996 | The Theory of Hybrid Automata. Proc. 11th IEEE LICS, p. 278–292 | OPEN (PDF, Berkeley/Bremen mirror) | `henzinger1996hybrid` | Формализм гибридных автоматов — расширение тайм-автоматов на непрерывные переменные (температура, давление). Раздел 2.2. |
| 6 | Шалыто А.А., Мандриков Е.А., Чеботарева Ю.К. | 2009 | Автоматное программирование и параллельные вычисления. Известия вузов. Приборостроение. 52(10): 21–29 | OPEN (CC BY, CyberLeninka) | `shalyto2009avtomatnoe` | Автоматное программирование (SWITCH-технология) Шалыто — отечественная школа. Раздел 1.2 «Автоматное программирование как методологическая база DSL». |
| 7 | Белов И.В., Гонцова О.Ф. | 2014 | Разработка управления электронными часами на основе теории автоматов. Экономика и социум 2-5 (11): 254–258 | OPEN (CC BY, CyberLeninka) | `belov2014chasy` | Прикладной пример FSM для управления электронным устройством — иллюстрация в §2.1. |

## Замечание про Alur 1994

Работа `alur1994theory` уже была добавлена в `04_Литература/01_FLV_RV/Alur_1994_Timed_Automata.pdf` в первой волне (см. соответствующий `_README.md`). Дублировать файл не стали — BibTeX-ключ один. В тексте ВКР цитируется из BIBLIO.bib как `\cite{alur1994theory}` независимо от папки.

## Закрытые работы — где скачать

| Работа | Метод доступа |
|---|---|
| Baier & Katoen «Principles of Model Checking» (2008) | ISBN 978-0262026499. MIT Press. ЭБС МГТУ. PDF chapters в Springer/MIT (CC BY-SA для отдельных глав) — проверить на mitpress.mit.edu. |

## Что покрыто этой партией для главы 1-2 ВКР

- §1.2 «Формальные модели измерительных процессов: FSM → Timed FSM → Hybrid Automata» — `alur1994theory`, `behrmann2004uppaal`, `henzinger1996hybrid`, `lee2017embedded`.
- §1.2.4 «Автоматное программирование (SWITCH-технология)» — `shalyto2009avtomatnoe`, `belov2014chasy`, `kazanenko2015primenenie` (из 02_Метрология).
- §2.1 «Timed FSM как эталон для FLV» — `alur1994theory`, `lee2017embedded`, `baier2008principles`.
- §2.2 «Расширение до гибридной модели (для непрерывных переменных T, P)» — `henzinger1996hybrid`.
- §2.3 «Связь с Uppaal как промышленной реализацией» — `behrmann2004uppaal`.

## Compliance

- Lee & Seshia — авторы официально выложили 2-е издание в открытый доступ через ptolemy.berkeley.edu (свободное некоммерческое использование).
- Henzinger 1996 — preprint размещён авторами на Berkeley/Bremen mirror для образовательных целей.
- Behrmann et al. UPPAAL tutorial — SFM-RT 2004 LNCS, авторская версия на uppaal.org с разрешения Springer.
- Baier & Katoen — MIT Press copyright, к ВКР применяем правило ≤ 15 слов цитирования.
- Российские статьи (CyberLeninka) — лицензия CC BY.

## Источники метаданных

- DOI/Crossref для `behrmann2004uppaal` (10.1007/978-3-540-30080-9_7), `alur1994theory` (10.1016/0304-3975(94)90010-8).
- LICS 1996 для `henzinger1996hybrid` (DOI 10.1109/LICS.1996.561342, без года в Crossref → проставлен из proceedings 1996).
- ISBN для книг — сверка по `worldcat.org`.
- Российские — CyberLeninka citation_* meta.
