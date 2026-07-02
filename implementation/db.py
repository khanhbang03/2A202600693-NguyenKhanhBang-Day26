from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - PostgreSQL support is optional at import time
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


class ValidationError(ValueError):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """SQLite-backed data access with validation before SQL construction."""

    SUPPORTED_OPERATORS = {
        "eq": "=",
        "=": "=",
        "ne": "!=",
        "!=": "!=",
        "lt": "<",
        "<": "<",
        "lte": "<=",
        "<=": "<=",
        "gt": ">",
        ">": ">",
        "gte": ">=",
        ">=": ">=",
        "like": "LIKE",
        "in": "IN",
    }
    AGGREGATES = {"count", "avg", "sum", "min", "max"}
    IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def list_tables(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self._validate_table(table)
        with self.connect() as connection:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            foreign_keys = connection.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
            indexes = connection.execute(f'PRAGMA index_list("{table}")').fetchall()

        return {
            "table": table,
            "columns": [
                {
                    "name": column["name"],
                    "type": column["type"],
                    "nullable": not bool(column["notnull"]),
                    "default": column["dflt_value"],
                    "primary_key": bool(column["pk"]),
                }
                for column in columns
            ],
            "foreign_keys": [
                {
                    "column": fk["from"],
                    "references_table": fk["table"],
                    "references_column": fk["to"],
                }
                for fk in foreign_keys
            ],
            "indexes": [
                {
                    "name": index["name"],
                    "unique": bool(index["unique"]),
                    "origin": index["origin"],
                }
                for index in indexes
            ],
        }

    def get_database_schema(self) -> dict[str, Any]:
        return {"tables": {table: self.get_table_schema(table) for table in self.list_tables()}}

    def search(
        self,
        table: str,
        filters: Any = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        selected_columns = self._validate_columns(columns or valid_columns, valid_columns)
        limit = self._validate_non_negative_int(limit, "limit", upper_bound=100)
        offset = self._validate_non_negative_int(offset, "offset")
        where_sql, params = self._build_where_clause(filters, valid_columns)

        sql = f"SELECT {', '.join(self._quote(column) for column in selected_columns)} FROM {self._quote(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if order_by is not None:
            self._validate_column(order_by, valid_columns)
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {self._quote(order_by)} {direction}"
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns,
            "rows": rows,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("insert values must be a non-empty object")

        provided_columns = list(values.keys())
        self._validate_columns(provided_columns, valid_columns)
        placeholders = ", ".join("?" for _ in provided_columns)
        column_sql = ", ".join(self._quote(column) for column in provided_columns)
        params = [values[column] for column in provided_columns]

        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    f"INSERT INTO {self._quote(table)} ({column_sql}) VALUES ({placeholders})",
                    params,
                )
                connection.commit()
                inserted_id = cursor.lastrowid
                row = connection.execute(
                    f"SELECT * FROM {self._quote(table)} WHERE rowid = ?",
                    (inserted_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"insert violates a database constraint: {exc}") from exc

        return {
            "table": table,
            "inserted_id": inserted_id,
            "row": dict(row) if row else {**values},
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: Any = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        metric = str(metric).lower()
        if metric not in self.AGGREGATES:
            raise ValidationError(f"unsupported aggregate metric '{metric}'")
        if metric == "count":
            aggregate_target = "*"
        else:
            if column is None:
                raise ValidationError(f"aggregate metric '{metric}' requires a column")
            self._validate_column(column, valid_columns)
            aggregate_target = self._quote(column)

        select_parts = []
        if group_by is not None:
            self._validate_column(group_by, valid_columns)
            select_parts.append(self._quote(group_by))
        select_parts.append(f"{metric.upper()}({aggregate_target}) AS value")

        where_sql, params = self._build_where_clause(filters, valid_columns)
        sql = f"SELECT {', '.join(select_parts)} FROM {self._quote(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if group_by is not None:
            sql += f" GROUP BY {self._quote(group_by)} ORDER BY {self._quote(group_by)}"

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }

    def _validate_table(self, table: str) -> list[str]:
        self._validate_identifier(table, "table")
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"unknown table '{table}'. Available tables: {', '.join(tables)}")
        return [column["name"] for column in self.get_table_schema_unchecked(table)]

    def get_table_schema_unchecked(self, table: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [
            {
                "name": column["name"],
                "type": column["type"],
                "nullable": not bool(column["notnull"]),
                "default": column["dflt_value"],
                "primary_key": bool(column["pk"]),
            }
            for column in columns
        ]

    def _validate_columns(self, columns: list[str], valid_columns: list[str]) -> list[str]:
        if not isinstance(columns, list) or not columns:
            raise ValidationError("columns must be a non-empty list")
        for column in columns:
            self._validate_column(column, valid_columns)
        return columns

    def _validate_column(self, column: str, valid_columns: list[str]) -> None:
        self._validate_identifier(column, "column")
        if column not in valid_columns:
            raise ValidationError(f"unknown column '{column}'. Available columns: {', '.join(valid_columns)}")

    def _validate_identifier(self, value: str, kind: str) -> None:
        if not isinstance(value, str) or not self.IDENTIFIER_RE.match(value):
            raise ValidationError(f"invalid {kind} identifier '{value}'")

    def _validate_non_negative_int(self, value: int, name: str, upper_bound: int | None = None) -> int:
        if not isinstance(value, int):
            raise ValidationError(f"{name} must be an integer")
        if value < 0:
            raise ValidationError(f"{name} must be non-negative")
        if upper_bound is not None and value > upper_bound:
            raise ValidationError(f"{name} must be <= {upper_bound}")
        return value

    def _build_where_clause(self, filters: Any, valid_columns: list[str]) -> tuple[str, list[Any]]:
        if filters in (None, {}, []):
            return "", []

        normalized = self._normalize_filters(filters)
        clauses: list[str] = []
        params: list[Any] = []
        for item in normalized:
            column = item["column"]
            operator = item["op"]
            value = item["value"]
            self._validate_column(column, valid_columns)
            if operator not in self.SUPPORTED_OPERATORS:
                raise ValidationError(f"unsupported filter operator '{operator}'")

            sql_operator = self.SUPPORTED_OPERATORS[operator]
            if sql_operator == "IN":
                if not isinstance(value, list) or not value:
                    raise ValidationError("in filters require a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{self._quote(column)} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{self._quote(column)} {sql_operator} ?")
                params.append(value)
        return " AND ".join(clauses), params

    def _normalize_filters(self, filters: Any) -> list[dict[str, Any]]:
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except json.JSONDecodeError as exc:
                raise ValidationError("filters string must be valid JSON") from exc
        if isinstance(filters, dict):
            normalized = []
            for column, value in filters.items():
                if isinstance(value, dict):
                    normalized.append({"column": column, "op": value.get("op", "eq"), "value": value.get("value")})
                else:
                    normalized.append({"column": column, "op": "eq", "value": value})
            return normalized
        if isinstance(filters, list):
            normalized = []
            for item in filters:
                if not isinstance(item, dict) or not {"column", "op", "value"} <= set(item):
                    raise ValidationError("filter list items must include column, op, and value")
                normalized.append({"column": item["column"], "op": item["op"], "value": item["value"]})
            return normalized
        raise ValidationError("filters must be an object, list, JSON string, or null")

    def _quote(self, identifier: str) -> str:
        self._validate_identifier(identifier, "identifier")
        return f'"{identifier}"'


class PostgresAdapter:
    """PostgreSQL-backed adapter with the same MCP-facing surface as SQLiteAdapter."""

    SUPPORTED_OPERATORS = SQLiteAdapter.SUPPORTED_OPERATORS
    AGGREGATES = SQLiteAdapter.AGGREGATES
    IDENTIFIER_RE = SQLiteAdapter.IDENTIFIER_RE

    def __init__(self, dsn: str, schema: str = "public"):
        if psycopg is None:
            raise RuntimeError("PostgreSQL support requires psycopg. Install with: python -m pip install psycopg[binary]")
        self.dsn = dsn
        self.schema = schema
        self._validate_identifier(schema, "schema")

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def list_tables(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (self.schema,),
            ).fetchall()
        return [row["table_name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self._validate_table(table)
        columns = self.get_table_schema_unchecked(table)
        with self.connect() as connection:
            foreign_keys = connection.execute(
                """
                SELECT
                    kcu.column_name AS column_name,
                    ccu.table_name AS references_table,
                    ccu.column_name AS references_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name = %s
                ORDER BY kcu.column_name
                """,
                (self.schema, table),
            ).fetchall()
            indexes = connection.execute(
                """
                SELECT indexname AS name, indexdef LIKE 'CREATE UNIQUE%%' AS unique
                FROM pg_indexes
                WHERE schemaname = %s
                  AND tablename = %s
                ORDER BY indexname
                """,
                (self.schema, table),
            ).fetchall()

        return {
            "table": table,
            "schema": self.schema,
            "columns": columns,
            "foreign_keys": [
                {
                    "column": fk["column_name"],
                    "references_table": fk["references_table"],
                    "references_column": fk["references_column"],
                }
                for fk in foreign_keys
            ],
            "indexes": [{"name": index["name"], "unique": bool(index["unique"])} for index in indexes],
        }

    def get_database_schema(self) -> dict[str, Any]:
        return {
            "backend": "postgresql",
            "schema": self.schema,
            "tables": {table: self.get_table_schema(table) for table in self.list_tables()},
        }

    def search(
        self,
        table: str,
        filters: Any = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        selected_columns = self._validate_columns(columns or valid_columns, valid_columns)
        limit = self._validate_non_negative_int(limit, "limit", upper_bound=100)
        offset = self._validate_non_negative_int(offset, "offset")
        where_sql, params = self._build_where_clause(filters, valid_columns)

        sql = f"SELECT {', '.join(self._quote(column) for column in selected_columns)} FROM {self._qualified_table(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if order_by is not None:
            self._validate_column(order_by, valid_columns)
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {self._quote(order_by)} {direction}"
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return {
            "table": table,
            "backend": "postgresql",
            "columns": selected_columns,
            "rows": rows,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("insert values must be a non-empty object")

        provided_columns = list(values.keys())
        self._validate_columns(provided_columns, valid_columns)
        placeholders = ", ".join("%s" for _ in provided_columns)
        column_sql = ", ".join(self._quote(column) for column in provided_columns)
        params = [values[column] for column in provided_columns]

        try:
            with self.connect() as connection:
                row = connection.execute(
                    f"INSERT INTO {self._qualified_table(table)} ({column_sql}) VALUES ({placeholders}) RETURNING *",
                    params,
                ).fetchone()
                connection.commit()
        except psycopg.IntegrityError as exc:
            raise ValidationError(f"insert violates a database constraint: {exc}") from exc

        return {
            "table": table,
            "backend": "postgresql",
            "inserted_id": row.get("id") if row else None,
            "row": row if row else {**values},
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: Any = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        valid_columns = self._validate_table(table)
        metric = str(metric).lower()
        if metric not in self.AGGREGATES:
            raise ValidationError(f"unsupported aggregate metric '{metric}'")
        if metric == "count":
            aggregate_target = "*"
        else:
            if column is None:
                raise ValidationError(f"aggregate metric '{metric}' requires a column")
            self._validate_column(column, valid_columns)
            aggregate_target = self._quote(column)

        select_parts = []
        if group_by is not None:
            self._validate_column(group_by, valid_columns)
            select_parts.append(self._quote(group_by))
        select_parts.append(f"{metric.upper()}({aggregate_target}) AS value")

        where_sql, params = self._build_where_clause(filters, valid_columns)
        sql = f"SELECT {', '.join(select_parts)} FROM {self._qualified_table(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if group_by is not None:
            sql += f" GROUP BY {self._quote(group_by)} ORDER BY {self._quote(group_by)}"

        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        return {
            "table": table,
            "backend": "postgresql",
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }

    def _validate_table(self, table: str) -> list[str]:
        self._validate_identifier(table, "table")
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"unknown table '{table}'. Available tables: {', '.join(tables)}")
        return [column["name"] for column in self.get_table_schema_unchecked(table)]

    def get_table_schema_unchecked(self, table: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.column_name AS name,
                    c.data_type AS type,
                    c.is_nullable = 'YES' AS nullable,
                    c.column_default AS default,
                    EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_schema = c.table_schema
                          AND tc.table_name = c.table_name
                          AND kcu.column_name = c.column_name
                    ) AS primary_key
                FROM information_schema.columns c
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (self.schema, table),
            ).fetchall()
        return [
            {
                "name": column["name"],
                "type": column["type"],
                "nullable": bool(column["nullable"]),
                "default": column["default"],
                "primary_key": bool(column["primary_key"]),
            }
            for column in rows
        ]

    def _validate_columns(self, columns: list[str], valid_columns: list[str]) -> list[str]:
        return SQLiteAdapter._validate_columns(self, columns, valid_columns)

    def _validate_column(self, column: str, valid_columns: list[str]) -> None:
        SQLiteAdapter._validate_column(self, column, valid_columns)

    def _validate_identifier(self, value: str, kind: str) -> None:
        SQLiteAdapter._validate_identifier(self, value, kind)

    def _validate_non_negative_int(self, value: int, name: str, upper_bound: int | None = None) -> int:
        return SQLiteAdapter._validate_non_negative_int(self, value, name, upper_bound)

    def _build_where_clause(self, filters: Any, valid_columns: list[str]) -> tuple[str, list[Any]]:
        if filters in (None, {}, []):
            return "", []

        normalized = self._normalize_filters(filters)
        clauses: list[str] = []
        params: list[Any] = []
        for item in normalized:
            column = item["column"]
            operator = item["op"]
            value = item["value"]
            self._validate_column(column, valid_columns)
            if operator not in self.SUPPORTED_OPERATORS:
                raise ValidationError(f"unsupported filter operator '{operator}'")

            sql_operator = self.SUPPORTED_OPERATORS[operator]
            if sql_operator == "IN":
                if not isinstance(value, list) or not value:
                    raise ValidationError("in filters require a non-empty list value")
                placeholders = ", ".join("%s" for _ in value)
                clauses.append(f"{self._quote(column)} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{self._quote(column)} {sql_operator} %s")
                params.append(value)
        return " AND ".join(clauses), params

    def _normalize_filters(self, filters: Any) -> list[dict[str, Any]]:
        return SQLiteAdapter._normalize_filters(self, filters)

    def _quote(self, identifier: str) -> str:
        self._validate_identifier(identifier, "identifier")
        return f'"{identifier}"'

    def _qualified_table(self, table: str) -> str:
        self._validate_identifier(table, "table")
        return f"{self._quote(self.schema)}.{self._quote(table)}"
