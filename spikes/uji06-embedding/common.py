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

    def topk(self, query, k):
        rows = self.db.execute(
            "SELECT rowid FROM m WHERE m MATCH ? ORDER BY bm25(m) LIMIT ?",
            (fts_query(query), k),
        ).fetchall()
        return [r[0] for r in rows]


def rrf(rank_lists, k=60, top=10):
    scores = {}
    for lst in rank_lists:
        for rank, doc in enumerate(lst, 1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return [d for d, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:top]]
