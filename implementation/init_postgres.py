from __future__ import annotations

import argparse
import os
import re

import psycopg


POSTGRES_SCHEMA_SQL = """
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 100),
    email TEXT UNIQUE NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    grade DOUBLE PRECISION CHECK (grade >= 0 AND grade <= 100),
    UNIQUE (student_id, course_id, term)
);
"""

POSTGRES_SEED_SQL = """
INSERT INTO students (name, cohort, score, email, active) VALUES
    ('An Nguyen', 'A1', 91.5, 'an.nguyen@example.edu', TRUE),
    ('Binh Tran', 'A1', 84.0, 'binh.tran@example.edu', TRUE),
    ('Chi Pham', 'B2', 77.5, 'chi.pham@example.edu', TRUE),
    ('Dung Le', 'B2', 88.0, 'dung.le@example.edu', FALSE),
    ('Em Vo', 'C3', 95.0, 'em.vo@example.edu', TRUE);

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


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def create_postgres_database(dsn: str, schema: str = "public") -> None:
    if not IDENTIFIER_RE.match(schema):
        raise ValueError(f"invalid PostgreSQL schema identifier '{schema}'")
    with psycopg.connect(dsn) as connection:
        connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        connection.execute(f'SET search_path TO "{schema}"')
        for statement in _sql_statements(POSTGRES_SCHEMA_SQL):
            connection.execute(statement)
        for statement in _sql_statements(POSTGRES_SEED_SQL):
            connection.execute(statement)
        connection.commit()


def _sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize the PostgreSQL lab schema and seed data.")
    parser.add_argument("--dsn", default=os.environ.get("POSTGRES_DSN"), required=os.environ.get("POSTGRES_DSN") is None)
    parser.add_argument("--schema", default=os.environ.get("POSTGRES_SCHEMA", "public"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    create_postgres_database(args.dsn, args.schema)
    print(f"initialized PostgreSQL schema '{args.schema}'")
