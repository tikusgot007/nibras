import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize startup probe JSON results into Markdown tables (Fase 0 Uji #2)"
    )
    parser.add_argument(
        "--dir",
        default="results/startup",
        help="Directory containing startup test result JSON files (default: results/startup)",
    )
    return parser.parse_args()


def natural_sort_key(s: str) -> List[Any]:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def parse_scenario_name(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    match = re.match(r"^(.+)-run-\d+$", base)
    if match:
        return match.group(1)
    return base


def compute_median_max(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return round(statistics.median(values), 1), round(max(values), 1)


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
        print(f"No JSON result files found in {results_dir}")
        return

    json_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

    scenario_runs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for fpath in json_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["_file"] = os.path.basename(fpath)
                scen = parse_scenario_name(fpath)
                scenario_runs[scen].append(data)
        except Exception as e:
            sys.stderr.write(f"Skipping malformed file {fpath}: {e}\n")

    print("### Tabel Hasil Uji Waktu Startup per Skenario\n")
    print("| Skenario | Run | Median T3 (ms) | Maks T3 (ms) | Median T6 (ms) | Maks T6 (ms) | Isolasi OK | Status |")
    print("|---|---|---|---|---|---|---|---|")

    scenario_import_timings: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    for scen, runs in sorted(scenario_runs.items(), key=lambda x: natural_sort_key(x[0])):
        run_count = len(runs)
        t3_vals = [r.get("elapsed_from_t0_ms", {}).get("T3", 0.0) for r in runs]
        t6_vals = [r.get("elapsed_from_t0_ms", {}).get("T6", 0.0) for r in runs]

        med_t3, max_t3 = compute_median_max(t3_vals)
        med_t6, max_t6 = compute_median_max(t6_vals)

        isolation_passed = all(r.get("isolation", {}).get("passed", False) for r in runs)
        all_passed = all(r.get("passed", False) for r in runs)

        iso_str = "100%" if isolation_passed else "FAIL"
        status_str = "PASS" if all_passed else "FAIL"

        print(
            f"| `{scen}` | {run_count} | {med_t3:,.1f} | {max_t3:,.1f} | "
            f"{med_t6:,.1f} | {max_t6:,.1f} | {iso_str} | {status_str} |"
        )

        for r in runs:
            timings = r.get("import_timings_ms", {})
            for pkg, duration in timings.items():
                if duration > 0:
                    scenario_import_timings[scen][pkg].append(duration)

    print("\n### Rincian Tonggak Waktu (Median ms per Skenario)\n")
    print("| Skenario | T1 (Interpreter) | T2 (Qt Ready) | T3 (First Paint) | T4 (Imports) | T5 (DBs) | T6 (Total Ready) |")
    print("|---|---|---|---|---|---|---|")

    for scen, runs in sorted(scenario_runs.items(), key=lambda x: natural_sort_key(x[0])):
        t1_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T1", 0.0) for r in runs])
        t2_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T2", 0.0) for r in runs])
        t3_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T3", 0.0) for r in runs])
        t4_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T4", 0.0) for r in runs])
        t5_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T5", 0.0) for r in runs])
        t6_med, _ = compute_median_max([r.get("elapsed_from_t0_ms", {}).get("T6", 0.0) for r in runs])

        print(f"| `{scen}` | {t1_med:,.1f} | {t2_med:,.1f} | {t3_med:,.1f} | {t4_med:,.1f} | {t5_med:,.1f} | {t6_med:,.1f} |")

    focus_scen = "usb3-cold" if "usb3-cold" in scenario_import_timings else (list(scenario_import_timings.keys())[0] if scenario_import_timings else None)

    if focus_scen:
        print(f"\n### 5 Import Paling Lambat (Skenario `{focus_scen}`)\n")
        print("| Peringkat | Paket / Modul | Median Waktu (ms) | Maksimum Waktu (ms) |")
        print("|---|---|---|---|")

        pkg_stats = []
        for pkg, times in scenario_import_timings[focus_scen].items():
            med_time, max_time = compute_median_max(times)
            pkg_stats.append((pkg, med_time, max_time))

        pkg_stats.sort(key=lambda x: x[1], reverse=True)
        for rank, (pkg, med_time, max_time) in enumerate(pkg_stats[:5], 1):
            print(f"| {rank} | `{pkg}` | {med_time:,.1f} | {max_time:,.1f} |")


if __name__ == "__main__":
    main()
