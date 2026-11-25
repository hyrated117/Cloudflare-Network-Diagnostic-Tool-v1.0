#!/usr/bin/env python3
"""Conformance check: the Python and Node servers must answer identically.

Both entry points in server/ implement the same MCP stdio surface, and they had
drifted: one accepted arguments its own input schema forbade, exported CSV in a
different dialect, described tools differently, and rejected URLs with another
message. This script feeds the same requests to both servers and fails on any
difference except the volatile fields (timestamps, and the text copy of a tool
result, which the runtimes serialize with different whitespace; its payload is
compared instead).

Every request except `health_score` is answered without network access: the
arguments are rejected before a lookup, or PATH is emptied so trace_route reports
that no traceroute tool exists. `health_score` probes 1.1.1.1:443, so the check
replaces that connect() in both runtimes (a sitecustomize stub for Python, a
--require stub for Node) and asks twice: once with the probe succeeding and once
with it failing. The probe is therefore deterministic, and the documented mapping
is asserted in both directions - reachable answers 95/healthy, blocked answers
64/degraded - instead of accepting whichever way a real network happened to go.
The stub logs each intercepted call, so the check also fails loudly if the probe
target ever changes and the stub stops being exercised.
`--live-trace DEST` adds one real trace and asserts it succeeds on both servers,
which is how Windows CI exercises the tracert path.
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
    # The only network calls, stubbed one outcome per request: reachable first,
    # blocked second, so both documented score/status pairs are asserted.
    {"jsonrpc": "2.0", "id": 23, "method": "tools/call", "params": {"name": "health_score", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 24, "method": "tools/call", "params": {"name": "health_score", "arguments": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
]
MALFORMED_LINE = "{not json"
# The probe outcomes the stubs hand out, in request order.
PROBE_SEQUENCE = ("reachable", "blocked")
HEALTH_SCORE_EXPECTED = (
    {"reachable": True, "score": 95, "status": "healthy"},
    {"reachable": False, "score": 64, "status": "degraded"},
)
LIVE_TRACE_REQUESTS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
]

# Prepended to PYTHONPATH; `site` imports it before the server does anything.
PYTHON_PROBE_STUB = '''\
"""Stub the health_score probe for Tools/check-conformance.py."""

import os
import socket

_sequence = [mode for mode in os.environ.get("CONFORMANCE_PROBE", "").split(",") if mode]
_log = os.environ.get("CONFORMANCE_PROBE_LOG")
_original = socket.create_connection


def create_connection(address, *args, **kwargs):
    if tuple(address[:2]) != ("1.1.1.1", 443) or not _sequence:
        return _original(address, *args, **kwargs)
    mode = _sequence.pop(0)
    if _log:
        with open(_log, "a", encoding="utf-8") as handle:
            handle.write(mode + "\\n")
    if mode == "blocked":
        raise OSError("conformance check: probe blocked")
    if mode == "reachable":
        return socket.socketpair()[0]
    raise RuntimeError(f"unknown conformance probe mode: {mode}")


socket.create_connection = create_connection
'''

# Loaded with `node --require`; patches the connect the server makes.
NODE_PROBE_STUB = """\
'use strict';
// Stub the health_score probe for Tools/check-conformance.py.
const fs = require('node:fs');
const net = require('node:net');
const { EventEmitter } = require('node:events');

const sequence = (process.env.CONFORMANCE_PROBE || '').split(',').filter(Boolean);
const logPath = process.env.CONFORMANCE_PROBE_LOG;
const original = net.createConnection;

net.createConnection = function createConnection(options, ...rest) {
  if (!options || options.host !== '1.1.1.1' || options.port !== 443 || sequence.length === 0) {
    return original.apply(net, [options, ...rest]);
  }
  const mode = sequence.shift();
  if (logPath) fs.appendFileSync(logPath, mode + '\\n');
  const socket = new EventEmitter();
  socket.destroy = () => {};
  process.nextTick(() => {
    if (mode === 'reachable') socket.emit('connect');
    else if (mode === 'blocked') socket.emit('error', new Error('conformance check: probe blocked'));
    else throw new Error(`unknown conformance probe mode: ${mode}`);
  });
  return socket;
};
"""

failures = []


def fail(message):
    if message in failures:
        return
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
    if not failures:
        print(f"ok {len(expected)} responses match")


def build_env(workdir, log_path):
    """Empty PATH (so trace_route finds no tool) plus the probe stubs."""
    env = {**os.environ}
    env["PATH"] = str(workdir / "empty")
    env["CONFORMANCE_PROBE"] = ",".join(PROBE_SEQUENCE)
    env["CONFORMANCE_PROBE_LOG"] = str(log_path)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(workdir / "python"), env.get("PYTHONPATH"))))
    env["NODE_OPTIONS"] = " ".join(filter(None, (env.get("NODE_OPTIONS"), f'--require "{workdir / "node-probe-stub.cjs"}"')))
    return env


def check_probe_stub(label, log_path):
    """The stub must have answered every probe; otherwise this measured the network."""
    intercepted = log_path.read_text(encoding="utf-8").split() if log_path.exists() else []
    if intercepted != list(PROBE_SEQUENCE):
        fail(f"{label}: the health_score probe stub intercepted {intercepted}, expected {list(PROBE_SEQUENCE)} (probe target or stubbing changed)")


def check_health_scores(label, normalized):
    """Both documented outcomes must come back exactly, in request order."""
    results = []
    for response in normalized:
        result = response.get("result")
        structured = result.get("structuredContent") if isinstance(result, dict) else None
        if isinstance(structured, dict) and structured.get("tool") == "health_score":
            results.append(structured)
    if len(results) != len(HEALTH_SCORE_EXPECTED):
        return fail(f"{label}: answered {len(results)} health_score results, expected {len(HEALTH_SCORE_EXPECTED)}")
    for index, (result, expected) in enumerate(zip(results, HEALTH_SCORE_EXPECTED), start=1):
        actual = {key: result.get(key) for key in expected}
        if actual != expected:
            fail(f"{label}: health_score probe {index} returned {actual}, expected {expected}")


def run_server(command, workdir, log_name, label):
    log_path = workdir / log_name
    completed = run(command, build_env(workdir, log_path), payload())
    normalized = normalize(responses(completed))
    check_probe_stub(label, log_path)
    check_health_scores(label, normalized)
    return normalized


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

    with tempfile.TemporaryDirectory() as temporary:
        workdir = Path(temporary)
        (workdir / "empty").mkdir()
        (workdir / "python").mkdir()
        (workdir / "python" / "sitecustomize.py").write_text(PYTHON_PROBE_STUB, encoding="utf-8")
        (workdir / "node-probe-stub.cjs").write_text(NODE_PROBE_STUB, encoding="utf-8")

        expected = run_server(PYTHON_SERVER, workdir, "probe-python.log", "server/index.py")
        if NODE_SERVER is None:
            fail("node was not found on PATH")
        else:
            compare(expected, run_server(NODE_SERVER, workdir, "probe-node.log", "server/index.js"))

    if args.live_trace:
        live_trace(args.live_trace)

    if failures:
        sys.exit(f"{len(failures)} conformance check(s) failed")

    print("Python and Node servers answer identically")


if __name__ == "__main__":
    main()
