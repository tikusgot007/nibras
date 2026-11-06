"""Startup recovery after an unclean shutdown (D-08).

When the previous session did not end cleanly: run ``PRAGMA quick_check``
on all databases, clean ``Temp/``, and mark messages that were streaming
as ``interrupted`` (never resumed automatically). Returns a report dict
for the recovery screen.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .databases import Databases
from .lock import read_clean_shutdown


def run_recovery(dbs: Databases, temp_dir: Path) -> dict:
    """Run recovery checks. Returns a report with what was found and done."""
    previous = read_clean_shutdown(dbs["core.db"])
    report: dict = {
        # No recorded previous session (first launch) is not a crash.
        "clean_shutdown": previous is not False,
        "first_run": previous is None,
        "quick_check": {},
        "temp_cleaned": False,
        "interrupted_messages": 0,
    }
    if report["clean_shutdown"]:
        return report

    report["quick_check"] = dbs.quick_check_all()

    if Path(temp_dir).exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        report["temp_cleaned"] = True

    cur = dbs["conversations.db"].execute(
        "UPDATE messages SET status = 'interrupted' WHERE status = 'streaming'"
    )
    report["interrupted_messages"] = cur.rowcount
    dbs["conversations.db"].commit()
    return report
