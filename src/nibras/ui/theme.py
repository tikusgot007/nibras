"""Midnight Agent theme (D-51) and bundled fonts.

Dark blue-charcoal background, cyan/teal accent. Inter for text,
JetBrains Mono for code (both OFL, bundled in ``App/fonts`` at build
time; system fonts are the fallback when the files are absent).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

BACKGROUND = "#0f141b"
SURFACE = "#171e28"
SURFACE_LIGHT = "#1f2937"
TEXT = "#e6edf3"
TEXT_MUTED = "#8b98a9"
ACCENT = "#22d3ee"
ACCENT_DARK = "#0e7490"
BORDER = "#2a3648"
USER_BUBBLE = "#12303a"
DANGER = "#ef4444"

QSS = f"""
QMainWindow, QWidget {{ background-color: {BACKGROUND}; color: {TEXT}; }}
QWidget#sidebar {{ background-color: {SURFACE}; border-right: 1px solid {BORDER}; }}
QListWidget {{ background-color: {SURFACE}; border: none; outline: none; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:selected {{ background-color: {SURFACE_LIGHT}; }}
QPushButton {{ background-color: {SURFACE_LIGHT}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 12px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; }}
QPushButton#primary {{ background-color: {ACCENT_DARK}; border-color: {ACCENT}; }}
QTextEdit, QLineEdit, QSpinBox {{ background-color: {SURFACE};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 6px;
    selection-background-color: {ACCENT_DARK}; }}
QTextBrowser {{ background-color: transparent; border: none; }}
QFrame#messageCard {{ background-color: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 8px; }}
QFrame#messageCardUser {{ background-color: {USER_BUBBLE};
    border: 1px solid {BORDER}; border-radius: 8px; }}
QStatusBar {{ background-color: {SURFACE}; color: {TEXT_MUTED}; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QSplitter::handle {{ background-color: {BORDER}; }}
QScrollBar:vertical {{ background: {SURFACE}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_LIGHT}; border-radius: 5px; }}
"""


def load_fonts(fonts_dir: Path) -> None:
    """Register bundled fonts if present; otherwise keep system fonts."""
    for name in ("Inter.ttf", "JetBrainsMono.ttf"):
        path = Path(fonts_dir) / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


def text_font() -> str:
    return "Inter"


def mono_font() -> str:
    return "JetBrains Mono"
