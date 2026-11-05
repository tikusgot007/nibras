"""Lock + recovery tests (D-08)."""

from __future__ import annotations

from pathlib import Path

from nibras.storage import conversations
from nibras.storage.databases import Databases
from nibras.storage.lock import (
    SingleInstanceLock,
    read_clean_shutdown,
    write_clean_shutdown,
)
from nibras.storage.recovery import run_recovery


def test_second_instance_lock_fails(data_dir: Path):
    first = SingleInstanceLock(data_dir)
    second = SingleInstanceLock(data_dir)
    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()
    # After release a new lock can be taken.
    third = SingleInstanceLock(data_dir)
    assert third.acquire() is True
    third.release()


def test_recovery_marks_streaming_interrupted(root_dir: Path):
    dbs = Databases(root_dir / "Data").open_all()
    try:
        conv_db = dbs["conversations.db"]
        conv_id = conversations.create_conversation(conv_db, "Tes")
        conversations.add_message(conv_db, conv_id, "user", "Halo")
        conversations.add_message(conv_db, conv_id, "assistant", "setengah",
                                  status="streaming")
        write_clean_shutdown(dbs["core.db"], False)
        assert read_clean_shutdown(dbs["core.db"]) is False

        temp_file = root_dir / "Temp" / "sisa.txt"
        temp_file.write_text("x")
        report = run_recovery(dbs, root_dir / "Temp")
        assert report["clean_shutdown"] is False
        assert report["quick_check"] == {n: "ok" for n in Databases.NAMES}
        assert report["temp_cleaned"] is True
        assert not temp_file.exists()
        assert report["interrupted_messages"] == 1
        msgs = conversations.list_messages(conv_db, conv_id)
        assert msgs[1]["status"] == "interrupted"
    finally:
        dbs.close()


def test_clean_shutdown_skips_recovery(root_dir: Path):
    dbs = Databases(root_dir / "Data").open_all()
    try:
        write_clean_shutdown(dbs["core.db"], True)
        report = run_recovery(dbs, root_dir / "Temp")
        assert report["clean_shutdown"] is True
        assert report["interrupted_messages"] == 0
    finally:
        dbs.close()
