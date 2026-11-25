#!/usr/bin/env python3
"""Conformance check: the Python and Node servers must answer identically.

Both entry points in server/ implement the same MCP stdio surface, and they had
drifted: one accepted arguments its own input schema forbade, exported CSV in a
different dialect, described tools differently, and rejected URLs with another
message. This script feeds the same requests to both servers and fails on any
difference except the volatile fields (timestamps, and the text copy of a tool
result, which the runtimes serialize with different whitespace; its payload is
compared instead).

Every request but `health_score` is answered without network access: the arguments
are rejected before a lookup, or PATH is emptied so trace_route reports that no
traceroute tool exists. `health_score` opens the same TCP connection to
1.1.1.1:443 in both servers, so both must report the same `reachable` and `score`
whether the probe succeeds or is blocked. `--live-trace DEST` adds one real trace
and asserts it succeeds on both servers, which is how Windows CI exercises the
tracert path.
"""

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_SERVER = [sys.executable, str(REPO_ROOT / "server" / "index.py")]
NODE = shutil.which("node")
NODE_SERVER = [NODE, str(REPO_ROOT / "server" / "index.js")] if NODE else None

REQUESTS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "json", "results": {"ok": True, "count": 2, "nested": {"hosts": ["1.1.1.1", "8.8.8.8"]}}}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "csv", "results": {"ok": True, "count": 2, "nested": {"hosts": ["1.1.1.1", "8.8.8.8"]}, "note": "a, b"}}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "xml", "results": {}}}},
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "json", "results": [1, 2]}}},
    {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "dns_check", "arguments": {"domain": ""}}},
    {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "dns_check", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "dns_check", "arguments": {"domain": "example.com", "verbose": True}}},
    {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "doh_test", "arguments": {"url": ":"}}},
    {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "doh_test", "arguments": {"url": "http://"}}},
    {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "doh_test", "arguments": {"url": "ftp://example.com/dns-query"}}},
    {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {"name": "doh_test", "arguments": {"url": 42}}},
    {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": "-oops"}}},
    {"jsonrpc": "2.0", "id": 16, "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": "two words"}}},
    {"jsonrpc": "2.0", "id": 17, "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": 42}}},
    # Empty PATH: both servers must report the same "no traceroute tool" result.
    {"jsonrpc": "2.0", "id": 18, "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": "127.0.0.1"}}},
    {"jsonrpc": "2.0", "id": 19, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {"name": "export_results", "arguments": "not an object"}},
    {"jsonrpc": "2.0", "id": 21, "method": "does/not/exist", "params": {}},
    {"jsonrpc": "2.0", "id": 22, "method": "ping", "params": None},
    # The one real network call: both servers probe 1.1.1.1:443 and must agree.
    {"jsonrpc": "2.0", "id": 23, "method": "tools/call", "params": {"name": "health_score", "arguments": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
]
MALFORMED_LINE = "{not json"
LIVE_TRACE_REQUESTS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
]

failures = []


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    failures.append(message)


def payload():
    lines = [json.dumps(request) for request in REQUESTS] + [MALFORMED_LINE]
    return "\n".join(lines) + "\n"


def run(command, env, stdin):
    return subprocess.run(command, input=stdin, capture_output=True, text=True, env=env, timeout=180)


def responses(completed):
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


def normalize(value):
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if key == "timestamp":
                continue
            normalized[key] = [normalize_content(entry) for entry in item] if key == "content" and isinstance(item, list) else normalize(item)
        return normalized
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def normalize_content(entry):
    """The text entry duplicates structuredContent; compare its payload, not its spacing."""
    if isinstance(entry, dict) and isinstance(entry.get("text"), str):
        try:
            return {"type": entry.get("type"), "payload": normalize(json.loads(entry["text"]))}
        except json.JSONDecodeError:
            return normalize(entry)
    return normalize(entry)


def diff_text(expected, actual):
    left = json.dumps(expected, indent=1, sort_keys=True).splitlines()
    right = json.dumps(actual, indent=1, sort_keys=True).splitlines()
    return "\n".join(list(difflib.unified_diff(left, right, "server/index.py", "server/index.js", lineterm="", n=1))[:60])


def compare(expected, actual):
    if len(expected) != len(actual):
        return fail(f"response count: server/index.py answered {len(expected)}, server/index.js answered {len(actual)}")
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            return fail(f"response {index + 1} (id {left.get('id')}) differs\n{diff_text(left, right)}")
    print(f"ok {len(expected)} responses match")


def live_trace(destination):
    requests = LIVE_TRACE_REQUESTS + [{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": destination}}}]
    stdin = "\n".join(json.dumps(request) for request in requests) + "\n"
    for label, command in (("server/index.py", PYTHON_SERVER), ("server/index.js", NODE_SERVER)):
        if command is None:
            fail(f"{label}: node was not found on PATH")
            continue
        completed = run(command, dict(os.environ), stdin)
        try:
            result = responses(completed)[-1]["result"]["structuredContent"]
        except (IndexError, KeyError, json.JSONDecodeError):
            fail(f"{label}: no trace_route result for {destination} (exit {completed.returncode}): {completed.stderr.strip()[:300]}")
            continue
        output = result.get("output") or ""
        if result.get("status") != "ok":
            detail = result.get("error") or result.get("message") or (output.splitlines()[0] if output else "no output")
            fail(f"{label}: trace_route {destination} returned {result.get('status')}: {detail}")
        elif result.get("returnCode") not in (None, 0):
            fail(f"{label}: trace_route {destination} exited {result['returnCode']}")
        elif not output.strip():
            fail(f"{label}: trace_route {destination} produced no trace")
        elif destination not in output:
            fail(f"{label}: trace_route {destination} output does not mention the destination: {output[:300]}")
        else:
            print(f"ok {label}: traced {destination} in {len(output.splitlines())} lines")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live-trace", metavar="DESTINATION", help="also assert a real trace succeeds on both servers (Windows CI uses 127.0.0.1)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as empty:
        env = {**os.environ, "PATH": empty}
        stdin = payload()
        expected = responses(run(PYTHON_SERVER, env, stdin))
        if NODE_SERVER is None:
            fail("node was not found on PATH")
        else:
            compare(normalize(expected), normalize(responses(run(NODE_SERVER, env, stdin))))

    if args.live_trace:
        live_trace(args.live_trace)

    if failures:
        sys.exit(f"{len(failures)} conformance check(s) failed")

    print("Python and Node servers answer identically")


if __name__ == "__main__":
    main()
