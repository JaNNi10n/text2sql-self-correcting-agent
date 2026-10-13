"""Schema linking: keep the top-k most question-relevant tables plus their FK neighbours."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import sqlglot
from sqlglot import exp

from t2s.embed import QUERY_PREFIX, embed
from t2s.schema import Table, introspect


@dataclass
class LinkResult:
    tables: set[str]  # lower-cased names kept in the prompt
    ranked: list[tuple[str, float]]  # every table with its relevance score
    pruned: bool  # True when at least one table was dropped


def column_docs(tables: tuple[Table, ...]) -> list[tuple[str, str]]:
    """(table_lower, 'table.column: sample values') for every column."""
    docs = []
    for t in tables:
        for c in t.columns:
            vals = ", ".join(c.samples)
            docs.append((t.name.lower(), f"{t.name}.{c.name}: {vals}"))
    return docs


@lru_cache(maxsize=256)
def _db_index(db: str) -> tuple[tuple[Table, ...], list[str], np.ndarray]:
    tables = introspect(db)
    docs = column_docs(tables)
    return tables, [d[0] for d in docs], embed([d[1] for d in docs])


def fk_neighbours(tables: tuple[Table, ...]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {t.name.lower(): set() for t in tables}
    for t in tables:
        for _, ref, _ in t.fks:
            a, b = t.name.lower(), ref.lower()
            if b in adj:
                adj[a].add(b)
                adj[b].add(a)
    return adj


def link(question: str, db: str, k: int = 4) -> LinkResult:
    tables, owners, mat = _db_index(db)
    q = embed([QUERY_PREFIX + question])[0]
    sims = mat @ q
    best: dict[str, float] = {}
    for owner, s in zip(owners, sims):  # table score = its best-matching column
        best[owner] = max(best.get(owner, -1.0), float(s))
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    keep = {name for name, _ in ranked[:k]}
    adj = fk_neighbours(tables)
    for name in list(keep):
        keep |= adj.get(name, set())
    return LinkResult(keep, ranked, pruned=len(keep) < len(tables))


def gold_tables(sql: str, all_tables: set[str]) -> set[str]:
    """Lower-cased real table names referenced by a SQL string (aliases resolved by sqlglot)."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
        names = {t.name.lower() for t in tree.find_all(exp.Table)}
    except sqlglot.errors.ParseError:
        names = {tok.lower().strip('"`') for tok in sql.replace(",", " ").split()}
    return names & all_tables


def recall(linked: set[str], gold: set[str]) -> float:
    return 1.0 if not gold else len(linked & gold) / len(gold)
