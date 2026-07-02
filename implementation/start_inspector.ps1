$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python).Source
$env:NPM_CONFIG_CACHE = Join-Path $Here ".npm-cache"
npx -y @modelcontextprotocol/inspector $Python (Join-Path $Here "mcp_server.py")
