#!/usr/bin/env python3
"""
validate.py — валидация DSL-спецификации против flv_dsl.schema.json.

Usage:
    python validate.py dsl_v1.yaml
    python validate.py *.yaml

Возвращает 0 если все файлы валидны, 1 если есть ошибки.
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Установи: pip install pyyaml")
try:
    import jsonschema
except ImportError:
    sys.exit("Установи: pip install jsonschema")
import json


SCHEMA_PATH = Path(__file__).parent / "flv_dsl.schema.json"


def validate_one(yaml_path: Path, schema: dict) -> int:
    """Возвращает 0 = OK, 1 = ошибки."""
    with open(yaml_path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"[ERR] {yaml_path}: YAML parse error — {e}")
            return 1

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    # Дополнительные семантические проверки сверх Schema
    semantic_errors = []

    state_names = {s["name"] for s in data.get("states", [])}
    for tr in data.get("transitions", []):
        if tr["from"] not in state_names:
            semantic_errors.append(f"transition {tr.get('id', '?')}: from='{tr['from']}' не в states")
        if tr["to"] not in state_names:
            semantic_errors.append(f"transition {tr.get('id', '?')}: to='{tr['to']}' не в states")

    check_ids = {c["id"] for c in data.get("checks", []) if "id" in c}
    for vname, v in data.get("violations_catalog", {}).items():
        rc = v.get("related_check")
        if rc and rc not in check_ids:
            semantic_errors.append(f"violation '{vname}': related_check='{rc}' не определён")

    if not errors and not semantic_errors:
        print(f"[OK]  {yaml_path}")
        return 0

    print(f"[ERR] {yaml_path}:")
    for err in errors:
        loc = "/".join(str(p) for p in err.path) or "(root)"
        print(f"  Schema: {loc}: {err.message}")
    for msg in semantic_errors:
        print(f"  Semantic: {msg}")
    return 1


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    rc = 0
    for arg in sys.argv[1:]:
        for path in Path(".").glob(arg) if "*" in arg else [Path(arg)]:
            rc |= validate_one(path, schema)
    sys.exit(rc)


if __name__ == "__main__":
    main()
