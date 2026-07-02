from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BASE_DIR / "sqlite_lab.db"

SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    email TEXT UNIQUE NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    term TEXT NOT NULL,
    grade REAL CHECK (grade >= 0 AND grade <= 100),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (student_id, course_id, term)
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, score, email, active) VALUES
    ('An Nguyen', 'A1', 91.5, 'an.nguyen@example.edu', 1),
    ('Binh Tran', 'A1', 84.0, 'binh.tran@example.edu', 1),
    ('Chi Pham', 'B2', 77.5, 'chi.pham@example.edu', 1),
    ('Dung Le', 'B2', 88.0, 'dung.le@example.edu', 0),
    ('Em Vo', 'C3', 95.0, 'em.vo@example.edu', 1);

INSERT INTO courses (code, title, credits) VALUES
    ('MCP101', 'Model Context Protocol Basics', 3),
    ('SQL201', 'Applied SQL Safety', 4),
    ('AI301', 'Agent Tooling Studio', 3);

INSERT INTO enrollments (student_id, course_id, term, grade) VALUES
    (1, 1, '2026-S1', 93.0),
    (1, 2, '2026-S1', 89.5),
    (2, 1, '2026-S1', 85.0),
    (3, 2, '2026-S1', 78.0),
    (4, 3, '2026-S1', 88.5),
    (5, 1, '2026-S1', 96.0),
    (5, 3, '2026-S1', 94.5);
"""


def create_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Path:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        connection.executescript(SEED_SQL)
        connection.commit()
    return path


if __name__ == "__main__":
    print(create_database())
