#!/usr/bin/env python3
"""Smoke-test the Python MCP stdio server without external network access."""

import json
import subprocess
import sys

requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "json", "results": {"ok": True}}}},
]
completed = subprocess.run(
    [sys.executable, "server/index.py"],
    input="".join(json.dumps(item) + "\n" for item in requests),
    text=True,
    capture_output=True,
    check=True,
    timeout=15,
)
responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
assert len(responses) == 3, f"Expected 3 JSON-RPC responses, got {len(responses)}"
assert responses[0]["id"] == 1 and "serverInfo" in responses[0]["result"]
assert responses[1]["id"] == 2 and {tool["name"] for tool in responses[1]["result"]["tools"]} >= {"dns_check", "export_results"}
assert responses[2]["id"] == 3 and responses[2]["result"]["content"]
print("Python MCP smoke test passed")
