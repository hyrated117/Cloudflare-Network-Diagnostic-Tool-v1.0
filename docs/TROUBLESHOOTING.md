# 🛠️ Troubleshooting Guide  
Cloudflare Network Diagnostic Tool • MCP Server • AppMaker Generator

This guide helps diagnose and resolve common issues across the SwiftUI app, MCP server, and installer pack.

---

# ⚡ Quick Fixes

### ✔ Restart the MCP server
```bash
pkill -f cloudflare-network-diagnostic-mcp
rm -rf ~/.config/mcp/servers/*
bash installers/install-mcp-unified.sh
