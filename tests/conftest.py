"""Shared fixtures for Nibras tests."""

from __future__ import annotations

import os
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


@pytest.fixture(scope="session")
def qapp():
    """ONE QApplication for the whole test session. Qt allows a single
    application object per process; mixing QCoreApplication and QApplication
    across test modules crashes the interpreter."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
