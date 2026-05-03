# Электрические/блок-схемы для ВКР

Для ВКР по приборостроению нужны минимум 3 типа схем:

1. **Структурная (блок-) схема стенда S1** — термокамера, PT100, АЦП, драйвер, контроллер, ПК. Глава 4.
2. **Электрическая принципиальная схема измерительной цепи** — мост Уитстона / 4-проводная схема для PT100 + усилитель + АЦП. Глава 4.
3. **Функциональная схема ИИС** — обобщённая, с местом FLV-модуля в контуре. Глава 1-2.

## Что использовать

| Инструмент | Когда применять | Плюсы | Минусы |
|---|---|---|---|
| **schemdraw (Python)** | Электрические схемы (компоненты, проводники, измерительные цепи) | Программная генерация → git-friendly, воспроизводимо. Прямой экспорт SVG/PNG. Хорошо смотрится в .docx. | Не для PCB layout. Стиль скромнее CircuiTikz. |
| **Mermaid `flowchart`** | Структурные/блок-схемы (стенд, контур ИИС, архитектура) | Уже используется в проекте. PNG через `scripts/mermaid_to_png.py`. | Не для электротехнических символов. |
| **draw.io / diagrams.net** | Гибрид: блок-схемы с электрическими символами, GUI | Удобный GUI, есть библиотека электрических компонентов. Можно сохранить XML и коммитить. | Не код-генерируемо, ручная правка. |
| **KiCad / Circuit-Synth** | Полноценные электрические схемы + PCB | Профессиональный уровень. | Overkill для бакалаврской ВКР. |

## Рекомендация для проекта

**schemdraw + Mermaid**:
- Структурные/функциональные/архитектурные схемы → Mermaid (как сейчас).
- Электрические принципиальные схемы (4-провод PT100, усилитель, АЦП) → schemdraw.

draw.io — backup, если будет специфичная схема, которую трудно сделать программно.

## Установка schemdraw

```bash
pip install schemdraw
```

Дополнительно для качественного PNG: `pip install matplotlib`.

## Шаблон: блок-схема стенда S1

```python
import schemdraw
import schemdraw.elements as elm
import schemdraw.flow as flow

with schemdraw.Drawing(file='03_Симулятор/figures/stand_block_diagram.png', dpi=300) as d:
    d.config(unit=2)
    d += (chamber := flow.Box(w=3, h=1.5).label('Термокамера\n+ образец'))
    d += flow.Arrow().right().length(1).label('T(t)', loc='top')
    d += (sensor := flow.Box(w=2.5, h=1.5).label('PT100\nдатчик'))
    d += flow.Arrow().right().length(1).label('R(T)', loc='top')
    d += (adc := flow.Box(w=2, h=1.5).label('АЦП\n16 бит'))
    d += flow.Arrow().right().length(1).label('код', loc='top')
    d += (host := flow.Box(w=2.5, h=1.5).label('ПК + LabVIEW\nили Python'))
    d += flow.Arrow().left().length(1).label('control', loc='bottom').at(host.W).to(chamber.E - (0, 1.5))
```

## Шаблон: 4-проводная измерительная схема PT100

```python
import schemdraw
import schemdraw.elements as elm

with schemdraw.Drawing(file='03_Симулятор/figures/pt100_4wire.png', dpi=300) as d:
    d.config(unit=2)
    d += (src := elm.SourceI().label('I = 1 mA', loc='left'))
    d += elm.Line().right(2)
    d += (rs := elm.Resistor().label('PT100\nR(T)', loc='right').down())
    d += elm.Line().left(2)
    d += elm.Line().up().tox(src.start)
    d += (volt := elm.Voltmeter().right().at(rs.start - (1, 0)).label('U_meas', loc='top'))
```

## Где взять готовые символы

Schemdraw поддерживает:
- **Базовые элементы:** R, C, L, источники тока/напряжения, диоды, транзисторы.
- **Логические вентили:** AND, OR, NOT, NAND, NOR, XOR.
- **Функциональные блоки** (`schemdraw.flow`): boxes, arrows, decisions.
- **Аналоговые блоки:** ОУ, компараторы.
- **DSP** (`schemdraw.dsp`): сумматоры, фильтры, ADCs.

Полная документация: <https://schemdraw.readthedocs.io/>.

## Интеграция в наш workflow

1. Скрипт-генератор схемы — в `03_Симулятор/figures/build_*.py` (один файл на схему, для воспроизводимости).
2. Output — PNG 300 DPI в той же папке.
3. Источник Python и PNG — оба коммитятся в git.
4. В Markdown главы 4: `![Рис. 4.1 — Структурная схема стенда S1](figures/stand_block_diagram.png)`.

## Ссылки

- **schemdraw** (основной): <https://github.com/cdelker/schemdraw>
- **Документация:** <https://schemdraw.readthedocs.io/>
- **Скилл от Dan McCreary** (англ.): пример Claude-skill для schemdraw — <https://www.linkedin.com/posts/danmccreary_schemdraw-circuit-generator-circuits-1-activity-7423198046684934144-ZJG_>
- **scientific-schematics SKILL.md** в davila7/claude-code-templates: <https://github.com/davila7/claude-code-templates/blob/main/cli-tool/components/skills/scientific/scientific-schematics/SKILL.md>
- **Circuit-Synth** (если потребуется PCB): <https://github.com/circuit-synth/circuit-synth>
- **kicad-happy** (для KiCad-flow): <https://github.com/aklofas/kicad-happy>

## Если требуется PCB / схемотехника глубже

Маловероятно для нашей ВКР (фокус — алгоритмический FLV-метод, а не разработка печатной платы), но если научрук попросит spec-уровень:
1. **KiCad** — открытый pro-grade EDA. Установка: <https://www.kicad.org/>.
2. **kicad-happy** Claude skill: автоматизирует анализ DRC/ERC, BoM, gerber-export.
3. **Circuit-Synth** — Python → KiCad netlist, удобно для AI-генерации.

В нашем случае ограничимся структурными и принципиальными схемами уровня измерительного канала. Этого достаточно для главы «Описание стенда» и «Программная реализация».
