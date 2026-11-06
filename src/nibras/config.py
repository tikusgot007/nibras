"""Application defaults and settings (D-05, D-10, D-15, D-42).

Defaults are user-visible and editable in Settings. The API key is never
stored here: it lives only in the vault (``Data/vault.bin``) and in memory
while unlocked. Secrets must never be written to logs, databases, or
commits.
"""

from __future__ import annotations

# Provider defaults. The repository is public, so no endpoint URL or model
# name is hard-coded: the user fills both in Settings at first setup.
DEFAULT_BASE_URL = ""
DEFAULT_MODEL = ""
# Starting value for the model's context window (tokens); the user adjusts
# it in Settings to match the chosen model.
DEFAULT_CONTEXT_WINDOW = 1_000_000

DEFAULT_AUTO_LOCK_MINUTES = 30

APP_NAME = "Nibras"
APP_TITLE = "Nibras"

# Settings keys stored in core.db (settings table).
KEY_BASE_URL = "provider.base_url"
KEY_MODEL = "provider.model"
KEY_CONTEXT_WINDOW = "provider.context_window"
KEY_AUTO_LOCK_MINUTES = "vault.auto_lock_minutes"
KEY_THEME = "ui.theme"

DEFAULT_SETTINGS = {
    KEY_BASE_URL: DEFAULT_BASE_URL,
    KEY_MODEL: DEFAULT_MODEL,
    KEY_CONTEXT_WINDOW: str(DEFAULT_CONTEXT_WINDOW),
    KEY_AUTO_LOCK_MINUTES: str(DEFAULT_AUTO_LOCK_MINUTES),
    KEY_THEME: "midnight",
}

# How often (seconds) the auto-lock countdown in the status bar refreshes.
AUTO_LOCK_TICK_SECONDS = 30
