"""
sim — Python-симулятор стенда S1 (термокамера со стабилизацией PT100)
для ВКР Катальшова Д.А., К2-81Б.

Тема ВКР: «Метод функционально-логической верификации программных
моделей измерительных процессов в составе ИИС».

Архитектура — см. 02_Спецификация/simulator_arch.md и
99_Артефакты/ADR_003_simulator_engineering_stack.md.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vkr-katalshov-sim")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"

__all__ = ["__version__"]
