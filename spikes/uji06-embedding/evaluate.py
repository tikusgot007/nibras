"""Quality evaluation for Uji #6.

Configs: A vector int8, B vector fp32, C FTS5 BM25 only, D hybrid RRF (FTS5 + vector int8).
Metrics: Recall@1, Recall@5, MRR@10, total and per query type.

Usage: python evaluate.py --models C:/nibras-staging/models --out ../../results/uji06-raw
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from common import Embedder, FtsIndex, rrf, vector_topk

HERE = Path(__file__).parent
TYPES = ["id-id", "en-en", "id-en", "en-id", "informal", "typo"]


def metrics(ranked_ids_per_query, queries):
    """ranked_ids_per_query: list of lists of corpus ids (best first)."""
    agg = defaultdict(lambda: {"n": 0, "r1": 0, "r5": 0, "rr": 0.0})
    for q, ranked in zip(queries, ranked_ids_per_query):
        rel = set(q["relevant_ids"])
        r1 = int(bool(rel & set(ranked[:1])))
        r5 = int(bool(rel & set(ranked[:5])))
        rr = 0.0
        for pos, d in enumerate(ranked[:10], 1):
            if d in rel:
                rr = 1.0 / pos
                break
        for key in ("total", q["type"]):
            a = agg[key]
            a["n"] += 1
            a["r1"] += r1
            a["r5"] += r5
            a["rr"] += rr
    out = {}
    for key, a in agg.items():
        out[key] = {
            "n": a["n"],
            "recall@1": a["r1"] / a["n"],
            "recall@5": a["r5"] / a["n"],
            "mrr@10": a["rr"] / a["n"],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="C:/nibras-staging/models")
    ap.add_argument("--out", default=str(HERE.parent.parent / "results" / "uji06-raw"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    corpus = json.loads((HERE / "dataset" / "corpus.json").read_text(encoding="utf8"))
    queries = json.loads((HERE / "dataset" / "queries.json").read_text(encoding="utf8"))
    ids = [e["id"] for e in corpus]
    texts = [e["text"] for e in corpus]
    qtexts = [q["query"] for q in queries]

    fts = FtsIndex(ids, texts)
    ranked = {}
    vec_ranked_int8 = None

    for name, variant in (("A_vector_int8", "int8"), ("B_vector_fp32", "fp32")):
        emb = Embedder(Path(args.models), variant)
        mat = emb.embed_passages(texts)
        qv = emb.embed_queries(qtexts)
        rl = [[ids[i] for i in vector_topk(mat, qv[j], 10)] for j in range(len(queries))]
        ranked[name] = rl
        if variant == "int8":
            vec_ranked_int8 = [list(vector_topk(mat, qv[j], 50)) for j in range(len(queries))]

    ranked["C_fts5_bm25"] = [[ids[i] for i in fts.topk(q, 10)] for q in qtexts]
    ranked["D_hybrid_rrf"] = [
        [ids[i] for i in rrf([fts.topk(qtexts[j], 50), [int(x) for x in vec_ranked_int8[j]]], k=60, top=10)]
        for j in range(len(queries))
    ]

    results = {name: metrics(rl, queries) for name, rl in ranked.items()}
    (out / "quality_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf8")

    by_id = {e["id"]: e for e in corpus}
    failures = []
    for q, rl in zip(queries, ranked["A_vector_int8"]):
        if not set(q["relevant_ids"]) & set(rl[:5]):
            failures.append(
                {
                    "query_id": q["id"],
                    "type": q["type"],
                    "query": q["query"],
                    "relevant": [{"id": r, "text": by_id[r]["text"]} for r in q["relevant_ids"]],
                    "top5": [{"id": d, "text": by_id[d]["text"]} for d in rl[:5]],
                }
            )
    (out / "failures_config_A.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps({n: results[n]["total"] for n in results}, indent=2))
    print("failures A:", len(failures))


if __name__ == "__main__":
    main()
