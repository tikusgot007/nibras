import sys
import time

T1_TIME = time.time()

import argparse
import importlib
import json
import os
import sqlite3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Startup probe for Nibras Fase 0 Uji #2")
    parser.add_argument("--t0", type=float, required=True, help="Epoch timestamp in milliseconds at process launch")
    parser.add_argument("--out", required=True, help="Path to write the JSON result")
    parser.add_argument("--data-dir", required=True, help="Target Data/ directory on USB for test databases")
    parser.add_argument("--bundle-dir", default="", help="Expected bundle root directory for isolation verification")
    return parser.parse_args()


def verify_isolation(bundle_dir: str) -> dict:
    bundle_real = os.path.realpath(bundle_dir) if bundle_dir else ""
    py_exec_real = os.path.realpath(sys.executable)
    py_prefix_real = os.path.realpath(sys.prefix)

    enable_user_site = None
    try:
        import site
        enable_user_site = getattr(site, "ENABLE_USER_SITE", None)
    except Exception:
        pass

    user_site_ok = (enable_user_site is False or enable_user_site is None)

    exec_in_bundle = (bundle_real == "" or py_exec_real.startswith(bundle_real))
    prefix_in_bundle = (bundle_real == "" or py_prefix_real.startswith(bundle_real))

    external_paths = []
    for p in sys.path:
        if not p:
            continue
        p_real = os.path.realpath(p)
        if bundle_real and not p_real.startswith(bundle_real):
            external_paths.append(p)

    sys_path_ok = (len(external_paths) == 0)
    passed = (user_site_ok and exec_in_bundle and prefix_in_bundle and sys_path_ok)

    return {
        "passed": passed,
        "sys_executable": sys.executable,
        "sys_prefix": sys.prefix,
        "bundle_dir": bundle_dir,
        "enable_user_site": enable_user_site,
        "user_site_ok": user_site_ok,
        "exec_in_bundle": exec_in_bundle,
        "prefix_in_bundle": prefix_in_bundle,
        "external_sys_paths": external_paths,
        "sys_path_count": len(sys.path),
        "sys_path": sys.path,
    }


def main() -> None:
    args = parse_args()
    t0_ms = args.t0
    t1_ms = T1_TIME * 1000.0

    bundle_dir = args.bundle_dir
    if not bundle_dir:
        exec_dir = os.path.dirname(os.path.realpath(sys.executable))
        bundle_dir = os.path.dirname(exec_dir)

    t2_start = time.perf_counter()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    app = QApplication.instance() or QApplication(sys.argv)
    t2_ms = time.time() * 1000.0

    t3_start = time.perf_counter()
    window = QMainWindow()
    window.setWindowTitle("Nibras Probe")
    window.setCentralWidget(QLabel("Nibras Portable Assistant Probe"))
    window.resize(320, 200)
    window.show()

    painted = False

    def on_painted():
        nonlocal painted
        painted = True
        window.close()
        app.quit()

    QTimer.singleShot(0, on_painted)
    app.exec()
    t3_ms = time.time() * 1000.0

    packages_to_import = [
        ("numpy", "numpy"),
        ("onnxruntime", "onnxruntime"),
        ("openai", "openai"),
        ("anthropic", "anthropic"),
        ("httpx", "httpx"),
        ("markdown_it", "markdown_it"),
        ("pygments", "pygments"),
        ("cryptography", "cryptography"),
        ("argon2", "argon2"),
        ("psutil", "psutil"),
        ("pywin32", "win32api"),
        ("mcp", "mcp"),
    ]

    import_timings = {}
    import_errors = {}
    for label, mod_name in packages_to_import:
        p_start = time.perf_counter()
        try:
            importlib.import_module(mod_name)
            dur = (time.perf_counter() - p_start) * 1000.0
            import_timings[label] = round(dur, 2)
        except Exception as e:
            import_errors[label] = str(e)
            import_timings[label] = -1.0

    t4_ms = time.time() * 1000.0

    data_dir = os.path.abspath(args.data_dir)
    os.makedirs(data_dir, exist_ok=True)
    db_names = ["core.db", "memory.db", "conversations.db", "index.db"]
    db_results = {}

    t5_start = time.perf_counter()
    for db_name in db_names:
        db_path = os.path.join(data_dir, db_name)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("PRAGMA synchronous=FULL;")
        cur = conn.cursor()
        cur.execute("PRAGMA quick_check;")
        qc_rows = cur.fetchall()
        qc_status = "ok" if (qc_rows and qc_rows[0][0] == "ok") else str(qc_rows)
        conn.close()
        db_results[db_name] = qc_status
    t5_ms = time.time() * 1000.0

    isolation = verify_isolation(bundle_dir)

    t6_ms = time.time() * 1000.0

    output_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamps": {
            "t0_launch": t0_ms,
            "t1_script_start": t1_ms,
            "t2_qt_ready": t2_ms,
            "t3_first_paint": t3_ms,
            "t4_imports_done": t4_ms,
            "t5_dbs_ready": t5_ms,
            "t6_ready": t6_ms,
        },
        "elapsed_from_t0_ms": {
            "T1": round(t1_ms - t0_ms, 2),
            "T2": round(t2_ms - t0_ms, 2),
            "T3": round(t3_ms - t0_ms, 2),
            "T4": round(t4_ms - t0_ms, 2),
            "T5": round(t5_ms - t0_ms, 2),
            "T6": round(t6_ms - t0_ms, 2),
        },
        "intervals_ms": {
            "interpreter_init": round(t1_ms - t0_ms, 2),
            "qt_init": round(t2_ms - t1_ms, 2),
            "first_paint": round(t3_ms - t2_ms, 2),
            "other_imports": round(t4_ms - t3_ms, 2),
            "db_init": round(t5_ms - t4_ms, 2),
            "finish": round(t6_ms - t5_ms, 2),
        },
        "import_timings_ms": import_timings,
        "import_errors": import_errors,
        "db_results": db_results,
        "isolation": isolation,
        "passed": isolation["passed"] and len(import_errors) == 0,
    }

    out_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    if not output_data["passed"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
