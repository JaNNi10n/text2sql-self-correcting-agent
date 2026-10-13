"""Central settings: paths, model options and the four ablation arms."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPIDER_DIR = Path(os.environ.get("T2S_SPIDER_DIR", ROOT / "spider"))
DB_DIR = SPIDER_DIR / "database"
CACHE_DIR = ROOT / ".cache"
RESULTS_DIR = ROOT / "results"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("T2S_MODEL", "qwen2.5-coder:1.5b")
LLM_OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 512}
LLM_TIMEOUT_S = 120.0

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EXEC_TIMEOUT_S = 2.0
MAX_ROWS = 1000


@dataclass(frozen=True)
class ArmConfig:
    name: str
    link_schema: bool
    shots: int
    max_retries: int
    model: str = MODEL
    top_k_tables: int = 4


ARMS = {
    "A0": ArmConfig("A0", link_schema=False, shots=0, max_retries=0),
    "A1": ArmConfig("A1", link_schema=True, shots=0, max_retries=0),
    "A2": ArmConfig("A2", link_schema=True, shots=3, max_retries=0),
    "A3": ArmConfig("A3", link_schema=True, shots=3, max_retries=2),
    # exploratory extra arm added after A0-A3 were run: A1 + self-correction, no few-shot
    "A1R": ArmConfig("A1R", link_schema=True, shots=0, max_retries=2),
    # optional larger-model arm (Qwen Research licence, non-commercial)
    "A3-3b": ArmConfig("A3-3b", link_schema=True, shots=3, max_retries=2, model="qwen2.5-coder:3b"),
    "A0-3b": ArmConfig("A0-3b", link_schema=False, shots=0, max_retries=0, model="qwen2.5-coder:3b"),
}


def db_path(db_id: str) -> Path:
    return DB_DIR / db_id / f"{db_id}.sqlite"
