"""Dataset statistics for queries_v2.json (Uji #6b Tahap 1, brief section 9.3).

Extends dataset_stats.py's tokenizer/stopword convention. Reports, for v2:
- distribution by query type
- distribution of word-similarity level between each query and its
  relevant entries (0% / semantic, 1-25%, 26-50%, >50% -- the last bucket
  must be empty per brief section 3)
- number of multi-label queries (relevant_ids with more than one entry)

Standard library only.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# Same stopword list as dataset_stats.py, kept identical for comparability.
STOP = set("""
yang dan di ke dari untuk dengan pada ini itu atau juga akan sudah belum tidak bukan ada adalah
apa siapa kapan mana berapa bagaimana kenapa mengapa saya aku dia kami kita mereka nya sih ya yak
the and for are was were with that this what when where which who how does did his her its their
from into has have had not but you your user users dimas sari aira
dgn utk yg gw gue lu lo ga gak tdk dmn brp kpn gmn
""".split())


def tokens(text: str):
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOP}


def overlap_bucket(frac: float, any_shared: bool) -> str:
    if not any_shared:
        return "0% (semantik)"
    if frac <= 0.25:
        return "1-25%"
    if frac <= 0.50:
        return "26-50%"
    return ">50%"


def main(ds_dir: Path):
    corpus = json.loads((ds_dir / "corpus.json").read_text(encoding="utf8"))
    queries = json.loads((ds_dir / "queries_v2.json").read_text(encoding="utf8"))
    by_id = {e["id"]: e for e in corpus}

    per_type_total = Counter()
    bucket_counts = Counter()
    bucket_by_type = {}
    multi_label = 0
    multi_label_by_type = Counter()
    over50_examples = []

    for q in queries:
        per_type_total[q["type"]] += 1
        if len(q["relevant_ids"]) > 1:
            multi_label += 1
            multi_label_by_type[q["type"]] += 1

        qt = tokens(q["query"])
        any_shared = False
        max_frac = 0.0
        for r in q["relevant_ids"]:
            et = tokens(by_id[r]["text"])
            shared = qt & et
            if shared:
                any_shared = True
            frac = len(shared) / len(et) if et else 0.0
            max_frac = max(max_frac, frac)

        bucket = overlap_bucket(max_frac, any_shared)
        bucket_counts[bucket] += 1
        bucket_by_type.setdefault(q["type"], Counter())[bucket] += 1
        if bucket == ">50%":
            over50_examples.append((q["id"], q["query"], q["relevant_ids"], round(max_frac, 2)))

    total = len(queries)
    semantic = bucket_counts.get("0% (semantik)", 0)

    stats = {
        "queries": total,
        "queries_by_type": dict(per_type_total),
        "similarity_buckets": dict(bucket_counts),
        "similarity_buckets_by_type": {t: dict(c) for t, c in bucket_by_type.items()},
        "semantic_queries": semantic,
        "semantic_pct": round(100 * semantic / total, 1) if total else 0,
        "over_50pct_queries": len(over50_examples),
        "over_50pct_examples": over50_examples,
        "multi_label_queries": multi_label,
        "multi_label_pct": round(100 * multi_label / total, 1) if total else 0,
        "multi_label_by_type": dict(multi_label_by_type),
    }
    return stats


if __name__ == "__main__":
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    print(json.dumps(main(d), ensure_ascii=False, indent=2))
