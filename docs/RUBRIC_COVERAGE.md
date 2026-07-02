# Rubric Coverage

This file maps the grading rubric directly to repository evidence.

## 1. Server Foundation - 20 points

- FastMCP server starts successfully: `python implementation/mcp_server.py`
- Clean project structure: `implementation/`, `tests/`, `client-configs/`, `docs/`
- SQLite initialization: `python implementation/init_db.py`
- Server and database logic are separated:
  - `implementation/mcp_server.py`
  - `implementation/db.py`
  - `implementation/init_db.py`
  - `implementation/init_postgres.py`

## 2. Required Tools - 30 points

- `search`: implemented in `implementation/mcp_server.py` and `implementation/db.py`
- `insert`: implemented in `implementation/mcp_server.py` and `implementation/db.py`
- `aggregate`: implemented in `implementation/mcp_server.py` and `implementation/db.py`
- Tests:
  - `tests/test_db.py`
  - `tests/test_postgres.py`

## 3. MCP Resources - 15 points

- Full schema resource: `schema://database`
- Per-table resource template: `schema://table/{table_name}`
- Tests:
  - `tests/test_mcp_server.py`
  - `implementation/verify_server.py`

## 4. Safety and Error Handling - 15 points

- Unknown tables and columns are rejected in both adapters.
- Unsupported filter operators and invalid aggregate metrics are rejected.
- SQL values use bound parameters:
  - SQLite: `?` placeholders
  - PostgreSQL: `%s` placeholders
- Identifiers are allowlisted before SQL construction.
- Tests:
  - `tests/test_db.py`
  - `tests/test_postgres.py`

## 5. Verification - 10 points

- Tool discovery: `python implementation/verify_server.py`
- Successful tool calls: `search`, `insert`, `aggregate`
- Failing tool call: invalid table search returns a clear error
- Automated tests: `pytest tests/ -v`

## 6. Client Integration and Demo - 10 points

- MCP client verification: `implementation/verify_server.py` uses the Python MCP client over stdio.
- Client configuration examples:
  - `client-configs/claude-code.mcp.json`
  - `client-configs/codex.config.toml`
  - `client-configs/gemini-settings.json`
- Setup and test steps: `README.md`
- Demo evidence: `docs/DEMO_EVIDENCE.md`
- Inspector helpers:
  - `implementation/start_inspector.ps1`
  - `implementation/start_inspector.sh`

## Bonus - up to 10 points

- HTTP/SSE bearer-token auth: `implementation/mcp_server.py`
- SQLite and PostgreSQL behind the same MCP surface:
  - `SQLiteAdapter`
  - `PostgresAdapter`
  - `--backend sqlite`
  - `--backend postgresql`
- Extra polish:
  - pagination and output limit
  - structured tests
  - repeatable verification script
