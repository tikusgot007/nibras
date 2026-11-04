"""Performance benchmark for Uji #6 (index 10,000 entries, query latency, RAM).

The 10,000 synthetic entries are built deterministically from the 500-entry corpus
by composing a base statement with context prefixes/suffixes and number changes.
They are used for speed only, never for quality.

Usage: python bench_index.py --models C:/nibras-staging/models --out ../../results/uji06-raw
"""
import argparse
import json
import platform
import random
import sqlite3
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np
import onnxruntime
import psutil
import tokenizers

from common import Embedder, vector_topk

HERE = Path(__file__).parent
PREFIXES = [
    "Catatan:", "Ingat bahwa", "Note that", "Sejak awal tahun,", "As of last month,", "Untuk referensi,",
    "FYI,", "Perlu diingat:", "Reminder:", "Menurut catatan lama,", "Per the latest update,", "Kata Dimas,",
]
SUFFIXES = [
    "", "", " Berlaku sampai ada kabar baru.", " This applies in most cases.", " Prioritas sedang.",
    " Confirmed twice.", " Dicek ulang bulan lalu.", " Sumber: percakapan pribadi.", " Low priority.",
]


def synth(corpus, n, seed=7):
    rnd = random.Random(seed)
    out = []
    while len(out) < n:
        base = rnd.choice(corpus)["text"]
        text = f"{rnd.choice(PREFIXES)} {base[0].lower() + base[1:]}{rnd.choice(SUFFIXES)}"
        text = "".join(
            str((int(ch) + rnd.randint(0, 3)) % 10) if ch.isdigit() and rnd.random() < 0.3 else ch
            for ch in text
        )
        out.append(text)
    return out


def cpu_name():
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
            capture_output=True, text=True,
        )
        return r.stdout.strip()
    except Exception:
        return platform.processor()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="C:/nibras-staging/models")
    ap.add_argument("--out", default=str(HERE.parent.parent / "results" / "uji06-raw"))
    ap.add_argument("--n", type=int, default=10000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    models = Path(args.models)
    proc = psutil.Process()

    corpus = json.loads((HERE / "dataset" / "corpus.json").read_text(encoding="utf8"))
    queries = json.loads((HERE / "dataset" / "queries.json").read_text(encoding="utf8"))
    qtexts = [q["query"] for q in queries]
    big = synth(corpus, args.n)

    result = {
        "env": {
            "os": platform.platform(),
            "cpu": cpu_name(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
            "python": platform.python_version(),
            "onnxruntime": onnxruntime.__version__,
            "numpy": np.__version__,
            "tokenizers": tokenizers.__version__,
            "sqlite": sqlite3.sqlite_version,
        },
        "model_files_mb": {
            v: round((models / f"model_{v}.onnx").stat().st_size / 2**20, 1) for v in ("int8", "fp32")
        },
        "n_entries": args.n,
    }

    for variant in ("int8", "fp32"):
        emb = Embedder(models, variant)
        result[f"load_{variant}"] = {
            "tokenizer_s": round(emb.tokenizer_load_s, 4),
            "model_s": round(emb.model_load_s, 4),
        }
        if variant == "int8":
            t0 = time.perf_counter()
            mat = emb.embed_passages(big, batch_size=32)
            total = time.perf_counter() - t0
            result["index_int8"] = {
                "total_s": round(total, 2),
                "per_entry_ms": round(1000 * total / args.n, 3),
                "batch_size": 32,
            }
            lat = []
            for q in qtexts:
                t = time.perf_counter()
                qv = emb.embed_queries([q])[0]
                vector_topk(mat, qv, 10)
                lat.append((time.perf_counter() - t) * 1000)
            lat.sort()
            result["query_int8_ms"] = {
                "median": round(statistics.median(lat), 2),
                "p95": round(lat[int(0.95 * len(lat)) - 1], 2),
                "n": len(lat),
            }
            result["matrix_mb"] = round(mat.nbytes / 2**20, 1)
        del emb

    mi = proc.memory_info()
    result["ram_peak_mb"] = round(getattr(mi, "peak_wset", mi.rss) / 2**20, 1)
    (out / "bench_performance.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
