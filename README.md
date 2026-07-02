# SQLite Lab FastMCP Server

This repository contains a complete FastMCP server backed by SQLite or PostgreSQL. It exposes the required MCP tools:

- `search`
- `insert`
- `aggregate`

It also exposes schema context through:

- `schema://database`
- `schema://table/{table_name}`

The sample database contains `students`, `courses`, and `enrollments` tables with reproducible seed data for both database backends.

## Project Structure

```text
implementation/
  db.py                 # SQLite adapter, validation, safe SQL construction
  init_db.py            # reproducible schema and seed data
  init_postgres.py      # reproducible PostgreSQL schema and seed data
  mcp_server.py         # FastMCP tools, resources, stdio/http/sse startup
  verify_server.py      # repeatable MCP stdio smoke test
  start_inspector.ps1   # Windows Inspector helper
  start_inspector.sh    # macOS/Linux Inspector helper
client-configs/
  claude-code.mcp.json
  codex.config.toml
  gemini-settings.json
tests/
  test_db.py
  test_mcp_server.py
```

## Setup

```bash
python -m pip install -r requirements.txt
python implementation/init_db.py
```

The SQLite database is created at `implementation/sqlite_lab.db`. If it is missing, `mcp_server.py` also creates it automatically.

To initialize PostgreSQL, set a DSN or pass one explicitly:

```bash
python implementation/init_postgres.py --dsn "postgresql://USER:PASSWORD@localhost:5432/DATABASE"
```

## Run The Server

Default stdio transport:

```bash
python implementation/mcp_server.py
```

Use a custom SQLite database:

```bash
python implementation/mcp_server.py --db implementation/sqlite_lab.db
```

Use PostgreSQL with the same MCP tools and resources:

```bash
python implementation/mcp_server.py --backend postgresql --postgres-dsn "postgresql://USER:PASSWORD@localhost:5432/DATABASE"
```

The same setting can be provided through environment variables:

```bash
DATABASE_BACKEND=postgresql
POSTGRES_DSN=postgresql://USER:PASSWORD@localhost:5432/DATABASE
POSTGRES_SCHEMA=public
```

Bonus HTTP transport with bearer-token auth:

```bash
python implementation/mcp_server.py --transport streamable-http --auth-token dev-secret
```

Bonus SSE transport with bearer-token auth:

```bash
python implementation/mcp_server.py --transport sse --auth-token dev-secret
```

HTTP and SSE clients must send:

```text
Authorization: Bearer dev-secret
```

## Tools

### `search`

Searches validated table rows with selected columns, filters, ordering, limit, and offset.

Example arguments:

```json
{
  "table": "students",
  "filters": {"cohort": "A1"},
  "columns": ["name", "cohort", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 20,
  "offset": 0
}
```

Supported filter operators: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `like`, `in`.

### `insert`

Inserts one row after validating the table and all provided columns.

Example arguments:

```json
{
  "table": "students",
  "values": {
    "name": "Lan Ho",
    "cohort": "A1",
    "score": 82.0,
    "email": "lan.ho@example.edu"
  }
}
```

### `aggregate`

Runs `count`, `avg`, `sum`, `min`, or `max` with optional filters and grouping.

Example arguments:

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

## Resources

Read the full database schema:

```text
schema://database
```

Read one table schema:

```text
schema://table/students
```

## Verification

Run automated tests:

```bash
pytest tests/ -v
```

Run a real MCP stdio smoke test:

```bash
python implementation/verify_server.py
```

The verification script checks:

- server initialization
- discovery of `search`, `insert`, and `aggregate`
- discovery of `schema://database`
- discovery of `schema://table/{table_name}`
- successful search, insert, aggregate, and schema reads
- a clear error for an invalid table request

To run the optional live PostgreSQL test:

```bash
POSTGRES_TEST_DSN="postgresql://USER:PASSWORD@localhost:5432/DATABASE" pytest tests/test_postgres.py -v
```

## Inspector

Windows PowerShell:

```powershell
.\implementation\start_inspector.ps1
```

macOS/Linux:

```bash
chmod +x implementation/start_inspector.sh
./implementation/start_inspector.sh
```

Manual command:

```bash
npx -y @modelcontextprotocol/inspector python /ABSOLUTE/PATH/TO/implementation/mcp_server.py
```

In Inspector, verify that the tools and resources appear, then run one valid call and one invalid call.

## MCP Client Examples

Config examples are in `client-configs/`. Replace `/ABSOLUTE/PATH/TO` with this repository's absolute path.

Gemini CLI command:

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

Gemini smoke prompt:

```bash
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server and show me the top 2 students by score."
```

Codex config fragment:

```toml
[mcp_servers.sqlite_lab]
command = "python"
args = ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
```

Claude Code `.mcp.json` fragment:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

## Demo Script

For a short demo video, show these steps:

1. Run `python implementation/verify_server.py`.
2. Open Inspector with `implementation/start_inspector.ps1` or `implementation/start_inspector.sh`.
3. Show tool discovery for `search`, `insert`, and `aggregate`.
4. Read `schema://database` and `schema://table/students`.
5. Run `search` for cohort `A1`.
6. Run `aggregate` for average score by cohort.
7. Run an invalid `search` against `missing_table` and show the clear error.
8. Optional bonus: start `--transport streamable-http --auth-token dev-secret` and show that HTTP clients need a bearer token.

## Deliverable Checklist

- Working FastMCP server: complete
- SQLite database and seed data: complete
- `search`, `insert`, `aggregate` tools: complete
- Schema resource and schema resource template: complete
- Verification steps: complete
- Automated tests and repeatable verification script: complete
- Client configuration examples: complete
- README with setup and demo steps: complete
- Inspector startup command and helper scripts: complete
- Verified MCP stdio client smoke test: complete
- Bonus authentication for HTTP/SSE transport: complete
- Bonus PostgreSQL backend behind the same MCP surface: complete
- Bonus pagination and output limits: complete
