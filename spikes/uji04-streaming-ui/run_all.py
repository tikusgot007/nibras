"""Run idle baseline + 3 fixtures x 2 modes x 3 runs, each in its own process."""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "results", "uji04-raw")
RUN_TIMEOUT = 420  # s; a run that hangs longer is killed and recorded as "timeout"
os.makedirs(OUT, exist_ok=True)


def run(args, name):
    path = os.path.join(OUT, name + ".json")
    if os.path.exists(path):
        print(name, "skipped (already exists)", flush=True)
        return
    t0 = time.time()
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "ui_probe.py"), *args, "--out", path],
                       timeout=RUN_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"status": "timeout", "name": name, "limit_s": RUN_TIMEOUT}, f)
    print(name, "done in", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    run(["--idle", "--idle-seconds", "10", "--run", "0"], "idle_baseline")
    for r in (1, 2, 3):
        for fx in ("plain", "code_heavy", "wide_mixed"):
            for mode in ("full", "batched"):
                run(["--fixture", fx, "--mode", mode, "--run", str(r)], f"{fx}_{mode}_run{r}")
