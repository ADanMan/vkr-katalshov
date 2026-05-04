"""
flv.matchers — детерминированные matcher'ы для трёх условий приёма
трассы согласно `02_Спецификация/formal_model.md`:

* `sequence` — структурное условие (обязательность шагов и порядок).
* `timing` — длительности состояний в [t_min; t_max].
* `predicate` — гарды и checks-предикаты.

Все matcher'ы наследуют `BaseMatcher` (см. `base.py`) и независимо
эмитят `Violation`-объекты, которые позже агрегируются в `Verdict`.
"""

from .base import BaseMatcher
from .predicate import PredicateMatcher
from .sequence import SequenceMatcher
from .timing import TimingMatcher

__all__ = [
    "BaseMatcher",
    "PredicateMatcher",
    "SequenceMatcher",
    "TimingMatcher",
]
