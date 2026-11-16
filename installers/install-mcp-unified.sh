#!/bin/bash
# Unified MCP Server Installer for macOS/Linux
# Supports Python and Node.js implementations

set -euo pipefail

 echo "🚀 Cloudflare Network Diagnostic Tool - MCP Server Installer"
echo "================================================="

VERSION="1.0.0"
INSTALL_DIR="${HOME}/.local/cloudflare-mcp"
LOG_FILE="${INSTALL_DIR}/install.log"

# Resolve repository files relative to this script, not the caller's working directory.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create installation directory before logging.
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

# Check for available runtimes.
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

# Install Python server if available.
if [ "${PYTHON_AVAILABLE}" = true ]; then
    PYTHON_SOURCE="${REPO_ROOT}/server/index.py"
    [ -f "${PYTHON_SOURCE}" ] || error "Python server source not found: ${PYTHON_SOURCE}"
    log "Installing Python server..."
    mkdir -p "${INSTALL_DIR}/server/python"
    install -m 755 "${PYTHON_SOURCE}" "${INSTALL_DIR}/server/python/index.py"
    log "✓ Python server files installed"
fi

# Install Node server if available. The package manifest lives under installers/.
if [ "${NODE_AVAILABLE}" = true ]; then
    NODE_SOURCE="${REPO_ROOT}/server/index.js"
    NODE_PACKAGE="${REPO_ROOT}/installers/package.json"
    [ -f "${NODE_SOURCE}" ] || error "Node server source not found: ${NODE_SOURCE}"
    [ -f "${NODE_PACKAGE}" ] || error "Node package manifest not found: ${NODE_PACKAGE}"
    log "Installing Node.js server..."
    mkdir -p "${INSTALL_DIR}/server/node"
    install -m 644 "${NODE_SOURCE}" "${INSTALL_DIR}/server/node/index.js"
    install -m 644 "${NODE_PACKAGE}" "${INSTALL_DIR}/server/node/package.json"
    (cd "${INSTALL_DIR}/server/node" && npm install --omit=dev)
    log "✓ Node.js server and dependencies installed"
fi

# Copy configuration files when present.
log "Copying configuration files..."
mkdir -p "${INSTALL_DIR}/config"
for config in mcp-server.json mcp-client.json; do
    if [ -f "${REPO_ROOT}/server/${config}" ]; then
        install -m 644 "${REPO_ROOT}/server/${config}" "${INSTALL_DIR}/config/${config}"
    else
        warning "Configuration file not found: server/${config}"
    fi
done

log ""
log "✅ Installation files complete"
log "Version: ${VERSION}"
log "Install directory: ${INSTALL_DIR}"
log "Log file: ${LOG_FILE}"
log ""
log "Note: The current server/index.py and server/index.js are diagnostic stubs, not complete MCP protocol servers."
log "For more information, visit: https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0"
