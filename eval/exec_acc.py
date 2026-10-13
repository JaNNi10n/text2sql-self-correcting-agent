"""Execution accuracy (EX): do the gold and predicted SQL return the same result?

Results are compared as multisets of rows (collections.Counter), or as ordered lists when
the gold SQL contains ORDER BY. Floats are rounded to 6 decimals so 1e-7 noise from
different-but-equivalent arithmetic does not count as a mismatch. Column order inside a row
is significant (stricter than the official test-suite, which also tries column permutations).
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path

from t2s.guard import GuardError, execute

ORDER_BY = re.compile(r"\border\s+by\b", re.I)
GOLD_TIMEOUT_S = 30.0
PRED_TIMEOUT_S = 10.0
EVAL_MAX_ROWS = 100_000


def _norm(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def normalize(rows: list[tuple]) -> list[tuple]:
    return [tuple(_norm(v) for v in r) for r in rows]


def results_match(gold: list[tuple], pred: list[tuple], ordered: bool) -> bool:
    g, p = normalize(gold), normalize(pred)
    if ordered:
        return g == p
    return Counter(g) == Counter(p)


def run_gold(sql: str, db: str | Path) -> list[tuple]:
    return execute(sql, db, timeout_s=GOLD_TIMEOUT_S, max_rows=EVAL_MAX_ROWS, guard=False).rows


def exec_match(gold_sql: str, pred_sql: str, db: str | Path, gold_rows: list[tuple] | None = None) -> dict:
    """{'correct': bool, 'pred_error': str | None}. `gold_rows` may be passed to avoid re-running."""
    if gold_rows is None:
        gold_rows = run_gold(gold_sql, db)
    try:
        pred_rows = execute(pred_sql, db, timeout_s=PRED_TIMEOUT_S, max_rows=EVAL_MAX_ROWS).rows
    except (GuardError, TimeoutError, sqlite3.Error) as exc:
        return {"correct": False, "pred_error": f"{type(exc).__name__}: {exc}"}
    ordered = bool(ORDER_BY.search(gold_sql))
    return {"correct": results_match(gold_rows, pred_rows, ordered), "pred_error": None}
