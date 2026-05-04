"""
flv.adapters — pluggable-адаптеры источников трасс
(entry-points group `flv.source_adapter`, см. ADR-004).

Встроенные реализации:
* jsonl.JsonlAdapter — наш формат JSONL по
  `02_Спецификация/event_log.schema.json` (Phase 2).

Опциональные расширения (заглушки в Phase 4 — для главы 3 ПЗ как
демонстрация переносимости фреймворка на разные ИИС):
* labview — TDMS-файлы LabVIEW + Hook VI.
* teststand — XML-отчёты NI TestStand.
* serial — Arduino/ESP32 serial-стрим (для Wokwi/Velxio demo-track).
* scpi — лог SCPI-команд.
* otel — OpenTelemetry traces.
"""

from .jsonl import JsonlAdapter

__all__ = ["JsonlAdapter"]
