"""Prompt construction, the Ollama /api/chat client and SQL extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from t2s.config import LLM_OPTIONS, LLM_TIMEOUT_S, MODEL, OLLAMA_URL

SYSTEM = (
    "You are an expert SQLite developer. Given a database schema and a question, write ONE "
    "SQLite SELECT query that answers the question. Use only tables and columns that exist in "
    "the schema. Select only the columns the question asks for. Return the query in a single "
    "```sql fenced block with no explanation."
)


class LLMUnavailable(RuntimeError):
    """The model server could not be reached."""


@dataclass
class LLMReply:
    text: str
    tokens_in: int
    tokens_out: int


class ChatModel(Protocol):
    def chat(self, messages: list[dict], **options) -> LLMReply: ...


class OllamaChat:
    def __init__(self, model: str = MODEL, url: str = OLLAMA_URL, options: dict | None = None):
        self.model, self.url = model, url.rstrip("/")
        self.options = options or LLM_OPTIONS
        self._client = httpx.Client(timeout=LLM_TIMEOUT_S)

    def chat(self, messages: list[dict], **options) -> LLMReply:
        """`options` override the defaults for this call (e.g. temperature on retries)."""
        opts = {**self.options, **options}
        payload = {"model": self.model, "messages": messages, "stream": False, "options": opts}
        try:
            r = self._client.post(f"{self.url}/api/chat", json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise LLMUnavailable(f"Ollama not reachable at {self.url}: {exc}") from exc
        if r.status_code >= 500 or r.status_code == 404:
            raise LLMUnavailable(f"Ollama error {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        d = r.json()
        return LLMReply(d["message"]["content"], d.get("prompt_eval_count", 0), d.get("eval_count", 0))

    def healthy(self) -> bool:
        try:
            return self._client.get(f"{self.url}/api/tags", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False


def build_messages(question: str, schema_text: str, shots: list[dict]) -> list[dict]:
    parts = [f"### SQLite schema\n{schema_text}"]
    if shots:
        ex = "\n\n".join(f"Question: {s['question']}\n```sql\n{s['sql']}\n```" for s in shots)
        parts.append(f"### Examples from other databases (for SQL style only)\n{ex}")
    parts.append(f"### Question\n{question}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def feedback_message(error: str, sql: str, hint: str = "") -> dict:
    """Execution feedback for the next attempt: the failed SQL, the error and a grounding hint."""
    if "0 rows" in error:
        hint = hint or (
            "If the question filters on a value, check the sample values in the schema for the "
            "exact spelling and case, and check that the join path is correct."
        )
    return {
        "role": "user",
        "content": (
            f"Failed SQL:\n```sql\n{sql}\n```\nProblem: {error}\n{hint}\n"
            "Do not repeat the failed query. Re-read the schema and return a corrected SQLite "
            "query in a ```sql block."
        ),
    }


_FENCE = re.compile(r"```(?:sql|sqlite)?\s*\n?(.*?)```", re.S | re.I)
_START = re.compile(r"\b(WITH|SELECT)\b", re.I)


def extract_sql(text: str) -> str:
    """First fenced block; else everything from the first SELECT/WITH. Trailing ';' dropped."""
    m = _FENCE.search(text)
    if m:
        sql = m.group(1)
    else:
        s = _START.search(text)
        sql = text[s.start():] if s else text
    return sql.strip().rstrip(";").strip()
