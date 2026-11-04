"""Shared helpers for Uji #6: e5 embedder (ONNX Runtime + tokenizers), FTS5, RRF.

No torch / transformers. Only onnxruntime, numpy, tokenizers, sqlite3 (stdlib).
"""
import re
import sqlite3
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
MAX_LEN = 512


class Embedder:
    def __init__(self, model_dir: Path, variant: str):
        t0 = time.perf_counter()
        self.tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_LEN)
        self.tok.enable_padding(pad_id=1, pad_token="<pad>")
        self.tokenizer_load_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        self.sess = ort.InferenceSession(
            str(model_dir / f"model_{variant}.onnx"), providers=["CPUExecutionProvider"]
        )
        self.model_load_s = time.perf_counter() - t1
        self.names = {i.name for i in self.sess.get_inputs()}

    def _embed(self, texts):
        enc = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = self.sess.run(None, feed)[0]
        m = mask[..., None].astype(np.float32)
        pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
        pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        return pooled.astype(np.float32)

    def embed_passages(self, texts, batch_size=32):
        out = []
        for i in range(0, len(texts), batch_size):
            out.append(self._embed([PASSAGE_PREFIX + t for t in texts[i : i + batch_size]]))
        return np.vstack(out)

    def embed_queries(self, texts, batch_size=32):
        out = []
        for i in range(0, len(texts), batch_size):
            out.append(self._embed([QUERY_PREFIX + t for t in texts[i : i + batch_size]]))
        return np.vstack(out)


def vector_topk(matrix, qvec, k):
    sims = matrix @ qvec
    k = min(k, len(sims))
    idx = np.argpartition(-sims, k - 1)[:k]
    return idx[np.argsort(-sims[idx])]


def fts_query(text: str) -> str:
    toks = re.findall(r"\w+", text, flags=re.UNICODE)
    if not toks:
        return '""'
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in toks)


# Stopword list for Uji #6b Hybrid FTS5 queries (brief section 4 "Aturan Hybrid
# baru"): removed from the FTS5 query side only, never from the indexed text.
# Fixed in code before any evaluation run; not tuned against results.
STOPWORDS_ID_EN = set("""
yang dan di ke dari untuk dengan pada ini itu atau juga akan sudah belum tidak
bukan ada adalah apa siapa kapan mana berapa bagaimana kenapa mengapa saya aku
dia kami kita mereka nya sih ya kah lah pun serta namun tetapi karena sebab
jika kalau agar supaya hingga sampai saat ketika sebelum sesudah setelah antara
sebagai oleh bagi tentang dalam luar atas bawah lebih kurang paling sangat
banget begitu gitu gini begini demikian tersebut berikut yaitu yakni
dgn utk yg gw gue lu lo ga gak ngga enggak tdk dmn brp kpn gmn knp napa
the a an and or but for nor so yet is are was were be been being am
to of in on at by with from into onto over under about above below
this that these those it its they them their he she his her him we us our
you your i my me do does did have has had not no can cannot could would
should will shall may might must there here then than when where which who
whom whose what why how all any both each few more most other some such
only own same so than too very just
""".split())


def fts_query_stopwords(text: str, stopwords: set) -> str:
    """Query-side builder for Uji #6b Hybrid: drop stopwords (ID+EN) before
    building the FTS5 MATCH expression. The indexed text itself is untouched."""
    toks = re.findall(r"\w+", text, flags=re.UNICODE)
    kept = [t for t in toks if t.lower() not in stopwords]
    if not kept:
        kept = toks  # every token was a stopword; fall back to the raw query
    if not kept:
        return '""'
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in kept)


class FtsIndex:
    def __init__(self, ids, texts):
        self.db = sqlite3.connect(":memory:")
        self.db.execute(
            "CREATE VIRTUAL TABLE m USING fts5(text, tokenize='unicode61 remove_diacritics 2')"
        )
        self.db.executemany(
            "INSERT INTO m(rowid, text) VALUES (?, ?)", [(i, t) for i, t in enumerate(texts)]
        )
        self.db.commit()
        self.ids = ids

    def topk(self, query, k, query_builder=fts_query):
        rows = self.db.execute(
            "SELECT rowid FROM m WHERE m MATCH ? ORDER BY bm25(m) LIMIT ?",
            (query_builder(query), k),
        ).fetchall()
        return [r[0] for r in rows]


def rrf(rank_lists, k=60, top=10, weights=None):
    if weights is None:
        weights = [1.0] * len(rank_lists)
    scores = {}
    for lst, w in zip(rank_lists, weights):
        for rank, doc in enumerate(lst, 1):
            scores[doc] = scores.get(doc, 0.0) + w / (k + rank)
    return [d for d, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top]]
