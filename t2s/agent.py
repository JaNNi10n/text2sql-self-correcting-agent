"""The generate -> guard -> execute -> (feedback, retry) loop."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from t2s import fewshot, linker
from t2s.config import ARMS, ArmConfig
from t2s.generate import ChatModel, OllamaChat, build_messages, extract_sql, feedback_message
from t2s.guard import GuardError, execute
from t2s.schema import introspect, render

RETRY_TEMPERATURE = 0.7


def error_hint(err: str, tables, keep: set[str] | None) -> str:
    """Ground the model after schema errors by listing what actually exists.

    Table hints list *every* table in the DB, so a retry can recover a table that schema
    linking pruned; column hints list the columns of the tables shown in the prompt.
    """
    low = err.lower()
    if "no such table" in low:
        return "Valid table names are: " + ", ".join(t.name for t in tables) + "."
    if "no such column" in low or "ambiguous column" in low:
        shown = [t for t in tables if keep is None or t.name.lower() in keep]
        cols = "; ".join(f"{t.name}({', '.join(c.name for c in t.columns)})" for t in shown)
        return f"Valid columns are: {cols}. Qualify columns with their table name or alias."
    return ""


def run_agent(
    question: str,
    db: str | Path,
    cfg: ArmConfig = ARMS["A3"],
    llm: ChatModel | None = None,
    db_id: str | None = None,
) -> dict:
    """Answer `question` on SQLite file `db`.

    Returns {sql, rows, columns, attempts, error_trace, tokens_in, tokens_out, latency_ms,
    attempt_sqls, linked_tables, shots, status} where status is ok | empty | error | guard.
    """
    t0 = time.perf_counter()
    db = str(db)
    db_id = db_id or Path(db).stem
    llm = llm or OllamaChat(cfg.model)
    tables = introspect(db)
    keep = None
    if cfg.link_schema:
        keep = linker.link(question, db, k=cfg.top_k_tables).tables
    shots = fewshot.retrieve(question, db_id, cfg.shots)
    schema_text = render(tables, keep)
    messages = build_messages(question, schema_text, shots)

    trace: list[dict] = []
    sqls: list[str] = []
    tok_in = tok_out = 0
    sql, rows, cols, status = "", [], [], "error"
    executed_empty: str | None = None  # last SQL that ran cleanly but returned 0 rows
    for attempt in range(1, cfg.max_retries + 2):
        # Attempt 1 is greedy (temperature 0). Retries sample at RETRY_TEMPERATURE with a
        # per-attempt seed: greedy decoding on an almost identical prompt tends to reproduce
        # the failed query verbatim, while a seeded sample stays reproducible.
        opts = {} if attempt == 1 else {"temperature": RETRY_TEMPERATURE, "seed": 42 + attempt}
        reply = llm.chat(messages, **opts)
        tok_in += reply.tokens_in
        tok_out += reply.tokens_out
        sql = extract_sql(reply.text)
        sqls.append(sql)
        try:
            res = execute(sql, db)
            rows, cols = res.rows, res.columns
            if rows:
                status = "ok"
                break
            status, err = "empty", "the query ran but returned 0 rows"
            executed_empty = sql
        except GuardError as exc:
            status, err, rows, cols = "guard", f"rejected by safety guard: {exc}", [], []
        except TimeoutError as exc:
            status, err, rows, cols = "error", str(exc), [], []
        except sqlite3.Error as exc:
            status, err, rows, cols = "error", f"SQLite error: {exc}", [], []
        trace.append({"attempt": attempt, "sql": sql, "error": err, "kind": status})
        if attempt <= cfg.max_retries:
            # Retry prompts drop the few-shot examples: they come from other databases, and a
            # small model that hallucinated an identifier usually copied it from one of them.
            messages = build_messages(question, schema_text, []) + [
                {"role": "assistant", "content": reply.text},
                feedback_message(err, sql, error_hint(err, tables, keep)),
            ]
    if status in ("error", "guard") and executed_empty is not None:
        # a retry made things worse: fall back to the last query that at least executed
        sql, rows, cols, status = executed_empty, [], [], "empty"
    return {
        "sql": sql,
        "rows": rows,
        "columns": cols,
        "status": status,
        "attempts": len(sqls),
        "attempt_sqls": sqls,
        "error_trace": trace,
        "tokens_in": tok_in,
        "tokens_out": tok_out,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "linked_tables": sorted(keep) if keep is not None else None,
        "shots": [s["question"] for s in shots],
    }
