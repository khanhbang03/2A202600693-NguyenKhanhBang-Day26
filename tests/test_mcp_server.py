from __future__ import annotations

import pytest

from implementation.init_db import create_database
from implementation.mcp_server import build_server


@pytest.mark.asyncio
async def test_tools_and_resources_are_registered(tmp_path):
    db_path = create_database(tmp_path / "lab.db")
    server = build_server(db_path)

    tools = await server.list_tools()
    assert sorted(tool.name for tool in tools) == ["aggregate", "insert", "search"]

    resources = await server.list_resources()
    assert [str(resource.uri) for resource in resources] == ["schema://database"]

    templates = await server.list_resource_templates()
    template_uris = [str(getattr(template, "uriTemplate", getattr(template, "uri_template", ""))) for template in templates]
    assert template_uris == ["schema://table/{table_name}"]
