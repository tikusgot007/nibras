import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checker spike for SQLite on USB after sudden unplug (Spike #1)"
    )
    parser.add_argument(
        "--db-dir",
        required=True,
        help="Target directory on the USB drive containing test databases",
    )
    parser.add_argument(
        "--host-log",
        required=True,
        help="Path to host PC log file containing recorded sequence numbers",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Identifier for this test run (e.g. run-01, 1, etc.)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for the JSON test result",
    )
    parser.add_argument(
        "--duration",
        default="-",
        help="Duration before unplugging (e.g. ~10 detik, ~30 detik, ~2 menit)",
    )
    parser.add_argument(
        "--scan-fix",
        default="-",
        help="Whether Windows Scan and Fix prompt appeared (Ya / Tidak)",
    )
    return parser.parse_args()


def detect_storage_files(db_dir: str) -> Tuple[List[str], List[str]]:
    rollback_journals = []
    wal_files = []
    if not os.path.exists(db_dir):
        return rollback_journals, wal_files
    for fname in os.listdir(db_dir):
        lower = fname.lower()
        if lower.endswith("-wal") or lower.endswith("-shm"):
            wal_files.append(fname)
        elif lower.endswith("-journal") or "-mj" in lower:
            rollback_journals.append(fname)
    return rollback_journals, wal_files


def read_host_log_info(host_log_path: str) -> Tuple[Optional[int], Optional[bool]]:
    if not os.path.exists(host_log_path):
        return None, None
    last_seq: Optional[int] = None
    last_fts5_enabled: Optional[bool] = None
    with open(host_log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line.startswith("# fts5_enabled:"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        val = parts[1].strip().lower()
                        last_fts5_enabled = (val in ("true", "1", "yes"))
                continue
            try:
                val = int(line)
                last_seq = val
            except ValueError:
                continue
    return last_seq, last_fts5_enabled


def check_integrity(conn: sqlite3.Connection, db_name: str) -> Tuple[bool, List[str]]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA {db_name}.integrity_check;")
    rows = cur.fetchall()
    errors = []
    for r in rows:
        val = r[0]
        if val != "ok":
            errors.append(str(val))
    return (len(errors) == 0), errors


def main() -> None:
    args = parse_args()

    db_dir = os.path.abspath(args.db_dir)
    host_log_path = os.path.abspath(args.host_log)
    out_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print(f"=== Nibras Fase 0 - Uji #1: SQLite Checker (Run: {args.run_id}) ===")
    print(f"DB Directory : {db_dir}")
    print(f"Host Log     : {host_log_path}")
    print(f"Output File  : {out_path}")
    print("==================================================================")

    failures: List[str] = []

    journal_files_before, wal_files_before = detect_storage_files(db_dir)
    hot_journal_detected = len(journal_files_before) > 0
    if wal_files_before:
        failures.append(f"Pelanggaran D-01: file WAL terdeteksi: {wal_files_before}")
    print(f"[STEP 1] Pre-open rollback journal files: {hot_journal_detected} {journal_files_before} (WAL files: {wal_files_before})")

    core_db_path = os.path.join(db_dir, "core_test.db")
    memory_db_path = os.path.join(db_dir, "memory_test.db")

    if not os.path.exists(core_db_path):
        failures.append(f"Database file not found: {core_db_path}")
    if not os.path.exists(memory_db_path):
        failures.append(f"Database file not found: {memory_db_path}")

    if failures:
        result: Dict[str, Any] = {
            "run_id": args.run_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "passed": False,
            "failures": failures,
            "hot_journal_detected": hot_journal_detected,
            "journal_files_before_open": journal_files_before,
            "wal_files_before_open": wal_files_before,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\n[FAIL] Test {args.run_id} failed with {len(failures)} error(s).")
        sys.exit(1)

    conn = sqlite3.connect(core_db_path)
    conn.execute("ATTACH DATABASE ? AS mem;", (memory_db_path,))
    print("[STEP 2] Databases opened in read-write mode (automatic rollback engaged).")

    core_ok, core_errs = check_integrity(conn, "main")
    mem_ok, mem_errs = check_integrity(conn, "mem")

    if not core_ok:
        failures.append(f"core_test.db integrity_check failed: {core_errs}")
    if not mem_ok:
        failures.append(f"memory_test.db integrity_check failed: {mem_errs}")

    print(f"[STEP 3] Integrity check -> core_test.db: {'OK' if core_ok else 'FAILED'}, memory_test.db: {'OK' if mem_ok else 'FAILED'}")

    cur = conn.cursor()
    cur.execute("SELECT MIN(seq), MAX(seq), COUNT(seq) FROM main.events;")
    core_min, core_max, core_count = cur.fetchone()

    cur.execute("SELECT MIN(seq), MAX(seq), COUNT(seq) FROM mem.entries;")
    mem_min, mem_max, mem_count = cur.fetchone()

    core_max = core_max or 0
    mem_max = mem_max or 0
    core_min = core_min or 0
    mem_min = mem_min or 0

    if core_count == 0 or core_min != 1:
        failures.append(f"core_test.db events MIN(seq)={core_min}, expected 1")
    if core_count != (core_max - core_min + 1):
        failures.append(
            f"core_test.db events COUNT={core_count} does not match MAX - MIN + 1 ({core_max - core_min + 1})"
        )

    if mem_count == 0 or mem_min != 1:
        failures.append(f"memory_test.db entries MIN(seq)={mem_min}, expected 1")
    if mem_count != (mem_max - mem_min + 1):
        failures.append(
            f"memory_test.db entries COUNT={mem_count} does not match MAX - MIN + 1 ({mem_max - mem_min + 1})"
        )

    equal_max_seq = (core_max == mem_max)
    if not equal_max_seq:
        failures.append(
            f"Cross-database sequence mismatch: core MAX(seq)={core_max} vs memory MAX(seq)={mem_max}"
        )
    print(f"[STEP 4] Sequence stats -> core MIN={core_min} MAX={core_max} COUNT={core_count} | mem MIN={mem_min} MAX={mem_max} COUNT={mem_count} (equal MAX: {equal_max_seq})")

    cur.execute(
        """
        SELECT seq FROM (
            SELECT seq, LAG(seq, 1) OVER (ORDER BY seq) as prev_seq
            FROM main.events
        ) WHERE prev_seq IS NOT NULL AND seq != prev_seq + 1;
        """
    )
    core_gaps = [r[0] for r in cur.fetchall()]

    cur.execute(
        """
        SELECT seq FROM (
            SELECT seq, LAG(seq, 1) OVER (ORDER BY seq) as prev_seq
            FROM mem.entries
        ) WHERE prev_seq IS NOT NULL AND seq != prev_seq + 1;
        """
    )
    mem_gaps = [r[0] for r in cur.fetchall()]

    has_gaps = bool(core_gaps or mem_gaps)
    if core_gaps:
        failures.append(f"Gaps detected in core_test.db events sequence at: {core_gaps[:10]}")
    if mem_gaps:
        failures.append(f"Gaps detected in memory_test.db entries sequence at: {mem_gaps[:10]}")
    print(f"[STEP 5] Sequence gaps -> core gaps: {len(core_gaps)}, memory gaps: {len(mem_gaps)}")

    cur.execute("SELECT seq, payload, checksum FROM main.events ORDER BY seq;")
    events_corrupted = 0
    events_verified = 0
    for seq_val, payload_val, expected_chk in cur:
        events_verified += 1
        actual_chk = hashlib.sha256(payload_val).hexdigest()
        if actual_chk != expected_chk:
            events_corrupted += 1

    cur.execute("SELECT seq, text, checksum FROM mem.entries ORDER BY seq;")
    entries_corrupted = 0
    entries_verified = 0
    for seq_val, text_val, expected_chk in cur:
        entries_verified += 1
        actual_chk = hashlib.sha256(text_val.encode("utf-8")).hexdigest()
        if actual_chk != expected_chk:
            entries_corrupted += 1

    if events_corrupted > 0:
        failures.append(f"Checksum mismatch in core_test.db: {events_corrupted} corrupted rows")
    if entries_corrupted > 0:
        failures.append(f"Checksum mismatch in memory_test.db: {entries_corrupted} corrupted rows")
    print(f"[STEP 6] Checksums verified -> events: {events_verified} (corrupted: {events_corrupted}), entries: {entries_verified} (corrupted: {entries_corrupted})")

    last_host_seq, fts_enabled = read_host_log_info(host_log_path)
    if last_host_seq is None:
        last_host_seq = 0

    max_db_seq = core_max
    lost_transactions = max(0, last_host_seq - max_db_seq)
    if lost_transactions > 1:
        failures.append(
            f"Lost committed transactions exceeded limit: {lost_transactions} lost (host_log={last_host_seq}, db={max_db_seq}, max allowed is 1)"
        )
    print(f"[STEP 7] Host log comparison -> host last_seq: {last_host_seq}, DB max_seq: {max_db_seq}, lost: {lost_transactions} (fts_enabled: {fts_enabled})")

    cur.execute("SELECT 1 FROM mem.sqlite_master WHERE type='table' AND name='entries_fts';")
    has_fts = cur.fetchone() is not None
    fts_status = "not_configured"
    if has_fts:
        try:
            conn.execute("INSERT INTO mem.entries_fts(entries_fts) VALUES('integrity-check');")
            fts_status = "ok"
            print("[STEP 8] FTS5 integrity check -> OK")
        except sqlite3.Error as e:
            fts_status = f"error: {e}"
            failures.append(f"FTS5 integrity-check failed: {e}")
            print(f"[STEP 8] FTS5 integrity check -> FAILED: {e}")
    else:
        print("[STEP 8] FTS5 table not present, skipped.")

    conn.close()

    journal_files_after, wal_files_after = detect_storage_files(db_dir)

    passed = (len(failures) == 0)

    result_data = {
        "run_id": args.run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration": args.duration,
        "prompt_scan_fix": args.scan_fix,
        "fts_enabled": fts_enabled,
        "passed": passed,
        "hot_journal_detected": hot_journal_detected,
        "journal_files_before_open": journal_files_before,
        "journal_files_after_check": journal_files_after,
        "wal_files_before_open": wal_files_before,
        "wal_files_after_check": wal_files_after,
        "integrity_check": {
            "core": "ok" if core_ok else core_errs,
            "memory": "ok" if mem_ok else mem_errs,
            "fts5": fts_status,
        },
        "sequence_analysis": {
            "core_min_seq": core_min,
            "core_max_seq": core_max,
            "core_count": core_count,
            "memory_min_seq": mem_min,
            "memory_max_seq": mem_max,
            "memory_count": mem_count,
            "equal_max_seq": equal_max_seq,
            "has_gaps": has_gaps,
            "core_gaps": core_gaps,
            "memory_gaps": mem_gaps,
        },
        "checksum_verification": {
            "events_verified": events_verified,
            "events_corrupted": events_corrupted,
            "entries_verified": entries_verified,
            "entries_corrupted": entries_corrupted,
        },
        "host_log_comparison": {
            "last_host_seq": last_host_seq,
            "max_db_seq": max_db_seq,
            "lost_transactions": lost_transactions,
        },
        "failures": failures,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    print("------------------------------------------------------------------")
    if passed:
        print(f"RESULT: PASS (Run {args.run_id})")
        sys.exit(0)
    else:
        print(f"RESULT: FAIL (Run {args.run_id})")
        for fail in failures:
            print(f" - {fail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
