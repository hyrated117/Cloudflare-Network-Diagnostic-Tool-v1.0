#!/bin/bash
# Python-only MCP server installer (macOS/Linux).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INSTALL_DIR="${HOME:?HOME must be set}/.local/cloudflare-mcp"
SERVER_DIR="${INSTALL_DIR}/server"
CONFIG_DIR="${INSTALL_DIR}/config"

command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required." >&2; exit 1; }
SOURCE="${REPO_ROOT}/server/index.py"
[ -f "${SOURCE}" ] || { echo "Server source not found: ${SOURCE}" >&2; exit 1; }

mkdir -p "${SERVER_DIR}" "${CONFIG_DIR}"
install -m 755 "${SOURCE}" "${SERVER_DIR}/index.py"

# Write the config files here, with the absolute path of the installed script.
# MCP clients resolve a relative "index.py" against their own working directory,
# not against the config file, so a relative path never finds the server.
PYTHON="$(command -v python3)"
SERVER_SCRIPT="${SERVER_DIR}/index.py"

json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

PYTHON_JSON="$(json_escape "${PYTHON}")"
SCRIPT_JSON="$(json_escape "${SERVER_SCRIPT}")"

cat > "${CONFIG_DIR}/mcp-server.json" <<EOF
{
  "name": "Cloudflare Network Diagnostic Tool",
  "version": "1.0.1",
  "description": "MCP server for Cloudflare network diagnostics",
  "type": "stdio",
  "command": "${PYTHON_JSON}",
  "args": ["${SCRIPT_JSON}"],
  "env": {
    "PYTHONUNBUFFERED": "1"
  }
}
EOF

cat > "${CONFIG_DIR}/mcp-client.json" <<EOF
{
  "name": "Cloudflare Diagnostic Client",
  "version": "1.0.1",
  "description": "MCP Client configuration for Cloudflare Network Diagnostic Tool",
  "servers": {
    "cloudflare-diagnostics": {
      "command": "${PYTHON_JSON}",
      "args": ["${SCRIPT_JSON}"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
EOF

echo "Python MCP server installed at ${SERVER_SCRIPT}"
echo "MCP configuration files are in ${CONFIG_DIR}"
