"""Quality evaluation for Uji #6b Tahap 2 (brief fase0-uji06b-embedding-lanjutan.md, section 4).

12 configurations x (queries.json v1, queries_v2.json v2) = 24 runs:
  Model:   S = multilingual-e5-small int8, B = multilingual-e5-base int8
  Entry:   mono = text only, bi = text + text_alt embedded separately,
           entry score = MAX of the two vectors' similarity
  Search:  vec = vector only, hyb1 = Hybrid RRF with FTS5 weight 1.0,
           hyb05 = Hybrid RRF with FTS5 weight 0.5

Hybrid rules (brief section 4, fixed before any run, never tuned on results):
  - FTS5 query side drops Indonesian+English stopwords (common.STOPWORDS_ID_EN).
    The indexed text is never stopword-filtered.
  - In `bi`, FTS5 indexes the concatenation of `text` and `text_alt`.
  - RRF uses k=60, top-50 from each source (FTS5 and vector).
  - FTS5 weight is only ever 1.0 (hyb1) or 0.5 (hyb05); vector weight is always 1.0.

No torch / transformers / sentence-transformers. No online services.

Usage:
  python evaluate_v2.py --models-s /path/models_s --models-b /path/models_b \
      --out ../../results/uji06b-raw
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from common import Embedder, FtsIndex, STOPWORDS_ID_EN, fts_query_stopwords, rrf, vector_topk
from evaluate import metrics, TYPES  # reuse Uji #6 metric/aggregation code

HERE = Path(__file__).parent
RRF_K = 60
RRF_TOPN_SOURCE = 50
FINAL_TOPN = 10


def load_dataset():
    corpus = json.loads((HERE / "dataset" / "corpus.json").read_text(encoding="utf8"))
    corpus_alt = json.loads((HERE / "dataset" / "corpus_alt.json").read_text(encoding="utf8"))
    alt_by_id = {e["id"]: e["text_alt"] for e in corpus_alt}
    ids = [e["id"] for e in corpus]
    texts = [e["text"] for e in corpus]
    alt_texts = [alt_by_id[i] for i in ids]
    queries_v1 = json.loads((HERE / "dataset" / "queries.json").read_text(encoding="utf8"))
    queries_v2 = json.loads((HERE / "dataset" / "queries_v2.json").read_text(encoding="utf8"))
    return ids, texts, alt_texts, {"v1": queries_v1, "v2": queries_v2}


def sims_mono(mat, qvec):
    return mat @ qvec


def sims_bi(mat_main, mat_alt, qvec):
    return np.maximum(mat_main @ qvec, mat_alt @ qvec)


def topk_from_sims(sims, k):
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    return idx[np.argsort(-sims[idx])]


def failures_for(config_name, ranked, queries, by_id, topn=5):
    out = []
    for q, rl in zip(queries, ranked):
        if not set(q["relevant_ids"]) & set(rl[:topn]):
            out.append(
                {
                    "query_id": q["id"],
                    "type": q["type"],
                    "query": q["query"],
                    "relevant": [{"id": r, "text": by_id[r]["text"]} for r in q["relevant_ids"]],
                    "top5": [{"id": d, "text": by_id[d]["text"]} for d in rl[:topn]],
                }
            )
    return out


def run_model(model_key, model_dir, ids, texts, alt_texts, querysets, by_id):
    emb = Embedder(Path(model_dir), "int8")
    mat_mono = emb.embed_passages(texts)
    mat_alt = emb.embed_passages(alt_texts)

    fts_mono = FtsIndex(ids, texts)
    bi_texts_for_fts = [t + " " + a for t, a in zip(texts, alt_texts)]
    fts_bi = FtsIndex(ids, bi_texts_for_fts)

    results = {}
    failures = {}

    for entry_mode in ("mono", "bi"):
        fts_idx = fts_mono if entry_mode == "mono" else fts_bi
        for qset_name, queries in querysets.items():
            qtexts = [q["query"] for q in queries]
            qvecs = emb.embed_queries(qtexts)
            for search_mode in ("vec", "hyb1", "hyb05"):
                cfg = f"{model_key}_{entry_mode}_{search_mode}"
                ranked = []
                for j, qv in enumerate(qvecs):
                    if entry_mode == "mono":
                        sims = sims_mono(mat_mono, qv)
                    else:
                        sims = sims_bi(mat_mono, mat_alt, qv)
                    if search_mode == "vec":
                        top_idx = topk_from_sims(sims, FINAL_TOPN)
                        ranked.append([ids[i] for i in top_idx])
                    else:
                        vec_rank50 = [int(x) for x in topk_from_sims(sims, RRF_TOPN_SOURCE)]
                        fts_rank50 = fts_idx.topk(
                            qtexts[j], RRF_TOPN_SOURCE, query_builder=lambda t: fts_query_stopwords(t, STOPWORDS_ID_EN)
                        )
                        w_fts = 1.0 if search_mode == "hyb1" else 0.5
                        merged = rrf(
                            [fts_rank50, vec_rank50],
                            k=RRF_K,
                            top=FINAL_TOPN,
                            weights=[w_fts, 1.0],
                        )
                        ranked.append([ids[i] for i in merged])
                results.setdefault(cfg, {})[qset_name] = metrics(ranked, queries)
                failures.setdefault(cfg, {})[qset_name] = failures_for(cfg, ranked, queries, by_id)
                print(f"{cfg} [{qset_name}] total:", results[cfg][qset_name]["total"])
    del emb
    return results, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-s", required=True, help="Dir with multilingual-e5-small ONNX files")
    ap.add_argument("--models-b", required=True, help="Dir with multilingual-e5-base ONNX files")
    ap.add_argument("--out", default=str(HERE.parent.parent / "results" / "uji06b-raw"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ids, texts, alt_texts, querysets = load_dataset()
    corpus = json.loads((HERE / "dataset" / "corpus.json").read_text(encoding="utf8"))
    by_id = {e["id"]: e for e in corpus}

    all_results = {}
    all_failures = {}
    t0 = time.perf_counter()
    for model_key, model_dir in (("S", args.models_s), ("B", args.models_b)):
        r, f = run_model(model_key, model_dir, ids, texts, alt_texts, querysets, by_id)
        for cfg, qd in r.items():
            all_results.setdefault(cfg, {}).update(qd)
        for cfg, qd in f.items():
            all_failures.setdefault(cfg, {}).update(qd)
    total_s = time.perf_counter() - t0
    merged_results = all_results

    (out / "quality_metrics_v2.json").write_text(
        json.dumps(merged_results, indent=2, ensure_ascii=False), encoding="utf8"
    )
    (out / "failures_v2_by_config.json").write_text(
        json.dumps(all_failures, ensure_ascii=False, indent=2), encoding="utf8"
    )
    (out / "stopwords.json").write_text(
        json.dumps(sorted(STOPWORDS_ID_EN), ensure_ascii=False, indent=2), encoding="utf8"
    )

    summary = {
        cfg: {qs: merged_results[cfg][qs]["total"] for qs in merged_results[cfg]}
        for cfg in merged_results
    }
    print(json.dumps(summary, indent=2))
    print(f"total eval time: {total_s:.1f}s")


if __name__ == "__main__":
    main()
