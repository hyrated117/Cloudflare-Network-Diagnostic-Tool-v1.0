#!/usr/bin/env python3
"""Differential test: both servers must answer a randomized corpus identically.

`Tools/check-conformance.py` pins 28 hand-written cases. That catches drift in the
behaviour someone thought to list, and nothing else. This drives both servers with a
seeded random corpus plus a fixed set of edge cases and fails on any difference in the
JSON-RPC responses, so validation rules, error wording, argument defaults, protocol
edge handling and export formatting cannot drift apart in ways nobody wrote down.

The corpus is deterministic: the seed defaults to 20261128 and `--seed` explores a
different one. Nothing here reaches the network, but the success and error paths that
normally need one are compared too: name resolution is stubbed in both runtimes from one
table (A, AAAA, both, neither), DoH is served by a loopback fixture (200, 404, 503, a
redirect, empty, non-JSON, over the 64 KiB cap), `trace_route` runs with an empty PATH so
it reports "unavailable", and `health_score` — which dials 1.1.1.1 — is not generated;
`check-conformance.py` stubs that probe and asserts both documented scores instead.

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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

# Name resolution is stubbed in both runtimes from this table, so no query leaves the box.
DNS_TABLE = {
    "a.parity.test": {"v4": ["192.0.2.1"], "v6": []},
    "aaaa.parity.test": {"v4": [], "v6": ["2001:db8::1"]},
    "dual.parity.test": {"v4": ["192.0.2.9", "192.0.2.2"], "v6": ["2001:db8::9"]},
    "missing.parity.test": {"v4": [], "v6": []},
}

# DoH is served by the loopback fixture in main(); the port is filled in by main() too.
DOH_PORT_PLACEHOLDER = "DOH_PORT"
DOH_BASE = f"http://127.0.0.1:{DOH_PORT_PLACEHOLDER}"
DOH_PATHS = ["/ok", "/unicode", "/text", "/long-text", "/empty", "/missing", "/error", "/redirect", "/over"]
DOH_OVER_CAP = 65537
DOH_REDIRECTS = {"/redirect": "/ok"}
DOH_BODIES = {
    "/ok": (200, '{"Status":0,"Answer":[{"name":"dual.parity.test.","type":1,"TTL":60,"data":"192.0.2.9"}]}'),
    "/unicode": (200, '{"Status":0,"note":"héllo 🙂"}'),
    "/text": (200, "parity fixture: not JSON"),
    "/long-text": (200, "x" * 5000),
    "/empty": (200, ""),
    "/missing": (404, '{"Status":3}'),
    "/error": (503, '{"Status":2}'),
    "/over": (200, "x" * DOH_OVER_CAP),
}
DNS_VALUES = BAD_DOMAINS + list(DNS_TABLE)
URL_VALUES = BAD_URLS + [DOH_BASE + path for path in DOH_PATHS]

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

# Every stub outcome, so no seed can skip one.
NETWORK_REQUESTS = [
    {"jsonrpc": "2.0", "id": f"dns:{host}", "method": "tools/call", "params": {"name": "dns_check", "arguments": {"domain": host}}}
    for host in DNS_TABLE
] + [
    {"jsonrpc": "2.0", "id": f"doh:{path}", "method": "tools/call", "params": {"name": "doh_test", "arguments": {"url": DOH_BASE + path}}}
    for path in DOH_PATHS
]

# Answer name resolution from DNS_TABLE in both runtimes; an unknown host is an error,
# never a real lookup, so a typo in a pool cannot reach the network.
PYTHON_DNS_STUB = '''\
"""Answer `dns_check` for Tools/test_parity.py from its table; never resolve for real."""
import ipaddress
import socket

TABLE = %s
_original = socket.getaddrinfo


def getaddrinfo(host, port, *args, **kwargs):
    entry = TABLE.get(host)
    if entry is None:
        try:
            ipaddress.ip_address(str(host))
        except ValueError:
            raise socket.gaierror("parity.test stub: unknown host " + str(host))
        return _original(host, port, *args, **kwargs)
    if not entry["v4"] and not entry["v6"]:
        raise socket.gaierror(str(host) + " not found")
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0)) for address in entry["v4"]]
    answers += [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, 0, 0, 0)) for address in entry["v6"]]
    return answers


socket.getaddrinfo = getaddrinfo
''' % json.dumps(DNS_TABLE, indent=4)

NODE_DNS_STUB = """\
'use strict';
// Answer `dns_check` for Tools/test_parity.py from its table; never resolve for real.
const dns = require('node:dns');
const table = %s;

const resolve = (family) => async (host) => {
  const entry = table[host];
  if (!entry) throw new Error(`parity.test stub: unknown host ${host}`);
  if (!entry[family].length) throw new Error(`${host} not found`);
  return entry[family];
};

dns.promises.resolve4 = resolve('v4');
dns.promises.resolve6 = resolve('v6');
""" % json.dumps(DNS_TABLE)


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
        arguments = {"domain": rng.choice(DNS_VALUES)} if rng.random() < 0.9 else {}
    elif name == "doh_test":
        arguments = {"url": rng.choice(URL_VALUES)} if rng.random() < 0.9 else {}
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
    messages = list(EDGE_MESSAGES) + list(NETWORK_REQUESTS)
    for index in range(count):
        roll = rng.random()
        if roll < 0.7:
            messages.append(tool_call(rng, 1000 + index))
        elif roll < 0.9:
            messages.append(protocol_request(rng))
        else:
            messages.append(rng.choice(EDGE_MESSAGES))
    return messages


class DohFixtureHandler(BaseHTTPRequestHandler):
    """Serve the DoH outcomes in DOH_BODIES, and one redirect, on loopback."""

    def do_GET(self):
        if self.path in DOH_REDIRECTS:
            self.send_response(302)
            self.send_header("Location", DOH_REDIRECTS[self.path])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path not in DOH_BODIES:
            return self.send_error(404)
        status, text = DOH_BODIES[self.path]
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_fixture():
    server = ThreadingHTTPServer(("127.0.0.1", 0), DohFixtureHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def build_env(workdir):
    """Stub name resolution, keep the fixture off any proxy, and hide every binary."""
    env = {**os.environ}
    env["PATH"] = str(workdir / "empty")
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(workdir / "python"), env.get("PYTHONPATH"))))
    env["NODE_OPTIONS"] = " ".join(filter(None, (env.get("NODE_OPTIONS"), f'--require "{workdir / "node-dns-stub.cjs"}"')))
    return env


def run_server(command, stdin, env):
    return subprocess.run(command, input=stdin, capture_output=True, text=True, env=env, timeout=180)


def check_outcomes(label, normalized):
    """The stubbed outcomes must be the documented ones, not merely equal."""
    results = {response["id"]: (response.get("result") or {}).get("structuredContent") for response in normalized if isinstance(response.get("id"), str)}
    problems = []

    def expect(key, fields):
        result = results.get(key) or {}
        actual = {field: result.get(field) for field in fields}
        if actual != fields:
            problems.append(f"{label}: {key} returned {actual}, expected {fields}")

    expect("dns:a.parity.test", {"status": "ok", "addresses": ["192.0.2.1"]})
    expect("dns:aaaa.parity.test", {"status": "ok", "addresses": ["2001:db8::1"]})
    expect("dns:dual.parity.test", {"status": "ok", "addresses": ["192.0.2.2", "192.0.2.9", "2001:db8::9"]})
    expect("dns:missing.parity.test", {"status": "error", "addresses": [], "error": "missing.parity.test not found"})
    expect("doh:/ok", {"status": "ok", "statusCode": 200, "response": {"Status": 0, "Answer": [{"name": "dual.parity.test.", "type": 1, "TTL": 60, "data": "192.0.2.9"}]}})
    expect("doh:/unicode", {"status": "ok", "statusCode": 200, "response": {"Status": 0, "note": "héllo 🙂"}})
    expect("doh:/text", {"status": "ok", "statusCode": 200, "response": {"raw": "parity fixture: not JSON"}})
    expect("doh:/empty", {"status": "ok", "statusCode": 200, "response": {"raw": ""}})
    expect("doh:/missing", {"status": "error", "statusCode": 404, "response": {"Status": 3}})
    expect("doh:/error", {"status": "error", "statusCode": 503, "response": {"Status": 2}})
    expect("doh:/redirect", {"status": "ok", "statusCode": 200})
    expect("doh:/over", {"status": "error", "statusCode": 200, "error": "DoH response exceeded 64 KiB limit"})
    long_raw = (results.get("doh:/long-text") or {}).get("response", {}).get("raw")
    if long_raw != "x" * 4096:
        problems.append(f"{label}: doh:/long-text kept {len(long_raw) if isinstance(long_raw, str) else 'no'} raw characters, expected 4096")
    return problems


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
    check = load_conformance()
    fixture = start_fixture()

    try:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "empty").mkdir()
            (workdir / "python").mkdir()
            (workdir / "python" / "sitecustomize.py").write_text(PYTHON_DNS_STUB, encoding="utf-8")
            (workdir / "node-dns-stub.cjs").write_text(NODE_DNS_STUB, encoding="utf-8")
            env = build_env(workdir)
            stdin = "\n".join(lines + MALFORMED_LINES) + "\n"
            stdin = stdin.replace(DOH_PORT_PLACEHOLDER, str(fixture.server_address[1]))
            expected = check.normalize(check.responses(run_server(python_server, stdin, env)))
            actual = check.normalize(check.responses(run_server(node_server, stdin, env)))
            problems = check_outcomes("server/index.py", expected) + check_outcomes("server/index.js", actual)
    finally:
        fixture.shutdown()
        fixture.server_close()

    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    if not compare(check, expected, actual) or problems:
        sys.exit(f"1 differential mismatch (seed {args.seed}, {len(lines) + len(MALFORMED_LINES)} requests)")
    print(f"ok {len(expected)} responses match (seed {args.seed}, {len(lines) + len(MALFORMED_LINES)} requests)")


if __name__ == "__main__":
    main()
