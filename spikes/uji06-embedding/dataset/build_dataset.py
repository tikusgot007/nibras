"""Build dataset/corpus.json and dataset/queries.json from the raw source lists.

One-off generator kept for provenance. Sources: groups.txt (hard-negative groups),
singles.txt (single entries), queries.txt.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
LANG = {"I": "id", "E": "en", "M": "mix"}
CAT = {
    "P": "User Preferences",
    "C": "Personal Context",
    "J": "Projects",
    "K": "Knowledge",
    "W": "Workflows",
    "S": "PC Information",
}

corpus = []
for fname in ("groups.txt", "singles.txt"):
    for line in (SRC / fname).read_text(encoding="utf8").splitlines():
        if not line.strip():
            continue
        eid, lang, cat, text = line.split("|", 3)
        corpus.append({"id": eid, "text": text, "lang": LANG[lang], "category": CAT[cat]})
ids = {e["id"] for e in corpus}
assert len(ids) == len(corpus), "duplicate ids"
by_id = {e["id"]: e for e in corpus}

queries = []
for n, line in enumerate((SRC / "queries.txt").read_text(encoding="utf8").splitlines(), 1):
    if not line.strip():
        continue
    typ, q, rel = line.split("|", 2)
    rels = rel.split(",")
    for r in rels:
        assert r in ids, f"unknown id {r} in {line}"
    queries.append({"id": f"q{n:03d}", "query": q, "type": typ, "relevant_ids": rels})

group_prefixes = Counter(e["id"][:3] for e in corpus if re.fullmatch(r"g\d\d[a-z]", e["id"]))
print("entries", len(corpus), Counter(e["lang"] for e in corpus), Counter(e["category"] for e in corpus))
print("hard-negative groups", len(group_prefixes), "sizes", Counter(group_prefixes.values()))
print("queries", len(queries), Counter(q["type"] for q in queries))
# language consistency of cross-lingual types
bad = []
for q in queries:
    langs = {by_id[r]["lang"] for r in q["relevant_ids"]}
    if q["type"] == "id-en" and langs != {"en"}:
        bad.append((q["id"], q["query"], langs))
    if q["type"] == "en-id" and langs != {"id"}:
        bad.append((q["id"], q["query"], langs))
    if q["type"] == "id-id" and langs != {"id"}:
        bad.append((q["id"], q["query"], langs))
    if q["type"] == "en-en" and langs != {"en"}:
        bad.append((q["id"], q["query"], langs))
print("type/lang mismatches", bad)

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf8")
(OUT / "queries.json").write_text(json.dumps(queries, ensure_ascii=False, indent=1), encoding="utf8")
