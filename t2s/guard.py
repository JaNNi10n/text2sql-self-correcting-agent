"""SQL safety guard and sandboxed read-only executor.

Defence in depth, each layer independent of the others:
1. Static check (sqlglot): exactly one statement, a SELECT / WITH ... SELECT / set operation
   of SELECTs, with no DML/DDL/PRAGMA/ATTACH anywhere in the tree or token stream.
2. Connection: `file:...?mode=ro` URI + `PRAGMA query_only=ON`.
3. sqlite3 authorizer: denies every action except reads/selects/functions/recursive CTEs.
4. Progress handler aborts statements running past the time budget; results capped.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.tokens import TokenType

from t2s.config import EXEC_TIMEOUT_S, MAX_ROWS
from t2s.schema import connect_ro

FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,  # PRAGMA, ATTACH, DETACH, VACUUM... parse as generic commands
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Merge,
    exp.TruncateTable,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Use,
    exp.Set,
)
FORBIDDEN_WORDS = {
    "ATTACH", "DETACH", "PRAGMA", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "VACUUM", "REINDEX", "TRUNCATE", "COMMIT", "ROLLBACK", "SAVEPOINT",
}
# Functions that can touch the filesystem / load code in some SQLite builds.
FORBIDDEN_FUNCS = {"load_extension", "writefile", "readfile", "edit", "fts3_tokenizer"}

ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


class GuardError(ValueError):
    """Raised when a statement is rejected before execution."""


@dataclass
class ExecResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_ms: float
    denied_actions: list[int] = field(default_factory=list)


def check(sql: str) -> exp.Expression:
    """Return the parsed statement if it is a single read-only query, else raise GuardError."""
    if not sql or not sql.strip():
        raise GuardError("empty SQL")
    try:
        tokens = sqlglot.tokenize(sql, read="sqlite")
    except Exception as exc:  # tokenizer errors on unbalanced quotes etc.
        raise GuardError(f"could not tokenize SQL: {exc}") from exc
    for tok in tokens:
        if tok.token_type in (TokenType.STRING, TokenType.IDENTIFIER):
            continue  # words inside string literals / quoted identifiers are data
        if tok.text.upper() in FORBIDDEN_WORDS:
            raise GuardError(f"forbidden keyword: {tok.text.upper()}")
    try:
        stmts = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except sqlglot.errors.SqlglotError as exc:
        raise GuardError(f"could not parse SQL: {str(exc).splitlines()[0]}") from exc
    if len(stmts) != 1:
        raise GuardError(f"expected exactly one statement, got {len(stmts)}")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        raise GuardError(f"only SELECT/WITH queries are allowed, got {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise GuardError(f"forbidden statement type inside query: {node.key.upper()}")
        if isinstance(node, (exp.Anonymous, exp.Func)):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in FORBIDDEN_FUNCS:
                raise GuardError(f"forbidden function: {name}")
    return tree


def execute(
    sql: str,
    db: str | Path,
    timeout_s: float = EXEC_TIMEOUT_S,
    max_rows: int = MAX_ROWS,
    guard: bool = True,
) -> ExecResult:
    """Run `sql` on a read-only connection with a wall-clock budget and a row cap.

    Raises GuardError (rejected), TimeoutError (budget exceeded) or sqlite3.Error.
    `guard=False` is only used by the evaluator for trusted gold SQL.
    """
    if guard:
        check(sql)
    conn = connect_ro(db)
    denied: list[int] = []

    def authorizer(action, *_):
        if action in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        denied.append(action)
        return sqlite3.SQLITE_DENY

    deadline = time.perf_counter() + timeout_s
    conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 1000)
    conn.set_authorizer(authorizer)
    start = time.perf_counter()
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(max_rows + 1)
        cols = [d[0] for d in (cur.description or [])]
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise TimeoutError(f"query exceeded {timeout_s:.1f}s time limit") from exc
        raise
    finally:
        conn.close()
    return ExecResult(
        columns=cols,
        rows=[tuple(r) for r in rows[:max_rows]],
        truncated=len(rows) > max_rows,
        elapsed_ms=(time.perf_counter() - start) * 1000,
        denied_actions=denied,
    )
