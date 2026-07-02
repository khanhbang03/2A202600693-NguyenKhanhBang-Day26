from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from init_db import create_database


ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "mcp_server.py"
DB = ROOT / "sqlite_lab_verify.db"


def _as_json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


async def main() -> None:
    create_database(DB)
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER), "--db", str(DB)],
        cwd=str(ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = sorted(tool.name for tool in tools.tools)
            assert tool_names == ["aggregate", "insert", "search"], tool_names
            print("tools:", ", ".join(tool_names))

            resources = await session.list_resources()
            resource_uris = sorted(str(resource.uri) for resource in resources.resources)
            assert "schema://database" in resource_uris, resource_uris
            print("resources:", ", ".join(resource_uris))

            templates = await session.list_resource_templates()
            template_uris = sorted(str(template.uriTemplate) for template in templates.resourceTemplates)
            assert "schema://table/{table_name}" in template_uris, template_uris
            print("resource templates:", ", ".join(template_uris))

            search = await session.call_tool(
                "search",
                {
                    "table": "students",
                    "filters": {"cohort": "A1"},
                    "columns": ["name", "cohort", "score"],
                    "order_by": "score",
                    "descending": True,
                },
            )
            assert not search.isError
            print("valid search:", _as_json(search.structuredContent or search.content))

            inserted = await session.call_tool(
                "insert",
                {
                    "table": "students",
                    "values": {
                        "name": "Lan Ho",
                        "cohort": "A1",
                        "score": 82.0,
                        "email": "lan.ho.verify@example.edu",
                    },
                },
            )
            assert not inserted.isError
            print("valid insert:", _as_json(inserted.structuredContent or inserted.content))

            aggregate = await session.call_tool(
                "aggregate",
                {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
            )
            assert not aggregate.isError
            print("valid aggregate:", _as_json(aggregate.structuredContent or aggregate.content))

            schema = await session.read_resource("schema://table/students")
            assert schema.contents
            print("table schema: schema://table/students readable")

            invalid = await session.call_tool("search", {"table": "missing_table"})
            assert invalid.isError
            print("invalid request error:", _as_json(invalid.content))

    print("verification complete")


if __name__ == "__main__":
    asyncio.run(main())
