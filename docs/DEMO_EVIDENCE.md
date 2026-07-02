# Demo Evidence

This transcript shows the server working from an MCP client. It is suitable to use as the voiceover/script for the short demo video.

## Command

```bash
python implementation/verify_server.py
```

## Verified Behavior

```text
tools: aggregate, insert, search
resources: schema://database
resource templates: schema://table/{table_name}
valid search: returns students in cohort A1 ordered by score
valid insert: inserts Lan Ho and returns the inserted row with generated id
valid aggregate: returns average score grouped by cohort
table schema: schema://table/students readable
invalid request error: unknown table 'missing_table'. Available tables: courses, enrollments, students
verification complete
```

## Inspector Demo Checklist

Use one of these commands:

```powershell
.\implementation\start_inspector.ps1
```

```bash
./implementation/start_inspector.sh
```

Then capture these screens for the submitted video or screenshots:

1. The server is connected.
2. Tools list contains `search`, `insert`, and `aggregate`.
3. Resources list contains `schema://database`.
4. Resource template list contains `schema://table/{table_name}`.
5. A valid `search` call returns rows.
6. A valid `aggregate` call returns grouped results.
7. An invalid `search` for `missing_table` returns a clear error.

## Bonus Demo Checklist

Run an authenticated HTTP server:

```bash
python implementation/mcp_server.py --transport streamable-http --auth-token dev-secret
```

Show that HTTP/SSE clients must send:

```text
Authorization: Bearer dev-secret
```

Run a PostgreSQL-backed server:

```bash
python implementation/init_postgres.py --dsn "postgresql://USER:PASSWORD@localhost:5432/DATABASE"
python implementation/mcp_server.py --backend postgresql --postgres-dsn "postgresql://USER:PASSWORD@localhost:5432/DATABASE"
```
