"""Few-shot retrieval: nearest Spider-train questions from *other* databases."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from t2s.config import CACHE_DIR, EMBED_MODEL, SPIDER_DIR
from t2s.embed import embed


@lru_cache(maxsize=1)
def _train_index() -> tuple[list[dict], np.ndarray]:
    train = []
    for name in ("train_spider.json", "train_others.json"):
        train += json.loads((SPIDER_DIR / name).read_text(encoding="utf-8"))
    pairs = [{"db_id": t["db_id"], "question": t["question"], "sql": t["query"]} for t in train]
    cache = CACHE_DIR / f"train_q_{EMBED_MODEL.replace('/', '_')}_{len(pairs)}.npy"
    if cache.exists():
        mat = np.load(cache)
    else:
        mat = embed([p["question"] for p in pairs])
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(cache, mat)
    return pairs, mat


def retrieve(question: str, db_id: str, n: int = 3) -> list[dict]:
    """Top-n (question, SQL) pairs by cosine similarity, excluding `db_id` to avoid leakage."""
    if n <= 0:
        return []
    pairs, mat = _train_index()
    sims = mat @ embed([question])[0]
    out = []
    for i in np.argsort(-sims):
        if pairs[i]["db_id"] != db_id:
            out.append({**pairs[i], "score": float(sims[i])})
            if len(out) == n:
                break
    return out
