"""Aggregate results/uji04-raw/*.json into a markdown table (no numbers invented)."""
import glob, json, os, statistics
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "results", "uji04-raw")
rows = []
for fx in ("plain", "code_heavy", "wide_mixed"):
    for mode in ("full", "batched"):
        for r in (1, 2, 3):
            d = json.load(open(os.path.join(RAW, f"{fx}_{mode}_run{r}.json"), encoding="utf-8"))
            if d.get("status") == "timeout":
                rows.append((fx, mode, r, "TIMEOUT", None, None, None, None, None, None)); continue
            rows.append((fx, mode, r, "ok", d["timer_lag_ms"]["p95"], d["timer_lag_ms"]["p99"], d["timer_lag_ms"]["max"],
                         d["click_delta_ms"]["p95"], d["click_delta_ms"]["max"], d["stream_seconds"]))
f = lambda v: "-" if v is None else f"{v:.1f}"
print("| fixture | mode | run | status | p95 lag | p99 lag | max lag | p95 klik | max klik | stream s |\n|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join([r[0], r[1], str(r[2]), r[3]] + [f(v) for v in r[4:]]) + " |")
