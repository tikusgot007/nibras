"""Path resolution for Nibras.

All runtime data lives on the USB stick (D-07). The USB root is resolved
from the location of the running interpreter (``App/python``) or from the
``NIBRAS_ROOT`` environment variable (development / tests only).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_ROOT = "NIBRAS_ROOT"


def find_usb_root(start: Path | None = None) -> Path:
    """Return the USB root directory.

    Resolution order:
    1. ``NIBRAS_ROOT`` environment variable, when set.
    2. Walk up from the interpreter location: ``<root>/App/python``.
    3. Walk up from this file looking for a directory containing ``App/``.
    4. Fall back to the current working directory (dev only).
    """
    env = os.environ.get(ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()

    candidates: list[Path] = []
    if start is not None:
        candidates.append(Path(start))
    candidates.append(Path(sys.executable).resolve())
    candidates.append(Path(__file__).resolve())

    for cand in candidates:
        for parent in [cand, *cand.parents]:
            if (parent / "App").is_dir() and (parent / "Data").is_dir():
                return parent
            if parent.name == "python" and parent.parent.name == "App":
                return parent.parent.parent

    return Path.cwd().resolve()


def data_dir(root: Path | None = None) -> Path:
    return (root or find_usb_root()) / "Data"


def temp_dir(root: Path | None = None) -> Path:
    return (root or find_usb_root()) / "Temp"


def backups_dir(root: Path | None = None) -> Path:
    return (root or find_usb_root()) / "Backups"


def app_dir(root: Path | None = None) -> Path:
    return (root or find_usb_root()) / "App"


def ensure_layout(root: Path | None = None) -> Path:
    """Create Data/, Temp/ and Backups/ on the USB stick. Returns root."""
    root = root or find_usb_root()
    for folder in (data_dir(root), temp_dir(root), backups_dir(root),
                   data_dir(root) / "logs"):
        folder.mkdir(parents=True, exist_ok=True)
    return root
