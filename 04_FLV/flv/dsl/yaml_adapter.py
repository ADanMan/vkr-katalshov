"""
flv.dsl.yaml_adapter — DSL-адаптер для YAML-формата спецификации
нормативной модели методики.

Контракт: реализует Protocol `flv.core.DslAdapter`. Загружает YAML,
валидирует против `flv_dsl.schema.json` и собирает иммутабельный
объект `Spec` для ядра.

Schema живёт в `02_Спецификация/flv_dsl.schema.json` (Phase 2). По
умолчанию загружается оттуда — относительный путь резолвится через
поиск в стандартных локациях (см. _find_default_schema).

Используется ядром:
    from flv.dsl import YamlDslAdapter
    spec = YamlDslAdapter().load("02_Спецификация/dsl_v1.yaml")

Используется через plugin discovery:
    from flv.plugins import get
    Adapter = get("dsl_adapter", "yaml")
    spec = Adapter().load(path)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from ..core import (
    CheckSpec,
    DslAdapter,
    Spec,
    TransitionSpec,
    ViolationSpec,
)

logger = logging.getLogger(__name__)

# Имя файла со Schema внутри 02_Спецификация/
DEFAULT_SCHEMA_NAME = "flv_dsl.schema.json"


def _find_default_schema() -> Path | None:
    """Поиск flv_dsl.schema.json в стандартных локациях относительно
    рабочей директории и пакета."""
    candidates = [
        Path.cwd() / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
        Path.cwd().parent / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
        Path(__file__).resolve().parents[3] / "02_Спецификация" / DEFAULT_SCHEMA_NAME,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


@dataclass
class YamlDslAdapter(DslAdapter):
    """DSL-адаптер YAML → flv.core.Spec.

    Параметры
    ---------
    schema_path : путь к JSON-Schema. Если None — выполняется поиск
                  через _find_default_schema(). Если Schema не
                  найдена, валидация пропускается с warning.
    """

    schema_path: Path | None = None
    name: str = field(default="yaml", init=False)

    def __post_init__(self) -> None:
        if self.schema_path is None:
            self.schema_path = _find_default_schema()
        self._schema: dict[str, Any] | None = None
        if self.schema_path and Path(self.schema_path).exists():
            self._schema = json.loads(
                Path(self.schema_path).read_text(encoding="utf-8")
            )
        else:
            logger.warning(
                "flv_dsl.schema.json не найден; валидация пропускается. "
                "Установите schema_path явно для строгой проверки."
            )

    # ──────────────────────────────────────────────────────────────────

    def load(self, source: Path | str) -> Spec:
        """Загрузить и валидировать YAML, вернуть Spec."""
        data = self._read_yaml(source)
        errors = self._validate_obj(data)
        if errors:
            raise ValueError(
                "DSL не прошёл валидацию по Schema:\n  - "
                + "\n  - ".join(errors)
            )
        return self._build_spec(data, source=str(source))

    def validate(self, source: Path | str) -> list[str]:
        """Вернуть список ошибок валидации (пустой при успехе)."""
        try:
            data = self._read_yaml(source)
        except (yaml.YAMLError, OSError) as exc:
            return [f"Ошибка чтения {source}: {exc}"]
        errors = self._validate_obj(data)
        # Дополнительные семантические проверки
        errors.extend(self._semantic_check(data))
        return errors

    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _read_yaml(source: Path | str) -> dict[str, Any]:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"DSL не найден: {path}")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"DSL должен быть mapping в корне, получено {type(data).__name__}")
        return data

    def _validate_obj(self, data: dict[str, Any]) -> list[str]:
        if self._schema is None:
            return []
        validator = jsonschema.Draft7Validator(self._schema)
        return [
            f"{'/'.join(str(p) for p in err.absolute_path) or '(root)'}: {err.message}"
            for err in sorted(
                validator.iter_errors(data),
                key=lambda e: list(e.absolute_path),
            )
        ]

    @staticmethod
    def _semantic_check(data: dict[str, Any]) -> list[str]:
        """Семантические проверки сверх Schema."""
        errors: list[str] = []
        state_names = {s["name"] for s in data.get("states", []) if "name" in s}
        for tr in data.get("transitions", []):
            if tr.get("from") not in state_names:
                errors.append(
                    f"transition {tr.get('id', '?')}: from='{tr.get('from')}' не в states"
                )
            if tr.get("to") not in state_names:
                errors.append(
                    f"transition {tr.get('id', '?')}: to='{tr.get('to')}' не в states"
                )
        check_ids = {c["id"] for c in data.get("checks", []) if "id" in c}
        for vname, v in (data.get("violations_catalog") or {}).items():
            rc = v.get("related_check") if isinstance(v, dict) else None
            if rc and rc not in check_ids:
                errors.append(
                    f"violation '{vname}': related_check='{rc}' не определён в checks"
                )
        return errors

    @staticmethod
    def _build_spec(data: dict[str, Any], *, source: str) -> Spec:
        meta = data.get("meta") or {}
        process = data.get("process") or {}

        states_raw = data.get("states") or []
        states = tuple(s["name"] for s in states_raw)
        # Initial — либо явное поле, либо первое состояние с required=True,
        # либо просто первое состояние списка (как принято в большинстве
        # FSM-DSL).
        initial: str = data.get("initial_state") or states[0] if states else ""

        transitions = tuple(
            TransitionSpec(
                id=tr.get("id", f"{tr['from']}_to_{tr['to']}"),
                from_state=tr["from"],
                to_state=tr["to"],
                guard=tr.get("guard"),
                time_min_s=(tr.get("time") or {}).get("min"),
                time_max_s=(tr.get("time") or {}).get("max"),
                description=tr.get("description", ""),
            )
            for tr in (data.get("transitions") or [])
        )

        checks = tuple(
            CheckSpec(
                id=c.get("id", f"check_{i}"),
                kind=c["kind"],
                payload={k: v for k, v in c.items() if k not in {"id", "kind"}},
            )
            for i, c in enumerate(data.get("checks") or [])
        )

        violations_catalog: dict[str, ViolationSpec] = {}
        for code, v in (data.get("violations_catalog") or {}).items():
            if isinstance(v, str):
                # Упрощённая запись: code: "Сообщение"
                violations_catalog[code] = ViolationSpec(
                    code=code, severity="critical", message=v
                )
            else:
                violations_catalog[code] = ViolationSpec(
                    code=code,
                    severity=v.get("severity", "critical"),
                    message=v.get("message", ""),
                    related_check=v.get("related_check"),
                )

        return Spec(
            id=meta.get("id", "unnamed"),
            process_name=process.get("name", "unnamed_process"),
            states=states,
            initial_state=initial,
            parameters=dict(data.get("parameters") or {}),
            transitions=transitions,
            checks=checks,
            violations_catalog=violations_catalog,
            meta={"source_file": source, **meta},
        )


__all__ = ["YamlDslAdapter"]
