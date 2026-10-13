"""Introspect a SQLite database and render it as CREATE TABLE text with sample values."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass
class Column:
    name: str
    type: str
    pk: bool
    samples: list[str] = field(default_factory=list)


@dataclass
class Table:
    name: str
    columns: list[Column]
    # (column, referenced_table, referenced_column)
    fks: list[tuple[str, str, str]] = field(default_factory=list)


def connect_ro(db: str | Path) -> sqlite3.Connection:
    """Read-only URI connection; tolerant of the odd non-UTF-8 bytes in Spider DBs."""
    uri = Path(db).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    conn.execute("PRAGMA query_only=ON")
    return conn


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _fmt(v) -> str:
    if isinstance(v, str):
        v = v if len(v) <= 30 else v[:27] + "..."
        return "'" + v.replace("'", "''") + "'"
    return str(v)


@lru_cache(maxsize=256)
def introspect(db: str, n_samples: int = 3) -> tuple[Table, ...]:
    conn = connect_ro(db)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY rowid"
            )
        ]
        tables = []
        for t in names:
            cols = []
            for _, cname, ctype, _, _, pk in conn.execute(f"PRAGMA table_info({_q(t)})"):
                try:
                    rows = conn.execute(
                        f"SELECT DISTINCT {_q(cname)} FROM {_q(t)} "
                        f"WHERE {_q(cname)} IS NOT NULL LIMIT {n_samples}"
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                cols.append(Column(cname, (ctype or "").upper(), bool(pk), [_fmt(r[0]) for r in rows]))
            fks = [
                (r[3], r[2], r[4] or "")
                for r in conn.execute(f"PRAGMA foreign_key_list({_q(t)})")
            ]
            tables.append(Table(t, cols, fks))
        return tuple(tables)
    finally:
        conn.close()


def render(tables: tuple[Table, ...] | list[Table], keep: set[str] | None = None) -> str:
    """CREATE TABLE statements (optionally only `keep` tables), samples as trailing comments."""
    out = []
    for t in tables:
        if keep is not None and t.name.lower() not in keep:
            continue
        pks = [c.name for c in t.columns if c.pk]
        defs: list[tuple[str, str]] = []  # (definition, comment)
        for c in t.columns:
            pk = " PRIMARY KEY" if c.pk and len(pks) == 1 else ""
            comment = f" -- e.g. {', '.join(c.samples)}" if c.samples else ""
            defs.append((f"{c.name} {c.type or 'TEXT'}{pk}", comment))
        if len(pks) > 1:
            defs.append((f"PRIMARY KEY ({', '.join(pks)})", ""))
        for col, rt, rc in t.fks:
            if keep is None or rt.lower() in keep:
                defs.append((f"FOREIGN KEY ({col}) REFERENCES {rt}({rc})", ""))
        body = [
            f"  {d}{',' if i < len(defs) - 1 else ''}{c}" for i, (d, c) in enumerate(defs)
        ]
        out.append(f"CREATE TABLE {t.name} (\n" + "\n".join(body) + "\n);")
    return "\n\n".join(out)
