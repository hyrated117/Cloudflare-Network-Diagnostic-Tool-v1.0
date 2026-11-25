#!/usr/bin/env python3
"""Cloudflare network diagnostics over newline-delimited JSON-RPC on stdio."""

import csv
import io
import json
import logging
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROTOCOL_VERSION = "2024-11-05"
MAX_DOH_BYTES = 65536
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


def trace_candidates():
    """Commands to try, in order, as (executable, fixed arguments) pairs."""
    if sys.platform.startswith("win"):
        # Windows ships tracert rather than traceroute. -d skips reverse DNS and
        # -h/-w bound a full run well inside the 20 second timeout.
        return [("tracert", ["-d", "-h", "15", "-w", "300"])]
    return [("traceroute", []), ("tracepath", [])]


class DiagnosticServer:
    """MCP-style JSON-RPC stdio server with network diagnostic tools."""

    def __init__(self):
        self.version = "1.0.1"
        self.name = "Cloudflare Network Diagnostic Tool"
        self.tools = {
            "dns_check": {
                "description": "Resolve IPv4 and IPv6 addresses for a domain.",
                "inputSchema": {"type": "object", "properties": {"domain": {"type": "string", "description": "Domain name to resolve"}}, "required": ["domain"], "additionalProperties": False},
                "handler": self.dns_check,
            },
            "doh_test": {
                "description": "Send a request to a DNS-over-HTTPS endpoint.",
                "inputSchema": {"type": "object", "properties": {"url": {"type": "string", "format": "uri", "description": "HTTP(S) DoH endpoint URL"}}, "required": ["url"], "additionalProperties": False},
                "handler": self.doh_test,
            },
            "trace_route": {
                "description": "Run traceroute or tracepath to a destination when available.",
                "inputSchema": {"type": "object", "properties": {"destination": {"type": "string", "description": "Host or IP address"}}, "required": ["destination"], "additionalProperties": False},
                "handler": self.trace_route,
            },
            "health_score": {
                "description": "Check TCP connectivity to Cloudflare DNS and return a basic health result.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                "handler": self.health_score,
            },
            "export_results": {
                "description": "Format diagnostic results as JSON or CSV.",
                "inputSchema": {"type": "object", "properties": {"format": {"type": "string", "enum": ["json", "csv"]}, "results": {"type": "object", "description": "Diagnostic payload to export"}}, "additionalProperties": False},
                "handler": self.export_results,
            },
        }

    def dns_check(self, domain):
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError("domain must be a non-empty string")
        domain = domain.strip()
        try:
            addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(domain, None)})
            return {"tool": "dns_check", "domain": domain, "status": "ok", "addresses": addresses, "timestamp": now()}
        except socket.gaierror as exc:
            return {"tool": "dns_check", "domain": domain, "status": "error", "addresses": [], "error": str(exc), "timestamp": now()}

    def doh_test(self, url):
        if not isinstance(url, str):
            raise ValueError("url must be a valid HTTP(S) URL")
        try:
            parsed = urllib.parse.urlsplit(url)
        except ValueError as exc:
            raise ValueError("url must be a valid HTTP(S) URL") from exc
        if not parsed.netloc:
            raise ValueError("url must be a valid HTTP(S) URL")
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
            raise ValueError("url must use HTTP or HTTPS and must not contain credentials")
        request = urllib.request.Request(url, headers={"Accept": "application/dns-json", "User-Agent": "Cloudflare-Diagnostic-Tool/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = response.read(MAX_DOH_BYTES + 1)
                # A body over the cap is a remote outcome, so report it like a
                # timeout: a tool result with status "error", not -32602.
                if len(payload) > MAX_DOH_BYTES:
                    return {"tool": "doh_test", "url": url, "status": "error", "statusCode": response.status, "error": "DoH response exceeded 64 KiB limit", "timestamp": now()}
                text = payload.decode("utf-8", errors="replace")
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"raw": text}
                return {"tool": "doh_test", "url": url, "status": "ok" if 200 <= response.status < 300 else "error", "statusCode": response.status, "response": data, "timestamp": now()}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {"tool": "doh_test", "url": url, "status": "error", "error": str(exc), "timestamp": now()}

    def trace_route(self, destination):
        if not isinstance(destination, str) or not destination.strip() or any(ch.isspace() for ch in destination) or destination.strip().startswith("-"):
            raise ValueError("destination must be a non-empty host or IP without whitespace and must not start with '-'")
        destination = destination.strip()
        for command, fixed_args in trace_candidates():
            try:
                completed = subprocess.run([command, *fixed_args, destination], capture_output=True, text=True, errors="replace", timeout=20, check=False)
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired as exc:
                return {"tool": "trace_route", "destination": destination, "status": "error", "error": str(exc), "timestamp": now()}
            output = completed.stdout.strip() or completed.stderr.strip() or "No output captured"
            return {"tool": "trace_route", "destination": destination, "status": "ok" if completed.returncode == 0 else "error", "returnCode": completed.returncode, "output": output, "timestamp": now()}
        return {"tool": "trace_route", "destination": destination, "status": "unavailable", "message": "No traceroute, tracepath or tracert utility available on this system.", "timestamp": now()}

    def health_score(self):
        try:
            with socket.create_connection(("1.1.1.1", 443), timeout=3):
                reachable = True
        except OSError:
            reachable = False
        return {"tool": "health_score", "score": 95 if reachable else 64, "status": "healthy" if reachable else "degraded", "reachable": reachable, "timestamp": now()}

    def export_results(self, format="json", results=None):
        if format not in ("json", "csv"):
            raise ValueError("format must be 'json' or 'csv'")
        if results is None:
            results = {}
        if not isinstance(results, dict):
            raise ValueError("results must be an object")
        if format == "json":
            content = json.dumps(results, indent=2)
        else:
            output = io.StringIO(newline="")
            writer = csv.writer(output, lineterminator="\n")
            writer.writerow(["name", "value"])
            for key, value in results.items():
                # Strings verbatim, every other value as compact JSON, matching the Node server.
                cell = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                writer.writerow([key, cell])
            content = output.getvalue().rstrip("\n")
        return {"tool": "export_results", "format": format, "status": "ok", "content": content, "timestamp": now()}

    def list_tools(self):
        return [{"name": name, "description": tool["description"], "inputSchema": tool["inputSchema"]} for name, tool in self.tools.items()]

    def process_message(self, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid Request"}}
        notification = "id" not in message
        msg_id = message.get("id")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return None if notification else {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "params must be an object"}}

        method = message["method"]
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": {"name": self.name, "version": self.version}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.list_tools()}
        elif method == "tools/call":
            try:
                name = params.get("name")
                tool = self.tools.get(name)
                if tool is None:
                    raise ValueError(f"Unknown tool '{name}'")
                arguments = params.get("arguments", {})
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
                schema = tool["inputSchema"]
                missing = [key for key in schema.get("required", []) if key not in arguments]
                if missing:
                    raise ValueError(f"Missing required argument '{missing[0]}'")
                extra = set(arguments) - set(schema.get("properties", {}))
                if schema.get("additionalProperties") is False and extra:
                    raise ValueError(f"Unexpected argument '{sorted(extra)[0]}'")
                output = tool["handler"](**arguments)
                result = {"content": [{"type": "text", "text": json.dumps(output)}], "structuredContent": output, "isError": output.get("status") == "error"}
            except (TypeError, ValueError) as exc:
                return None if notification else {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": str(exc)}}
        else:
            return None if notification else {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

        return None if notification else {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def run(self):
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            else:
                response = self.process_message(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    DiagnosticServer().run()
