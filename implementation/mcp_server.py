from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from mcp.server.auth.provider import AccessToken
    from mcp.server.auth.provider import TokenVerifier
    from mcp.server.auth.settings import AuthSettings
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - compatibility with standalone fastmcp package
    from fastmcp import FastMCP  # type: ignore

    AccessToken = None  # type: ignore
    AuthSettings = None  # type: ignore
    TokenVerifier = object  # type: ignore

try:
    from .db import PostgresAdapter, SQLiteAdapter, ValidationError
    from .init_db import DEFAULT_DATABASE_PATH, create_database
except ImportError:  # pragma: no cover - script execution fallback
    from db import PostgresAdapter, SQLiteAdapter, ValidationError
    from init_db import DEFAULT_DATABASE_PATH, create_database


class StaticTokenVerifier(TokenVerifier):
    def __init__(self, token: str):
        self.token = token

    async def verify_token(self, token: str):
        if token == self.token:
            return AccessToken(token=token, client_id="sqlite-lab-client", scopes=["sqlite-lab"])
        return None


def _json(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def build_adapter(
    backend: str = "sqlite",
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    postgres_dsn: str | None = None,
    postgres_schema: str = "public",
):
    if backend == "sqlite":
        path = Path(database_path)
        if not path.exists():
            create_database(path)
        return SQLiteAdapter(path)
    if backend == "postgresql":
        if not postgres_dsn:
            raise ValueError("PostgreSQL backend requires --postgres-dsn or POSTGRES_DSN")
        return PostgresAdapter(postgres_dsn, schema=postgres_schema)
    raise ValueError(f"unsupported backend '{backend}'")


def build_server(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    auth_token: str | None = None,
    backend: str = "sqlite",
    postgres_dsn: str | None = None,
    postgres_schema: str = "public",
) -> FastMCP:
    adapter = build_adapter(backend, database_path, postgres_dsn, postgres_schema)
    kwargs = {
        "name": "Database Lab MCP Server",
        "instructions": "Use search, insert, aggregate, and schema resources to inspect the configured lab database.",
    }
    if auth_token:
        if AccessToken is None or AuthSettings is None:
            raise RuntimeError("HTTP/SSE auth requires the MCP SDK auth classes")
        kwargs["token_verifier"] = StaticTokenVerifier(auth_token)
        kwargs["auth"] = AuthSettings(
            issuer_url="http://localhost:8000",
            resource_server_url="http://localhost:8000",
            required_scopes=["sqlite-lab"],
        )

    mcp = FastMCP(**kwargs)

    @mcp.tool(name="search")
    def search(
        table: str,
        filters: dict | list | str | None = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict:
        """Search rows with validated filters, selected columns, ordering, and pagination."""
        try:
            return adapter.search(table, filters, columns, limit, offset, order_by, descending)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="insert")
    def insert(table: str, values: dict) -> dict:
        """Insert one row after validating table and column names."""
        try:
            return adapter.insert(table, values)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="aggregate")
    def aggregate(
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict | list | str | None = None,
        group_by: str | None = None,
    ) -> dict:
        """Run count, avg, sum, min, or max with optional filters and grouping."""
        try:
            return adapter.aggregate(table, metric, column, filters, group_by)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.resource("schema://database")
    def database_schema() -> str:
        """Return the complete database schema as JSON text."""
        return _json(adapter.get_database_schema())

    @mcp.resource("schema://table/{table_name}")
    def table_schema(table_name: str) -> str:
        """Return one table schema as JSON text."""
        try:
            return _json(adapter.get_table_schema(table_name))
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    return mcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the database lab FastMCP server.")
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgresql"],
        default=os.environ.get("DATABASE_BACKEND", "sqlite"),
    )
    parser.add_argument("--db", default=os.environ.get("SQLITE_LAB_DB", str(DEFAULT_DATABASE_PATH)))
    parser.add_argument("--postgres-dsn", default=os.environ.get("POSTGRES_DSN"))
    parser.add_argument("--postgres-schema", default=os.environ.get("POSTGRES_SCHEMA", "public"))
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--auth-token", default=os.environ.get("SQLITE_LAB_AUTH_TOKEN"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mcp = build_server(
        args.db,
        auth_token=args.auth_token,
        backend=args.backend,
        postgres_dsn=args.postgres_dsn,
        postgres_schema=args.postgres_schema,
    )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
