"""Startup/recovery ordering (D-08): the recovery report must appear only
after an UNCLEAN previous session, never on first launch or after a clean
shutdown."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nibras.app import Application
from nibras.storage import conversations
from nibras.storage.lock import read_clean_shutdown


def test_first_launch_has_no_recovery_report(root_dir: Path):
    app = Application(root_dir)
    report = app._prepare_databases()
    try:
        assert report["clean_shutdown"] is True
        assert report["first_run"] is True
        assert report["interrupted_messages"] == 0
        # The current session is now marked "not yet clean".
        assert read_clean_shutdown(app.dbs["core.db"]) is False
    finally:
        app._shutdown()


def test_clean_shutdown_means_no_report_next_start(root_dir: Path):
    first = Application(root_dir)
    first._prepare_databases()
    first._shutdown()  # writes clean_shutdown=1

    second = Application(root_dir)
    report = second._prepare_databases()
    try:
        assert report["clean_shutdown"] is True
        assert report["first_run"] is False
    finally:
        second._shutdown()


def test_crash_means_report_next_start(root_dir: Path):
    crashed = Application(root_dir)
    crashed._prepare_databases()
    conn = crashed.dbs["conversations.db"]
    conv = conversations.create_conversation(conn, "Tes")
    conversations.add_message(conn, conv, "assistant", "setengah",
                              status="streaming")
    # Simulate a crash / USB pull: connections vanish, no clean shutdown.
    crashed.dbs.close()
    crashed.dbs = None

    after = Application(root_dir)
    report = after._prepare_databases()
    try:
        assert report["clean_shutdown"] is False
        assert report["interrupted_messages"] == 1
        assert all(v == "ok" for v in report["quick_check"].values())
    finally:
        after._shutdown()


def test_http_client_loggers_do_not_write_request_urls(root_dir: Path):
    """The HTTP client logs 'POST <url>' at INFO. The log lives on the USB stick
    and the URL is the user's private endpoint, so it must not be recorded."""
    import logging

    from nibras.app import setup_logging

    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging(root_dir / "Data")
        for name in ("httpx", "httpx2", "httpcore", "openai"):
            assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING, name
    finally:
        for h in list(root.handlers):
            if h not in before:
                h.close()
                root.removeHandler(h)
