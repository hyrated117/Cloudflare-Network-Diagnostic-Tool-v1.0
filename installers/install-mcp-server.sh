#!/bin/bash
# Python MCP Server Installer for macOS/Linux

set -e

echo "🚀 Python MCP Server Installer"
echo "==============================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION detected"

# Install dependencies
echo "📦 Installing dependencies..."
python3 -m pip install -q -r server/requirements.txt 2>/dev/null || echo "⚠️  Pip dependencies installation skipped"

# Create config directory
MCP_CONFIG_DIR="${HOME}/.config/mcp"
mkdir -p "$MCP_CONFIG_DIR"

echo "✅ Installation complete!"
echo "📝 Config directory: $MCP_CONFIG_DIR"
