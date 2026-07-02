from __future__ import annotations

import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path):
    db_path = create_database(tmp_path / "lab.db")
    return SQLiteAdapter(db_path)


def test_search_filters_ordering_and_pagination(adapter):
    result = adapter.search(
        "students",
        filters={"cohort": "A1"},
        columns=["name", "score"],
        order_by="score",
        descending=True,
        limit=1,
    )

    assert result["count"] == 1
    assert result["rows"][0]["name"] == "An Nguyen"


def test_insert_returns_inserted_row(adapter):
    result = adapter.insert(
        "students",
        {
            "name": "Lan Ho",
            "cohort": "A1",
            "score": 82.0,
            "email": "lan.ho@example.edu",
        },
    )

    assert result["inserted_id"]
    assert result["row"]["name"] == "Lan Ho"


def test_aggregate_avg_by_group(adapter):
    result = adapter.aggregate("students", "avg", column="score", group_by="cohort")

    rows = {row["cohort"]: row["value"] for row in result["rows"]}
    assert rows["A1"] == pytest.approx(87.75)


def test_schema_contains_tables(adapter):
    schema = adapter.get_database_schema()

    assert set(schema["tables"]) == {"courses", "enrollments", "students"}


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda a: a.search("missing"), "unknown table"),
        (lambda a: a.search("students", columns=["missing"]), "unknown column"),
        (lambda a: a.search("students", filters=[{"column": "score", "op": "between", "value": [80, 90]}]), "unsupported"),
        (lambda a: a.aggregate("students", "median", column="score"), "unsupported aggregate"),
        (lambda a: a.insert("students", {}), "non-empty"),
    ],
)
def test_invalid_requests_are_rejected(adapter, call, message):
    with pytest.raises(ValidationError, match=message):
        call(adapter)
