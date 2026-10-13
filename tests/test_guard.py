import sqlite3
import time

import pytest

from t2s.guard import GuardError, check, execute
from t2s.schema import connect_ro


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE x",
        "SELECT 1; DELETE FROM t",
        "ATTACH DATABASE 'evil.db' AS evil",
        "PRAGMA writable_schema = ON",
        "PRAGMA journal_mode = DELETE",
        "INSERT INTO students VALUES (9, 'x', 1, 'y')",
        "UPDATE students SET age = 0",
        "WITH t AS (SELECT 1) DELETE FROM students",
        "CREATE TABLE z (a INT)",
        "ALTER TABLE students ADD COLUMN pwned TEXT",
        "SELECT load_extension('evil')",
        "SELECT 1; SELECT 2",
        "",
    ],
)
def test_guard_rejects(sql):
    with pytest.raises(GuardError):
        check(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "WITH older AS (SELECT * FROM students WHERE age > 19) SELECT count(*) FROM older",
        "SELECT student_name FROM students UNION SELECT teacher_name FROM teachers",
        "SELECT 'drop table students' AS harmless_text",
        "SELECT student_name FROM students WHERE home_city = 'Pune';",
    ],
)
def test_guard_accepts_read_only(sql):
    check(sql)


def test_cte_select_executes(school_db):
    res = execute(
        "WITH pune AS (SELECT * FROM students WHERE home_city = 'Pune') "
        "SELECT student_name FROM pune ORDER BY student_name",
        school_db,
    )
    assert res.rows == [("Arjun",), ("Ravi",)]


def test_write_through_read_only_connection_raises(school_db):
    conn = connect_ro(school_db)  # raw connection: no guard, no authorizer
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM students")
    conn.close()
    # executor with the static guard switched off still cannot write (authorizer + ro URI)
    with pytest.raises(sqlite3.Error):
        execute("DELETE FROM students", school_db, guard=False)
    rows = execute("SELECT count(*) FROM students", school_db).rows
    assert rows == [(3,)]


def test_timeout_aborts_infinite_recursive_cte(school_db):
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c"
    start = time.perf_counter()
    with pytest.raises(TimeoutError):
        execute(sql, school_db, timeout_s=2.0)
    assert time.perf_counter() - start < 3.0


def test_row_cap(school_db):
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 5000) SELECT x FROM c"
    res = execute(sql, school_db)
    assert len(res.rows) == 1000 and res.truncated
