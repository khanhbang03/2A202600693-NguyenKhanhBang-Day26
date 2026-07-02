#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export NPM_CONFIG_CACHE="$PWD/.npm-cache"
npx -y @modelcontextprotocol/inspector "$(command -v python)" "$PWD/mcp_server.py"
