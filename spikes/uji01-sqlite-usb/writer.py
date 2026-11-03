import argparse
import ctypes
import hashlib
import os
import platform
import sqlite3
import sys
import time


def get_volume_filesystem(path: str) -> str:
    if sys.platform != "win32":
        return "non-windows"
    try:
        abs_path = os.path.abspath(path)
        drive = os.path.splitdrive(abs_path)[0]
        if drive:
            root_path = drive + "\\"
        else:
            root_path = abs_path
        fs_buffer = ctypes.create_unicode_buffer(260)
        success = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root_path),
            None,
            0,
            None,
            None,
            None,
            fs_buffer,
            len(fs_buffer),
        )
        if success:
            return fs_buffer.value
    except Exception:
        pass
    return "Unknown"


def is_fts5_available() -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE fts_check USING fts5(content);")
        conn.close()
        return True
    except sqlite3.Error:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Writer spike for SQLite on USB during sudden unplug (Spike #1)"
    )
    parser.add_argument(
        "--db-dir",
        required=True,
        help="Target directory on the USB drive where databases will be created",
    )
    parser.add_argument(
        "--host-log",
        required=True,
        help="Path to host PC log file to record committed sequence numbers",
    )
    parser.add_argument(
        "--payload-bytes",
        type=int,
        default=1024,
        help="Size of random BLOB payload in bytes (default: 1024)",
    )
    parser.add_argument(
        "--fts",
        action="store_true",
        help="Enable writing to FTS5 virtual table in memory_test.db",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    db_dir = os.path.abspath(args.db_dir)
    os.makedirs(db_dir, exist_ok=True)

    host_log_path = os.path.abspath(args.host_log)
    host_log_dir = os.path.dirname(host_log_path)
    if host_log_dir:
        os.makedirs(host_log_dir, exist_ok=True)

    fs_type = get_volume_filesystem(db_dir)
    fts5_ok = is_fts5_available()
    py_version = platform.python_version()
    sqlite_ver = sqlite3.sqlite_version

    print("=== Nibras Fase 0 - Uji #1: SQLite USB Writer ===")
    print(f"Target DB dir : {db_dir}")
    print(f"Volume FS     : {fs_type}")
    print(f"Host Log      : {host_log_path}")
    print(f"Python ver    : {py_version}")
    print(f"SQLite ver    : {sqlite_ver}")
    print(f"FTS5 enabled  : {args.fts} (FTS5 library support: {fts5_ok})")
    print(f"Payload size  : {args.payload_bytes} bytes")
    print("==================================================")

    if args.fts and not fts5_ok:
        sys.stderr.write("ERROR: --fts requested but FTS5 module is not available in SQLite runtime.\n")
        sys.exit(1)

    host_log_file = open(host_log_path, "a", encoding="utf-8")
    host_log_file.write(f"# START_SESSION: {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    host_log_file.write(f"# python_version: {py_version}\n")
    host_log_file.write(f"# sqlite_version: {sqlite_ver}\n")
    host_log_file.write(f"# fts5_available: {fts5_ok}\n")
    host_log_file.write(f"# fts5_enabled: {args.fts}\n")
    host_log_file.write(f"# volume_filesystem: {fs_type}\n")
    host_log_file.write(f"# db_dir: {db_dir}\n")
    host_log_file.flush()
    os.fsync(host_log_file.fileno())

    core_db_path = os.path.join(db_dir, "core_test.db")
    memory_db_path = os.path.join(db_dir, "memory_test.db")

    conn = sqlite3.connect(core_db_path, isolation_level=None)

    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=FULL;")

    conn.execute(f"ATTACH DATABASE '{memory_db_path}' AS mem;")
    conn.execute("PRAGMA mem.journal_mode=DELETE;")
    conn.execute("PRAGMA mem.synchronous=FULL;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY,
            ts REAL,
            payload BLOB,
            checksum TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mem.entries (
            seq INTEGER PRIMARY KEY,
            ts REAL,
            text TEXT,
            checksum TEXT
        );
        """
    )
    if args.fts:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS mem.entries_fts USING fts5(
                text
            );
            """
        )

    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(seq), 0) FROM events;")
    max_events = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(MAX(seq), 0) FROM mem.entries;")
    max_entries = cur.fetchone()[0]

    current_seq = max(max_events, max_entries) + 1
    print(f"Resuming at sequence: {current_seq}")

    interval_tx = 0
    total_tx = 0
    last_report_time = time.monotonic()

    try:
        while True:
            ts = time.time()
            payload = os.urandom(args.payload_bytes)
            payload_checksum = hashlib.sha256(payload).hexdigest()

            text_content = f"seq:{current_seq} ts:{ts} chk:{payload_checksum}"
            text_checksum = hashlib.sha256(text_content.encode("utf-8")).hexdigest()

            conn.execute("BEGIN;")
            conn.execute(
                "INSERT INTO events (seq, ts, payload, checksum) VALUES (?, ?, ?, ?);",
                (current_seq, ts, payload, payload_checksum),
            )
            conn.execute(
                "INSERT INTO mem.entries (seq, ts, text, checksum) VALUES (?, ?, ?, ?);",
                (current_seq, ts, text_content, text_checksum),
            )
            if args.fts:
                conn.execute(
                    "INSERT INTO mem.entries_fts (text) VALUES (?);",
                    (text_content,),
                )
            conn.execute("COMMIT;")

            host_log_file.write(f"{current_seq}\n")
            host_log_file.flush()
            os.fsync(host_log_file.fileno())

            interval_tx += 1
            total_tx += 1

            now = time.monotonic()
            elapsed = now - last_report_time
            if elapsed >= 5.0:
                tps = interval_tx / elapsed
                print(f"[PROGRESS] seq: {current_seq} | Throughput: {tps:.1f} tx/s (total this run: {total_tx})")
                interval_tx = 0
                last_report_time = now

            current_seq += 1

    except KeyboardInterrupt:
        print("\n[STOP] Writer stopped by user (Ctrl+C).")
    except (sqlite3.Error, OSError) as e:
        print(f"\n[I/O INTERRUPTION] Caught expected disconnect/error: {type(e).__name__}: {e}")
    finally:
        try:
            host_log_file.write(f"# END_SESSION: {time.strftime('%Y-%m-%dT%H:%M:%S')} last_seq:{current_seq - 1}\n")
            host_log_file.flush()
            os.fsync(host_log_file.fileno())
            host_log_file.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

        print(f"[FINISHED] Last successfully recorded seq: {current_seq - 1}")


if __name__ == "__main__":
    main()
