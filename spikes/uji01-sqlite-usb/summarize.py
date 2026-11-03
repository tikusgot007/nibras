import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize test results JSON into Markdown table"
    )
    parser.add_argument(
        "--dir",
        default="results",
        help="Directory containing test result JSON files (default: results)",
    )
    return parser.parse_args()


def natural_sort_key(s: str) -> List[Any]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def format_integrity(integrity_data: Dict[str, Any]) -> str:
    core = integrity_data.get("core", "-")
    mem = integrity_data.get("memory", "-")
    fts = integrity_data.get("fts5", "-")
    core_str = "OK" if core == "ok" else "ERR"
    mem_str = "OK" if mem == "ok" else "ERR"
    if fts == "ok":
        fts_str = "OK"
    elif fts == "not_configured":
        fts_str = "-"
    else:
        fts_str = "ERR"
    return f"{core_str} / {mem_str} / {fts_str}"


def main() -> None:
    args = parse_args()
    results_dir = os.path.abspath(args.dir)

    if not os.path.exists(results_dir):
        sys.stderr.write(f"Directory not found: {results_dir}\n")
        sys.exit(1)

    json_files = [
        os.path.join(results_dir, f)
        for f in os.listdir(results_dir)
        if f.lower().endswith(".json")
    ]

    if not json_files:
        print("No JSON results found in", results_dir)
        return

    records: List[Dict[str, Any]] = []
    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                records.append(data)
        except Exception as e:
            sys.stderr.write(f"Skipping malformed file {fpath}: {e}\n")

    records.sort(key=lambda x: natural_sort_key(str(x.get("run_id", ""))))

    header = (
        "| Run ID | Durasi Cabut | Opsi `--fts` | Hot Journal Ada? | "
        "`integrity_check` (Core / Mem / FTS) | `MAX(seq)` Core | `MAX(seq)` Mem | "
        "`seq` Host Log | Tx Hilang | Prompt Scan & Fix? | Status (PASS/FAIL) |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|"

    print(header)
    print(separator)

    for r in records:
        run_id = r.get("run_id", "-")
        duration = r.get("duration", "-")

        fts_enabled = r.get("fts_enabled")
        if fts_enabled is not None:
            fts_opt = "Ya" if fts_enabled else "Tidak"
        else:
            fts_val = r.get("integrity_check", {}).get("fts5", "not_configured")
            fts_opt = "Tidak" if fts_val == "not_configured" else "Ya"

        hot_j = "Ya" if r.get("hot_journal_detected") else "Tidak"
        integ = format_integrity(r.get("integrity_check", {}))

        seq_info = r.get("sequence_analysis", {})
        core_max = seq_info.get("core_max_seq", "-")
        mem_max = seq_info.get("memory_max_seq", "-")

        host_info = r.get("host_log_comparison", {})
        host_seq = host_info.get("last_host_seq", "-")
        lost_tx = host_info.get("lost_transactions", "-")

        scan_fix = r.get("prompt_scan_fix", "-")
        status = "PASS" if r.get("passed") else "FAIL"

        row = (
            f"| {run_id} | {duration} | {fts_opt} | {hot_j} | "
            f"{integ} | {core_max} | {mem_max} | "
            f"{host_seq} | {lost_tx} | {scan_fix} | {status} |"
        )
        print(row)


if __name__ == "__main__":
    main()
