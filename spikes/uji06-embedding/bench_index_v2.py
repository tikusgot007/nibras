"""Performance benchmark for Uji #6b Tahap 2 (brief section 6), one model per process
so S and B RAM numbers never mix.

Measures, for a single model (int8):
  - tokenizer + model load time
  - indexing time for 10,000 synthetic `mono` entries (1 vector each) and
    10,000 synthetic `bi` entries (text + alt, embedded separately -> 20,000
    vectors), built deterministically from the 500-entry corpus + corpus_alt
    the same way Uji #6's bench_index.py builds its synthetic set (prefixes /
    suffixes / digit jitter around real entries). Speed only, never quality.
  - median / p95 query latency (vector search over the mono index)
  - peak RSS of this process (resource.getrusage, cross-platform fallback to
    psutil's peak working set on Windows)
  - model file size on disk

No torch / transformers / sentence-transformers. No online services.

Usage: python bench_index_v2.py --model S --models-dir /path/to/models_s \
    --out ../../results/uji06b-raw
"""
import argparse
import json
import platform
import random
import sqlite3
import statistics
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


def _vary(text, rnd):
    text = f"{rnd.choice(PREFIXES)} {text[0].lower() + text[1:]}{rnd.choice(SUFFIXES)}"
    return "".join(
        str((int(ch) + rnd.randint(0, 3)) % 10) if ch.isdigit() and rnd.random() < 0.3 else ch
        for ch in text
    )


def synth_mono(corpus, n, seed=7):
    """Same construction as Uji #6's bench_index.synth(): n synthetic `mono` texts."""
    rnd = random.Random(seed)
    out = []
    while len(out) < n:
        base = rnd.choice(corpus)["text"]
        out.append(_vary(base, rnd))
    return out


def synth_bi(corpus, corpus_alt, n, seed=8):
    """n synthetic (text, text_alt) pairs, same variation scheme, same base entry
    for both sides of the pair so the pairing stays meaningful."""
    alt_by_id = {e["id"]: e["text_alt"] for e in corpus_alt}
    rnd = random.Random(seed)
    out_main, out_alt = [], []
    while len(out_main) < n:
        entry = rnd.choice(corpus)
        out_main.append(_vary(entry["text"], rnd))
        out_alt.append(_vary(alt_by_id[entry["id"]], rnd))
    return out_main, out_alt


def peak_rss_mb():
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB, macOS reports bytes.
        return round(ru / 1024, 1) if platform.system() != "Darwin" else round(ru / 2**20, 1)
    except Exception:
        mi = psutil.Process().memory_info()
        return round(getattr(mi, "peak_wset", mi.rss) / 2**20, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["S", "B"], required=True)
    ap.add_argument("--models-dir", required=True)
    ap.add_argument("--out", default=str(HERE.parent.parent / "results" / "uji06b-raw"))
    ap.add_argument("--n", type=int, default=10000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    models = Path(args.models_dir)

    corpus = json.loads((HERE / "dataset" / "corpus.json").read_text(encoding="utf8"))
    corpus_alt = json.loads((HERE / "dataset" / "corpus_alt.json").read_text(encoding="utf8"))
    queries = json.loads((HERE / "dataset" / "queries_v2.json").read_text(encoding="utf8"))
    qtexts = [q["query"] for q in queries]

    mono_texts = synth_mono(corpus, args.n)
    bi_main, bi_alt = synth_bi(corpus, corpus_alt, args.n)

    result = {
        "model": args.model,
        "env": {
            "os": platform.platform(),
            "cpu": platform.processor() or platform.machine(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
            "python": platform.python_version(),
            "onnxruntime": onnxruntime.__version__,
            "numpy": np.__version__,
            "tokenizers": tokenizers.__version__,
            "sqlite": sqlite3.sqlite_version,
        },
        "model_file_mb": round((models / "model_int8.onnx").stat().st_size / 2**20, 1),
        "n_entries": args.n,
    }

    emb = Embedder(models, "int8")
    result["load"] = {
        "tokenizer_s": round(emb.tokenizer_load_s, 4),
        "model_s": round(emb.model_load_s, 4),
    }

    t0 = time.perf_counter()
    mat_mono = emb.embed_passages(mono_texts, batch_size=32)
    t_mono = time.perf_counter() - t0
    result["index_mono"] = {
        "n_entries": args.n,
        "n_vectors": len(mono_texts),
        "total_s": round(t_mono, 2),
        "per_entry_ms": round(1000 * t_mono / args.n, 3),
        "batch_size": 32,
    }

    t0 = time.perf_counter()
    mat_bi_main = emb.embed_passages(bi_main, batch_size=32)
    mat_bi_alt = emb.embed_passages(bi_alt, batch_size=32)
    t_bi = time.perf_counter() - t0
    result["index_bi"] = {
        "n_entries": args.n,
        "n_vectors": len(bi_main) + len(bi_alt),
        "total_s": round(t_bi, 2),
        "per_entry_ms": round(1000 * t_bi / args.n, 3),
        "batch_size": 32,
    }

    lat = []
    for q in qtexts:
        t = time.perf_counter()
        qv = emb.embed_queries([q])[0]
        vector_topk(mat_mono, qv, 10)
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    result["query_ms"] = {
        "median": round(statistics.median(lat), 2),
        "p95": round(lat[int(0.95 * len(lat)) - 1], 2),
        "n": len(lat),
    }
    result["matrix_mb"] = {
        "mono": round(mat_mono.nbytes / 2**20, 1),
        "bi": round((mat_bi_main.nbytes + mat_bi_alt.nbytes) / 2**20, 1),
    }
    result["ram_peak_mb"] = peak_rss_mb()

    (out / f"bench_performance_{args.model}.json").write_text(
        json.dumps(result, indent=2), encoding="utf8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
