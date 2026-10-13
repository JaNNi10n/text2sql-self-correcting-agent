"""FastAPI service: POST /query {db_id, question} and GET /health.

Status codes: 404 unknown db_id (allowlist), 400 guard rejection, 503 Ollama unavailable.
The allowlist defaults to the 20 Spider dev databases; override with T2S_DB_ALLOWLIST
(comma-separated db ids).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from t2s.agent import run_agent
from t2s.config import ARMS, SPIDER_DIR, db_path
from t2s.generate import LLMUnavailable, OllamaChat

API_CONFIG = ARMS[os.environ.get("T2S_API_CONFIG", "A3")]

app = FastAPI(title="t2s: self-correcting text-to-SQL", version="1.0.0")


class QueryIn(BaseModel):
    db_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=1000)


@lru_cache(maxsize=1)
def allowlist() -> frozenset[str]:
    env = os.environ.get("T2S_DB_ALLOWLIST")
    if env:
        return frozenset(x.strip() for x in env.split(",") if x.strip())
    dev = json.loads((SPIDER_DIR / "dev.json").read_text(encoding="utf-8"))
    return frozenset(ex["db_id"] for ex in dev)


def get_llm() -> OllamaChat:
    return OllamaChat(API_CONFIG.model)


@app.get("/health")
def health() -> dict:
    if not get_llm().healthy():
        raise HTTPException(503, detail="Ollama is not reachable")
    return {"status": "ok", "ollama": "reachable", "model": API_CONFIG.model}


@app.post("/query")
def query(body: QueryIn) -> dict:
    # Allowlist check first: db_id never reaches the filesystem unless it is a known id.
    if body.db_id not in allowlist() or not db_path(body.db_id).is_file():
        raise HTTPException(404, detail=f"unknown db_id: {body.db_id}")
    try:
        res = run_agent(body.question, db_path(body.db_id), API_CONFIG, get_llm(), db_id=body.db_id)
    except LLMUnavailable as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    if res["status"] == "guard":
        raise HTTPException(
            400, detail={"reason": res["error_trace"][-1]["error"], "sql": res["sql"]}
        )
    res["rows"] = [
        [v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v for v in r]
        for r in res["rows"]
    ]
    return res
