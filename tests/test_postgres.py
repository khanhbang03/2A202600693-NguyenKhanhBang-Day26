from __future__ import annotations

import os

import pytest

from implementation.db import PostgresAdapter, ValidationError
from implementation.init_postgres import create_postgres_database
from implementation.mcp_server import build_adapter


def test_postgres_backend_requires_dsn():
    with pytest.raises(ValueError, match="requires"):
        build_adapter(backend="postgresql")


def test_postgres_adapter_uses_postgres_placeholders():
    adapter = PostgresAdapter("postgresql://user:pass@localhost/db")

    where_sql, params = adapter._build_where_clause(
        [
            {"column": "cohort", "op": "eq", "value": "A1"},
            {"column": "score", "op": "in", "value": [80, 90]},
        ],
        ["cohort", "score"],
    )

    assert where_sql == '"cohort" = %s AND "score" IN (%s, %s)'
    assert params == ["A1", 80, 90]


def test_postgres_adapter_rejects_bad_identifier():
    adapter = PostgresAdapter("postgresql://user:pass@localhost/db")

    with pytest.raises(ValidationError, match="invalid"):
        adapter._qualified_table("students;drop")


@pytest.mark.skipif(not os.environ.get("POSTGRES_TEST_DSN"), reason="set POSTGRES_TEST_DSN to run live PostgreSQL test")
def test_live_postgres_adapter_round_trip():
    dsn = os.environ["POSTGRES_TEST_DSN"]
    create_postgres_database(dsn)
    adapter = PostgresAdapter(dsn)

    search = adapter.search("students", filters={"cohort": "A1"}, order_by="score", descending=True)
    assert [row["name"] for row in search["rows"][:2]] == ["An Nguyen", "Binh Tran"]

    inserted = adapter.insert(
        "students",
        {"name": "Lan Ho", "cohort": "A1", "score": 82.0, "email": "lan.ho.pg@example.edu"},
    )
    assert inserted["row"]["name"] == "Lan Ho"

    aggregate = adapter.aggregate("students", "avg", column="score", group_by="cohort")
    assert any(row["cohort"] == "A1" for row in aggregate["rows"])
