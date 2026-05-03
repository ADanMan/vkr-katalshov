"""Общие фикстуры pytest для тестов симулятора."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_sim_on_path() -> None:
    """Гарантирует, что пакет sim/ доступен при запуске pytest без
    предварительной установки `pip install -e`."""
    pkg_root = Path(__file__).resolve().parent.parent
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))


@pytest.fixture()
def tmp_jsonl(tmp_path: Path) -> Path:
    """Временный путь к .jsonl-файлу."""
    return tmp_path / "run.jsonl"
