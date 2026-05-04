"""
flv.dsl — pluggable-адаптеры формата описания нормативной модели
методики (entry-points group `flv.dsl_adapter`, см. ADR-004).

Встроенные реализации:
* yaml_adapter.YamlDslAdapter — наш YAML-DSL по
  `02_Спецификация/flv_dsl.schema.json`.

Опциональные расширения (заглушки в Phase 4 — для главы 3 ПЗ):
* rtamt_adapter — STL/MTL через RTAMT.
* sysml_adapter — OMG SysML state-machine.
"""

from .yaml_adapter import YamlDslAdapter

__all__ = ["YamlDslAdapter"]
