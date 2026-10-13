"""Shared BAAI/bge-small-en-v1.5 embedder (lazy-loaded once per process)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from t2s.config import EMBED_MODEL

# bge v1.5 recommends this prefix for short queries that retrieve longer passages.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def _model():
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return SentenceTransformer(EMBED_MODEL, device=device)


def embed(texts: list[str], batch_size: int = 128) -> np.ndarray:
    """L2-normalised float32 embeddings, so a dot product is cosine similarity."""
    vecs = _model().encode(
        texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
    )
    return np.asarray(vecs, dtype=np.float32)
