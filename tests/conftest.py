"""Shared fixtures for Nibras tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "Data"
    folder.mkdir()
    (tmp_path / "Temp").mkdir()
    return folder


@pytest.fixture()
def root_dir(tmp_path: Path) -> Path:
    (tmp_path / "Data").mkdir()
    (tmp_path / "Temp").mkdir()
    (tmp_path / "Backups").mkdir()
    return tmp_path
