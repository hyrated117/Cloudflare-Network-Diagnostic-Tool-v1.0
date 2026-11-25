#!/bin/bash
# Unified MCP Server Installer for macOS/Linux
# Supports Python and Node.js implementations

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Cloudflare Network Diagnostic Tool - MCP Server Installer"
echo "================================================="

VERSION="1.0.1"
INSTALL_DIR="${HOME}/.local/cloudflare-mcp"
LOG_FILE="${INSTALL_DIR}/install.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "${INSTALL_DIR}"

log() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "${LOG_FILE}"
}

log "Installing to: ${INSTALL_DIR}"

PYTHON_AVAILABLE=false
NODE_AVAILABLE=false
if command -v python3 >/dev/null 2>&1; then
    log "Python 3 found: $(python3 --version)"
    PYTHON_AVAILABLE=true
else
    warning "Python 3 not found"
fi

if command -v node >/dev/null 2>&1; then
    log "Node.js found: $(node --version)"
    NODE_AVAILABLE=true
else
    warning "Node.js not found"
fi

if [ "${PYTHON_AVAILABLE}" = false ] && [ "${NODE_AVAILABLE}" = false ]; then
    error "Python 3 or Node.js is required. Install one and retry."
fi

if [ "${PYTHON_AVAILABLE}" = true ]; then
    PYTHON_SOURCE="${REPO_ROOT}/server/index.py"
    [ -f "${PYTHON_SOURCE}" ] || error "Python server source not found: ${PYTHON_SOURCE}"
    log "Installing Python server..."
    mkdir -p "${INSTALL_DIR}/server/python"
    install -m 755 "${PYTHON_SOURCE}" "${INSTALL_DIR}/server/python/index.py"
    log "✓ Python server files installed"
fi

if [ "${NODE_AVAILABLE}" = true ]; then
    NODE_SOURCE="${REPO_ROOT}/server/index.js"
    [ -f "${NODE_SOURCE}" ] || error "Node server source not found: ${NODE_SOURCE}"

    log "Installing Node.js server..."
    NODE_INSTALL_DIR="${INSTALL_DIR}/server/node"
    mkdir -p "${NODE_INSTALL_DIR}"
    install -m 644 "${NODE_SOURCE}" "${NODE_INSTALL_DIR}/index.js"
    # The server is an ES module with no runtime dependencies, so this manifest
    # only tells Node to load index.js as a module and no npm install is needed.
    printf '{\n  "type": "module"\n}\n' > "${NODE_INSTALL_DIR}/package.json"
    log "✓ Node.js server files installed"
fi

# Write the config files with the absolute path of the installed script.
# MCP clients resolve a relative "index.py" against their own working directory,
# not against the config file, so a relative path never finds the server.
if [ "${PYTHON_AVAILABLE}" = true ]; then
    SERVER_COMMAND="$(command -v python3)"
    SERVER_SCRIPT="${INSTALL_DIR}/server/python/index.py"
    ENV_BODY='"PYTHONUNBUFFERED": "1"'
else
    SERVER_COMMAND="$(command -v node)"
    SERVER_SCRIPT="${INSTALL_DIR}/server/node/index.js"
    ENV_BODY=''
fi

json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

COMMAND_JSON="$(json_escape "${SERVER_COMMAND}")"
SCRIPT_JSON="$(json_escape "${SERVER_SCRIPT}")"

log "Writing configuration files..."
mkdir -p "${INSTALL_DIR}/config"
cat > "${INSTALL_DIR}/config/mcp-server.json" <<EOF
{
  "name": "Cloudflare Network Diagnostic Tool",
  "version": "${VERSION}",
  "description": "MCP server for Cloudflare network diagnostics",
  "type": "stdio",
  "command": "${COMMAND_JSON}",
  "args": ["${SCRIPT_JSON}"],
  "env": {${ENV_BODY}}
}
EOF
cat > "${INSTALL_DIR}/config/mcp-client.json" <<EOF
{
  "name": "Cloudflare Diagnostic Client",
  "version": "${VERSION}",
  "description": "MCP Client configuration for Cloudflare Network Diagnostic Tool",
  "servers": {
    "cloudflare-diagnostics": {
      "command": "${COMMAND_JSON}",
      "args": ["${SCRIPT_JSON}"],
      "env": {${ENV_BODY}}
    }
  }
}
EOF

log ""
log "✅ Installation files complete"
log "Version: ${VERSION}"
log "Install directory: ${INSTALL_DIR}"
log "Log file: ${LOG_FILE}"
log ""
log "Use the project server implementations in server/index.py and server/index.js."
log "For more information, visit: https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0"
