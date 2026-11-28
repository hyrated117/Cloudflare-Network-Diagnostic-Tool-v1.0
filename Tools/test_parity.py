#!/usr/bin/env python3
"""Differential test: both servers must answer a randomized corpus identically.

`Tools/check-conformance.py` pins 28 hand-written cases. That catches drift in the
behaviour someone thought to list, and nothing else. This drives both servers with a
seeded random corpus plus a fixed set of edge cases and fails on any difference in the
JSON-RPC responses, so validation rules, error wording, argument defaults, protocol
edge handling and export formatting cannot drift apart in ways nobody wrote down.

The corpus is deterministic: the seed defaults to 20261128 and `--seed` explores a
different one. Nothing here reaches the network. The argument pools hold only values
each server rejects before a lookup, `trace_route` runs with an empty PATH so it reports
"unavailable", and `health_score` — the one tool that dials 1.1.1.1 — is never
generated; `check-conformance.py` stubs that probe instead.

Usage: python3 Tools/test_parity.py [--seed N] [--count N]
"""

import argparse
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED = 20261128
DEFAULT_COUNT = 300

# Values that fail `dns_check`'s own check, so no name is ever resolved.
BAD_DOMAINS = ["", " ", "\t", "\n", "\r\n  ", 42, 1.5, True, None, [], {}, ["example.com"]]

# URLs both servers reject before a request is made: no scheme, no host, a scheme
# other than HTTP(S), credentials, or unparseable brackets. None of them can fetch.
BAD_URLS = [
    "", " ", ":", "http://", "https://", "http://[", "%%%",
    "ftp://example.com/dns-query", "file:///etc/passwd", "mailto:someone@example.com",
    "not a url", "data:text/plain,hi", "javascript:alert(1)", "//example.com/doh",
    "https://user:pw@example.com/", "https://user@example.com/",
    42, 1.5, True, None, [], {},
]

# The last two reach the trace and find no binary (empty PATH), so both must say
# "unavailable"; the rest fail validation.
DESTINATIONS = [
    "", " ", "\t", "\n", "\u00a0", "-oops", " -oops ", "two words", "a\x00b",
    42, 1.5, True, None, [], {}, "127.0.0.1", "example.com", "2001:db8::1",
]

FORMATS = ["json", "csv", "JSON", "CSV", "", "xml", None, 42, True, [], {}]

RESULTS = [
    {}, {"a": 1}, {"note": "a, b"}, {"line": "a\r\nb"}, {"quote": 'a "b"'},
    {"accent": "héllo"}, {"emoji": "🙂"}, {"none": None}, {"empty": ""},
    {"nested": {"hosts": ["1.1.1.1", "8.8.8.8"]}}, {"count": 2},
    [1, 2], "text", 42, None, True,
]

KNOWN_TOOLS = ["dns_check", "doh_test", "trace_route", "export_results"]
ODD_NAMES = ["", "nope", "tools/list", "dns_check ", 42, 1.5, None, True, [], {"name": "dns_check"}]
PROTOCOL_METHODS = [
    "initialize", "ping", "tools/list", "notifications/initialized",
    "does/not/exist", "Initialize", "",
]
PARAMS = [{}, None, [], "x", 42, {"cursor": "c"}, {"name": "dns_check", "arguments": {"domain": ""}}]
IDS = [1, "text-id", None, 1.5, -3, 10**12, {"a": 1}, [1, 2]]

# Fixed oddities every seed runs, so a change of seed never drops them.
EDGE_MESSAGES = [
    None, 42, 1.5, True, "text", [], {},
    {"jsonrpc": "2.0"},
    {"method": "ping"},
    {"jsonrpc": "1.0", "id": 1, "method": "ping"},
    {"jsonrpc": "2.0", "id": 1},
    {"jsonrpc": "2.0", "id": 1, "method": 42},
    {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []},
    {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": None},
    {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": 42},
    [{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
    [{}],
    {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "dns_check"}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": 42}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "json", "results": {"accent": "héllo"}}}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "csv", "results": {"accent": "héllo", "emoji": "🙂"}}}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "export_results", "arguments": {"format": "json", "results": None}}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "export_results", "arguments": None}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "trace_route", "arguments": {"destination": "a\x00b"}}},
    {"jsonrpc": "2.0", "id": "id", "method": "tools/call", "params": {"name": "dns_check", "arguments": {"domain": ""}}},
]

# Not JSON, or JSON that is not a request: both servers must answer each the same way.
MALFORMED_LINES = ["{not json", "{", "[]", "null", "123", '"text"', "true", "[{}]  "]


def load_conformance():
    """The conformance module, so both checks normalize and diff the same way."""
    path = Path(__file__).with_name("check-conformance.py")
    spec = importlib.util.spec_from_file_location("check_conformance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_arguments(rng, name):
    """Arguments for one known tool: mostly valid shapes, sometimes a hostile one."""
    if name == "dns_check":
        arguments = {"domain": rng.choice(BAD_DOMAINS)} if rng.random() < 0.9 else {}
    elif name == "doh_test":
        arguments = {"url": rng.choice(BAD_URLS)} if rng.random() < 0.9 else {}
    elif name == "trace_route":
        arguments = {"destination": rng.choice(DESTINATIONS)} if rng.random() < 0.9 else {}
    else:
        arguments = {}
        if rng.random() < 0.8:
            arguments["format"] = rng.choice(FORMATS)
        if rng.random() < 0.8:
            arguments["results"] = rng.choice(RESULTS)
    if rng.random() < 0.2:
        arguments[rng.choice(["verbose", "timeout", "", "name"])] = rng.choice([1, None, "x", True])
    if rng.random() < 0.1:
        return rng.choice([None, [], "text", 42])
    return arguments


def tool_call(rng, request_id):
    if rng.random() < 0.72:
        name = rng.choice(KNOWN_TOOLS)
        arguments = build_arguments(rng, name)
    else:
        name = rng.choice(ODD_NAMES)
        arguments = rng.choice([{}, {"domain": ""}, None, [], "x", 42])
    params = {"name": name}
    if arguments is not None or rng.random() < 0.5:
        params["arguments"] = arguments
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}


def protocol_request(rng):
    message = {"jsonrpc": "2.0", "id": rng.choice(IDS), "method": rng.choice(PROTOCOL_METHODS)}
    if rng.random() < 0.8:
        message["params"] = rng.choice(PARAMS)
    return message


def corpus(seed, count):
    """A fixed edge list followed by a seeded mix of tool calls, protocol calls and junk."""
    rng = random.Random(seed)
    messages = list(EDGE_MESSAGES)
    for index in range(count):
        roll = rng.random()
        if roll < 0.7:
            messages.append(tool_call(rng, 1000 + index))
        elif roll < 0.9:
            messages.append(protocol_request(rng))
        else:
            messages.append(rng.choice(EDGE_MESSAGES))
    return messages


def run_server(command, stdin, workdir):
    """Empty PATH: `trace_route` finds no traceroute, so it cannot touch the network."""
    return subprocess.run(command, input=stdin, capture_output=True, text=True, env={**os.environ, "PATH": str(workdir / "empty")}, timeout=180)


def compare(check, expected, actual):
    """Every response, in order, must match once volatile fields are normalized."""
    if len(expected) != len(actual):
        print(f"FAIL: server/index.py answered {len(expected)} responses, server/index.js answered {len(actual)}", file=sys.stderr)
        return False
    for index, (left, right) in enumerate(zip(expected, actual), start=1):
        if left != right:
            print(f"FAIL: response {index} (id {left.get('id')}) differs\n{check.diff_text(left, right)}", file=sys.stderr)
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"corpus seed (default {DEFAULT_SEED})")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"random requests after the edge list (default {DEFAULT_COUNT})")
    args = parser.parse_args()

    node = shutil.which("node")
    if node is None:
        sys.exit("node was not found on PATH, so the two servers cannot be compared")
    python_server = [sys.executable, str(REPO_ROOT / "server" / "index.py")]
    node_server = [node, str(REPO_ROOT / "server" / "index.js")]

    lines = [json.dumps(message) for message in corpus(args.seed, args.count)]
    stdin = "\n".join(lines + MALFORMED_LINES) + "\n"
    check = load_conformance()

    with tempfile.TemporaryDirectory() as temporary:
        workdir = Path(temporary)
        (workdir / "empty").mkdir()
        expected = check.normalize(check.responses(run_server(python_server, stdin, workdir)))
        actual = check.normalize(check.responses(run_server(node_server, stdin, workdir)))

    if not compare(check, expected, actual):
        sys.exit(f"1 differential mismatch (seed {args.seed}, {len(lines) + len(MALFORMED_LINES)} requests)")
    print(f"ok {len(expected)} responses match (seed {args.seed}, {len(lines) + len(MALFORMED_LINES)} requests)")


if __name__ == "__main__":
    main()
