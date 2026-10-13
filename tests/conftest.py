"""Shared fixtures: a small 10-table SQLite database and a scripted (mock) LLM."""

from __future__ import annotations

import sqlite3

import pytest

from t2s.generate import LLMReply

SCHEMA = """
CREATE TABLE departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT, building TEXT);
CREATE TABLE teachers (teacher_id INTEGER PRIMARY KEY, teacher_name TEXT, salary REAL,
    dept_id INTEGER REFERENCES departments(dept_id));
CREATE TABLE courses (course_id INTEGER PRIMARY KEY, title TEXT, credits INTEGER,
    teacher_id INTEGER REFERENCES teachers(teacher_id));
CREATE TABLE students (student_id INTEGER PRIMARY KEY, student_name TEXT, age INTEGER,
    home_city TEXT);
CREATE TABLE enrollments (student_id INTEGER REFERENCES students(student_id),
    course_id INTEGER REFERENCES courses(course_id), grade TEXT,
    PRIMARY KEY (student_id, course_id));
CREATE TABLE authors (author_id INTEGER PRIMARY KEY, author_name TEXT, nationality TEXT);
CREATE TABLE books (book_id INTEGER PRIMARY KEY, book_title TEXT, publish_year INTEGER,
    author_id INTEGER REFERENCES authors(author_id));
CREATE TABLE loans (loan_id INTEGER PRIMARY KEY, book_id INTEGER REFERENCES books(book_id),
    loan_date TEXT, return_date TEXT);
CREATE TABLE weather (day TEXT PRIMARY KEY, max_temperature REAL, rainfall_mm REAL);
CREATE TABLE cafeteria_menu (dish_id INTEGER PRIMARY KEY, dish_name TEXT, price REAL,
    is_vegetarian INTEGER);
INSERT INTO departments VALUES (1,'Physics','North Hall'),(2,'History','South Hall');
INSERT INTO teachers VALUES (1,'Ada Lovelace',90000,1),(2,'Marc Bloch',70000,2);
INSERT INTO courses VALUES (1,'Quantum Mechanics',4,1),(2,'Medieval Europe',3,2);
INSERT INTO students VALUES (1,'Ravi',20,'Pune'),(2,'Meera',22,'Delhi'),(3,'Arjun',19,'Pune');
INSERT INTO enrollments VALUES (1,1,'A'),(2,1,'B'),(2,2,'A');
INSERT INTO authors VALUES (1,'R. K. Narayan','Indian'),(2,'Jane Austen','British');
INSERT INTO books VALUES (1,'Malgudi Days',1943,1),(2,'Emma',1815,2);
INSERT INTO loans VALUES (1,1,'2024-01-02','2024-01-20'),(2,2,'2024-02-01',NULL);
INSERT INTO weather VALUES ('2024-01-01',31.5,0.0),('2024-01-02',29.0,12.5);
INSERT INTO cafeteria_menu VALUES (1,'Paneer Tikka',120,1),(2,'Chicken Biryani',180,0);
"""


@pytest.fixture(scope="session")
def school_db(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("db") / "school.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return str(path)


class ScriptedLLM:
    """Returns canned replies in order (repeating the last one) and records every call."""

    def __init__(self, replies: list[str]):
        self.replies = replies
        self.calls: list[dict] = []

    def chat(self, messages, **options):
        self.calls.append({"messages": messages, "options": options})
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return LLMReply(text, tokens_in=100, tokens_out=20)


@pytest.fixture
def scripted_llm():
    return ScriptedLLM
