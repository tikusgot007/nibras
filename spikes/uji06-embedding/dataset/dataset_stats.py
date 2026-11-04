"""Dataset statistics, including the anti-leak percentage (brief section 6).

A query is "anti-leak" when it shares NO content word with any of its relevant
entries. Content word = lowercase alphanumeric token of length >= 3 that is not
in the stopword list below. Standard library only.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

STOP = set("""
yang dan di ke dari untuk dengan pada ini itu atau juga akan sudah belum tidak bukan ada adalah
apa siapa kapan mana berapa bagaimana kenapa mengapa saya aku dia kami kita mereka nya sih ya yak
the and for are was were with that this what when where which who how does did his her its their
from into has have had not but you your user users dimas sari aira
dgn utk yg gw gue lu lo ga gak tdk dmn brp kpn gmn
""".split())


def tokens(text: str):
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOP}


def main(ds_dir: Path):
    corpus = json.loads((ds_dir / "corpus.json").read_text(encoding="utf8"))
    queries = json.loads((ds_dir / "queries.json").read_text(encoding="utf8"))
    by_id = {e["id"]: e for e in corpus}
    anti = 0
    per_type = Counter()
    per_type_total = Counter()
    for q in queries:
        qt = tokens(q["query"])
        shared = set()
        for r in q["relevant_ids"]:
            shared |= qt & tokens(by_id[r]["text"])
        per_type_total[q["type"]] += 1
        if not shared:
            anti += 1
            per_type[q["type"]] += 1
    groups = Counter(e["id"][:3] for e in corpus if re.fullmatch(r"g\d\d[a-z]", e["id"]))
    stats = {
        "entries": len(corpus),
        "entries_by_lang": dict(Counter(e["lang"] for e in corpus)),
        "entries_by_category": dict(Counter(e["category"] for e in corpus)),
        "hard_negative_groups": len(groups),
        "queries": len(queries),
        "queries_by_type": dict(per_type_total),
        "anti_leak_queries": anti,
        "anti_leak_pct": round(100 * anti / len(queries), 1),
        "anti_leak_by_type": {t: f"{per_type[t]}/{per_type_total[t]}" for t in per_type_total},
    }
    return stats


if __name__ == "__main__":
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    print(json.dumps(main(d), ensure_ascii=False, indent=2))
