"""Lock + recovery tests (D-08)."""

from __future__ import annotations

import subprocess
import sys
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


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "from pathlib import Path;"
    "from nibras.storage.lock import SingleInstanceLock;"
    "sys.exit(0 if SingleInstanceLock(Path(sys.argv[2])).acquire() else 3)"
)


def _child_acquire(data_dir: Path) -> int:
    src = str(Path(__file__).resolve().parent.parent / "src")
    return subprocess.run(
        [sys.executable, "-c", _CHILD, src, str(data_dir)], timeout=60
    ).returncode


def test_second_process_is_rejected_while_first_holds_lock(data_dir: Path):
    """A real second OS process (a second Nibras.exe) must be refused."""
    first = SingleInstanceLock(data_dir)
    assert first.acquire() is True
    try:
        assert _child_acquire(data_dir) == 3
    finally:
        first.release()
    # After release another process can take it.
    assert _child_acquire(data_dir) == 0
