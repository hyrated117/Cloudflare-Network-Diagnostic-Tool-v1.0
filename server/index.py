#!/usr/bin/env python3
"""
Cloudflare Network Diagnostic Tool - Python MCP Server
Provides diagnostic tools for Cloudflare network services over stdio JSON-RPC.
"""

import json
import logging
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DiagnosticServer:
    """Main MCP Server for Cloudflare diagnostics."""

    def __init__(self):
        self.version = "1.0.0"
        self.name = "Cloudflare Network Diagnostic Tool"
        self.tools = {
            "dns_check": self.dns_check,
            "doh_test": self.doh_test,
            "trace_route": self.trace_route,
            "health_score": self.health_score,
            "export_results": self.export_results,
        }

    def dns_check(self, domain: str) -> dict:
        """Check DNS resolution for a domain."""
        logger.info("Running DNS check for %s", domain)
        try:
            info = socket.getaddrinfo(domain, None)
            addresses = sorted({item[4][0] for item in info})
            return {
                "tool": "dns_check",
                "domain": domain,
                "status": "ok",
                "addresses": addresses,
                "timestamp": datetime.now().isoformat(),
            }
        except socket.gaierror as exc:
            return {
                "tool": "dns_check",
                "domain": domain,
                "status": "error",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            }

    def doh_test(self, url: str) -> dict:
        """Test DNS-over-HTTPS endpoint."""
        logger.info("Testing DoH endpoint: %s", url)
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/dns-json",
                    "User-Agent": "Cloudflare-Diagnostic-Tool/1.0",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = {"raw": payload}
                return {
                    "tool": "doh_test",
                    "url": url,
                    "status": "ok",
                    "statusCode": response.status,
                    "response": data,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as exc:  # pragma: no cover - network-dependent
            return {
                "tool": "doh_test",
                "url": url,
                "status": "error",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            }

    def trace_route(self, destination: str) -> dict:
        """Perform traceroute to destination."""
        logger.info("Tracing route to %s", destination)
        command = None
        for candidate in ("traceroute", "tracepath"):
            if subprocess.run(["which", candidate], capture_output=True, text=True).returncode == 0:
                command = [candidate, destination]
                break
        if command is None:
            return {
                "tool": "trace_route",
                "destination": destination,
                "status": "unavailable",
                "message": "No traceroute utility available on this system.",
                "timestamp": datetime.now().isoformat(),
            }
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
            output = completed.stdout.strip() or completed.stderr.strip() or "No output captured"
            return {
                "tool": "trace_route",
                "destination": destination,
                "status": "ok" if completed.returncode == 0 else "error",
                "returnCode": completed.returncode,
                "output": output,
                "timestamp": datetime.now().isoformat(),
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "tool": "trace_route",
                "destination": destination,
                "status": "error",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            }

    def health_score(self) -> dict:
        """Calculate network health score."""
        logger.info("Calculating health score")
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=3)
            reachable = True
        except OSError:
            reachable = False
        score = 95 if reachable else 64
        status = "healthy" if reachable else "degraded"
        return {
            "tool": "health_score",
            "score": score,
            "status": status,
            "reachable": reachable,
            "timestamp": datetime.now().isoformat(),
        }

    def export_results(self, format: str = "json", results: dict | None = None) -> dict:
        """Export diagnostic results."""
        logger.info("Exporting results in %s format", format)
        payload = results or {}
        if format == "json":
            content = json.dumps(payload, indent=2)
        elif format == "csv":
            content = "tool,name,value\n"
            for key, value in payload.items():
                content += f"{key},{value}\n"
        else:
            content = str(payload)
        return {
            "tool": "export_results",
            "format": format,
            "status": "ok",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        if name not in self.tools:
            raise ValueError(f"Unknown tool '{name}'")
        args = arguments or {}
        return self.tools[name](**args)

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": tool.__doc__ or "No description provided.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            }
            for name, tool in self.tools.items()
        ]

    def process_message(self, message: dict):
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.list_tools()},
            }

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            try:
                result = self.call_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "json", "json": result}]},
                }
            except Exception as exc:  # pragma: no cover - caller error path
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32602, "message": str(exc)},
                }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"ok": True}}

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def run(self):
        logger.info("Starting %s v%s", self.name, self.version)
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON input: %s", exc)
                continue
            response = self.process_message(payload)
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    server = DiagnosticServer()
    server.run()
