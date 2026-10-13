"""Schema-linking recall on 10 hand-written questions over a 10-table fixture database.

Downloads BAAI/bge-small-en-v1.5 (~130 MB) from Hugging Face on first run.
"""

import pytest

from t2s import linker
from t2s.schema import introspect

CASES = [
    ("Which teachers work in the Physics department?", {"teachers", "departments"}),
    ("How many students are enrolled in Quantum Mechanics?", {"students", "enrollments", "courses"}),
    ("List the titles of books written by Indian authors.", {"books", "authors"}),
    ("Which books have not been returned yet?", {"books", "loans"}),
    ("What was the maximum temperature on 2024-01-02?", {"weather"}),
    ("Show vegetarian dishes cheaper than 150.", {"cafeteria_menu"}),
    ("What is the average salary of teachers?", {"teachers"}),
    ("Which students live in Pune?", {"students"}),
    ("Who teaches the course Medieval Europe?", {"courses", "teachers"}),
    ("What grade did Meera get in each course?", {"students", "enrollments", "courses"}),
]


@pytest.fixture(scope="module")
def linked(school_db):
    return [linker.link(q, school_db, k=4) for q, _ in CASES]


def test_linker_recall_at_least_0_9(school_db, linked):
    recalls = [linker.recall(r.tables, gold) for r, (_, gold) in zip(linked, CASES)]
    mean = sum(recalls) / len(recalls)
    print(f"linker mean table recall on fixtures: {mean:.3f}")
    assert mean >= 0.9


def test_linker_actually_prunes(school_db, linked):
    n_tables = len(introspect(school_db))
    assert any(len(r.tables) < n_tables for r in linked)


def test_fk_expansion(school_db):
    adj = linker.fk_neighbours(introspect(school_db))
    assert {"students", "courses"} <= adj["enrollments"]
    assert "departments" in adj["teachers"]


def test_gold_tables_resolves_aliases():
    sql = "SELECT T1.title FROM courses AS T1 JOIN teachers AS T2 ON T1.teacher_id = T2.teacher_id"
    assert linker.gold_tables(sql, {"courses", "teachers", "students"}) == {"courses", "teachers"}
