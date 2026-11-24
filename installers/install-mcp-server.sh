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
for config in mcp-server.json mcp-client.json; do
    source="${REPO_ROOT}/server/${config}"
    [ ! -f "${source}" ] || install -m 644 "${source}" "${CONFIG_DIR}/${config}"
done

echo "Python MCP server installed at ${SERVER_DIR}/index.py"
echo "Configure your MCP client to launch that script with python3."
