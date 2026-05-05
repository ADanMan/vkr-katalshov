# 04_Литература / 06_Семантический_разрыв

Эмпирические работы, подтверждающие тезис: **в реальном инструментальном/научном ПО типовые программные ошибки расходятся с нормативной методикой и проходят синтаксические проверки и юнит-тесты**. Это ключевая ссылочная база для ВВЕДЕНИЯ и раздела §1.5 «Семантический разрыв» главы 1 ПЗ.

## Таблица источников

| # | Работа | Год | Тип | DOI | Статус PDF | Файл / источник | BibKey | Тезис для главы 1 |
|---|---|---|---|---|---|---|---|---|
| 1 | Hatton L. «The T experiments: errors in scientific software» | 1997 | journal-article (IEEE CSE 4(2):27-38, 73 цит.) | 10.1109/99.609829 | PDF (leshatton.org) | `Hatton_1997_T_Experiments.pdf` | `hatton1997texperiments` | T1: 1 интерфейсная несогласованность на каждые 7 (Fortran) / 37 (C) интерфейсов; T2: точность вычислений падает с 6 до 1 значащей цифры из-за дефектов; до 40% ошибок статически детектируемы — но даже статически чистый код не гарантирует корректное измерение. |
| 2 | Soergel D. «Rampant software errors undermine scientific results» | 2014 | journal-article (F1000Research 3:303, CC-BY) | 10.12688/f1000research.5930.1 | PDF (F1000Research, open access) | `Soergel_2014_Rampant_Software_Errors.pdf` | `soergel2014rampant` | Систематизация эмпирических оценок частоты программных ошибок: от 1% LOC у NASA до 50% LOC у типового научного кода. Тезис: «если данные прошли через компьютер — большинство научных результатов могут содержать ошибку». |
| 3 | Ko A.J., Myers B.A., Aung H.H. «Six Learning Barriers in End-User Programming Systems» | 2004 | proc-paper (VL/HCC 2004, 340 цит.) | 10.1109/VLHCC.2004.47 | PDF (UW author page) | `Ko_2004_Six_Learning_Barriers.pdf` | `ko2004sixbarriers` | 6 типов барьеров для конечных пользователей-программистов (design / selection / coordination / use / understanding / information). Объясняет, почему инженеры-измерители (типичные end-user programmers в LabVIEW/TestStand/Python) делают семантические ошибки в синтаксически корректном коде. |
| 4 | Ko A.J., Myers B.A. «A framework and methodology for studying the causes of software errors in programming systems» | 2005 | journal-article (JVLC 16:41-84, 142 цит.) | 10.1016/j.jvlc.2004.08.003 | PDF (UW author page) | `Ko_2005_Software_Errors_Framework.pdf` | `ko2005framework` | Каркас «chain of cognitive breakdowns» — методологическая база для каталога нарушений FLV (Phase 2). Используется для классификации root-causes в §1.5. |
| 5 | Fan W., Jin H., Wang Y., Fu Y. «The influence of software timing error on measurement accuracy of data acquisition» | 2019 | journal-article (Meas. & Control 52:1008-1016, CC-BY) | 10.1177/0020294019858093 | CLOSED (open-access PDF на journals.sagepub.com) | — (web) | `fanwei2019timing` | Канонический пример: один и тот же стенд (RIGOL DG1022 + DS1102C + PCI7489) с тремя реализациями тайминга (VB Timer / multimedia timer / QueryPerformanceCounter) даёт воспроизводимость измерений 84.22% против 0.62% — нормативная методика измерения формально соблюдена, но программный таймер «сжирает» точность. |
| 6 | Paltenghi M., Pradel M. «Bugs in Quantum computing platforms: an empirical study» | 2022 | journal-article (PACMPL 6 OOPSLA1, 53 цит., CC-BY) | 10.1145/3527330 | PDF (arXiv 2110.14560) | `Paltenghi_2022_Bugs_Quantum_Computing.pdf` | `paltenghi2022quantum` | 223 реальных бага из 18 open-source платформ; 39.9% — domain-specific (квантовые); большинство манифестируются как «неожиданный выход», а не как краш — то есть проходят компилятор и юнит-тесты. Прямой аналог нашей ситуации в ИИС: семантические ошибки видимы только при сопоставлении с эталонной методикой. |
| 7 | Nguyen-Hoan L., Flint S., Sankaranarayana R. «A survey of scientific software development» | 2010 | proc-paper (ESEM 2010, 42 цит.) | 10.1145/1852786.1852802 | CLOSED (ACM DL) | — (web) | `nguyenhoan2010survey` | Опрос 60+ научных программистов: систематический дефицит формальных требований, отсутствие систематического тестирования, ad-hoc валидация. Источник статистики «как реально пишется измерительное ПО». |
| 8 | Popoola S., Zhao X., Gray J. «Evolution of Bad Smells in LabVIEW Graphical Models» | 2021 | journal-article (JOT 20(1):1, 3 цит., open access) | 10.5381/jot.2021.20.1.a1 | PDF (jot.fm) — лежит в `03_LabVIEW_TestStand/` | `Popoola_2021_Bad_Smells_LabVIEW.pdf` (в соседней папке) | `popoola2021badsmells` | Полуавтоматический анализ 81 LabVIEW-модели из 10 GitHub-репозиториев: 7 типов «bad smells», которые не отлавливаются компилятором, но ломают семантику измерения (Wire Tunnel Crossing, Long Wire, Cluttered Block Diagram и др.). |
| 9 | Zhao X., Rai G., Popoola S., Gray J. «Ask or tell: An empirical study on modeling challenges from LabVIEW community» | 2024 | journal-article (J. Comput. Languages 80:101284) | 10.1016/j.cola.2024.101284 | CLOSED (Elsevier) | — (web) | `zhao2024labview` | Двойное эмпирическое исследование: ML-анализ 162 000+ постов на forums.ni.com + опрос 60+ инженеров. Главный класс трудностей в LabVIEW — coding practice (программирование/моделирование, а не интерфейс прибора). Подтверждает массовость семантических ошибок в индустрии. |
| 10 | Грачева Н.О. «Методы метрологической аттестации программного обеспечения средств измерений» | 2006 | journal-article (Вестник УлГТУ № 2 (34)) | — (нет DOI) | PDF (CyberLeninka, открытый доступ) | `Gracheva_2006_Metrologicheskaya_Attestatsiya_PO.pdf` (в `02_Метрология/`) | `gracheva2006attestatsiya` | Российская работа: погрешности, вносимые алгоритмом и программной реализацией ПО СИ, выделены как самостоятельный источник недостоверности результата. Опорная русскоязычная ссылка для Введения и §1.5 ВКР. |

**Итого:** 10 BibTeX-записей. PDF скачано **6 из 10** (Hatton, Soergel, Ko 2004, Ko 2005, Paltenghi 2022, Грачева 2006 — последняя в `02_Метрология/`, Popoola 2021 — в `03_LabVIEW_TestStand/`). 4 закрытых: `fanwei2019timing` (Sage open-access, нужен прямой даунлоад с journals.sagepub.com), `nguyenhoan2010survey` (ACM DL — через ЭБС МГТУ), `zhao2024labview` (Elsevier — через ЭБС МГТУ), `popoola2021badsmells` лежит в соседней папке.

## Где какой PDF лежит физически

```
06_Семантический_разрыв/
├── Hatton_1997_T_Experiments.pdf
├── Ko_2004_Six_Learning_Barriers.pdf
├── Ko_2005_Software_Errors_Framework.pdf
├── Paltenghi_2022_Bugs_Quantum_Computing.pdf
└── Soergel_2014_Rampant_Software_Errors.pdf

03_LabVIEW_TestStand/
└── Popoola_2021_Bad_Smells_LabVIEW.pdf

02_Метрология/
└── Gracheva_2006_Metrologicheskaya_Attestatsiya_PO.pdf
```

Закрытые работы перечислены в таблице с DOI — попробовать через ЭБС МГТУ (Springer, Elsevier, ACM подписки) или через корпоративный VPN.

## Самая сильная работа для тезиса о семантическом разрыве

**`fanwei2019timing` (Fan, Jin, Wang, Fu 2019).** Это единственная работа в подборке, которая:

1. Использует реальный аппаратный стенд (RIGOL DG1022 + DS1102C + PCI7489) — то есть именно типовую ИИС.
2. Меняет **только программную реализацию таймера** при неизменной нормативной методике измерения.
3. Получает эмпирически **измеряемое** ухудшение метрики качества (повторяемость 0.62% → 84.22%).

Это «учебниковый» пример того, что синтаксически корректная и нормативно соответствующая программа может в 100 раз ухудшить точность измерения из-за одной семантической ошибки выбора API. Прямо обосновывает существование ниши для FLV: без сопоставления реальной траектории с временной семантикой эталонной FSM такие ошибки невидимы для классических V&V.

На втором месте — **`paltenghi2022quantum`** (большинство багов в платформах квантовых вычислений «тихие», не приводят к крашу), и **`hatton1997texperiments`** (классика — численная точность научного ПО).

## Compliance

Все авторы — академические исследователи США, ЕС, Великобритании, Австрии, Китая (Хуацяо), Австралии и РФ. Все журналы и конференции — техническое поле (IEEE CSE, F1000Research, VL/HCC, JVLC, Measurement & Control, PACMPL, ESEM, JOT, J. Comput. Languages, Вестник УлГТУ). Совпадений с реестрами иноагентов и нежелательных организаций РФ — **не обнаружено**. Категория риска для всех записей — **none**.

## Источники метаданных

DOI и ключевые поля (авторы, страницы, год, ISSN, тип публикации) верифицированы через CrossRef API на 2026-05-05. Поля, которые CrossRef не отдаёт, оставлены пустыми (не fabricate). PDF Hatton 1997 — с авторской страницы leshatton.org; Ko 2004/2005 — с faculty.washington.edu/ajko; Soergel 2014 — с f1000research.com (CC-BY 4.0); Paltenghi 2022 — с arXiv 2110.14560; Грачева 2006 — с CyberLeninka.
