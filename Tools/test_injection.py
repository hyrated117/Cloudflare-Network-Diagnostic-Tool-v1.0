#!/usr/bin/env python3
"""Hostile destinations and domains must reach argv and the resolver as data.

`trace_route` builds a command line and `dns_check` resolves a name, both from
caller-supplied strings. This drives each server with values built to look like flags
(`-n`, `--help`, a trailing `-n 1`) and like shell code (`;`, `&&`, `|`, `$(...)`,
backticks, `${IFS}` instead of a space), then inspects what actually happened:

- a fake `traceroute` at the front of `PATH` records its exact argv, so a value that
  reached the command line can be seen as one argument, never split into flags;
- resolver stubs in both runtimes record the host they were asked for, so a domain that
  is looked up can be seen arriving as one literal string, not something a shell expanded;
- every payload aims a `touch` at a marker file in a temporary directory, and the test
  fails if that file appears.

Rejected values must produce the server's validation error and no argv; accepted ones
must arrive as exactly `traceroute <value>`, with no extra argument, and leave no marker.
A domain that is not a valid hostname is refused by both servers before the resolver is
asked, so a hostile string cannot become a lookup either.
On Linux `traceroute` is invoked without
fixed flags, which is why one argument is expected here; the Windows `tracert` shape is
covered by `Tools/test_windows_trace_route.py`. Nothing here needs a network.

Usage: python3 Tools/test_injection.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (destination, "reject" when the server must refuse it, "exec" when it is safe to pass).
# Values with no whitespace survive validation, so their safety rests on argv, not checks.
DESTINATIONS = [
    ("-n 10.0.0.1", "reject"),
    ("--help", "reject"),
    (" -n ", "reject"),
    ("127.0.0.1 -n 1", "reject"),
    ("127.0.0.1\n-n 1", "reject"),
    ("127.0.0.1\t-n", "reject"),
    ("127.0.0.1\x00-n", "reject"),
    ("127.0.0.1", "exec"),
    ("$(touch${IFS}MARKER)", "exec"),
    ("`touch${IFS}MARKER`", "exec"),
    ("127.0.0.1;touch${IFS}MARKER", "exec"),
    ("127.0.0.1&&touch${IFS}MARKER", "exec"),
    ("127.0.0.1|tee${IFS}MARKER", "exec"),
    ("127.0.0.1>MARKER", "exec"),
]

EXECUTED = sum(1 for _, expectation in DESTINATIONS if expectation == "exec")

# (domain, "reject" for a protocol error, "invalid" for a tool-level hostname refusal,
# "lookup" when it must reach the resolver). No flag- or shell-shaped string is a legal
# hostname, so those are refused before any lookup.
DOMAINS = [
    ("", "reject"),
    (" ", "reject"),
    ("\t", "reject"),
    ("example.com", "lookup"),
    ("-n", "invalid"),
    ("--help", "invalid"),
    ("$(touch${IFS}MARKER)", "invalid"),
    ("`touch${IFS}MARKER`", "invalid"),
    ("example.com;touch${IFS}MARKER", "invalid"),
    ("example.com&&touch${IFS}MARKER", "invalid"),
]

PYTHON_RESOLVER_STUB = '''\
"""Record every name `dns_check` asks for, then answer it from a fixed address."""
import json
import os
import socket

LOG = os.environ["INJECTION_DNS_LOG"]


def getaddrinfo(host, port, *args, **kwargs):
    with open(LOG, "a", encoding="utf-8") as log:
        log.write(json.dumps(str(host)) + "\\n")
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.55", 0))]


socket.getaddrinfo = getaddrinfo
'''

NODE_RESOLVER_STUB = """\
'use strict';
// Record every name `dns_check` asks for, then answer it from a fixed address.
const fs = require('node:fs');
const dns = require('node:dns');
const log = process.env.INJECTION_DNS_LOG;

const record = (host) => fs.appendFileSync(log, JSON.stringify(String(host)) + '\\n');

dns.promises.resolve4 = async (host) => {
  record(host);
  return ['192.0.2.55'];
};
dns.promises.resolve6 = async (host) => {
  record(host);
  return [];
};
"""

# A traceroute that only records how it was invoked; it never touches the network.
FAKE_TRACEROUTE = """\
#!{python}
import json
import os
import sys

with open(os.environ["INJECTION_TRACE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
print("fake trace for " + (sys.argv[-1] if len(sys.argv) > 1 else "nothing"))
"""


def requests_for(marker):
    messages = []
    for index, (value, _) in enumerate(DESTINATIONS):
        messages.append({
            "jsonrpc": "2.0",
            "id": f"trace:{index}",
            "method": "tools/call",
            "params": {"name": "trace_route", "arguments": {"destination": value.replace("MARKER", marker)}},
        })
    for index, (value, _) in enumerate(DOMAINS):
        messages.append({
            "jsonrpc": "2.0",
            "id": f"dns:{index}",
            "method": "tools/call",
            "params": {"name": "dns_check", "arguments": {"domain": value.replace("MARKER", marker)}},
        })
    return messages


def responses(completed):
    """By id, so the checks can name the payload that misbehaved."""
    return {json.loads(line)["id"]: json.loads(line) for line in completed.stdout.splitlines() if line.strip()}


def read_json_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def failure(label, message):
    return f"{label}: {message}"


def check_server(label, completed, trace_log, dns_log, marker):
    problems = []
    answers = responses(completed)
    argv_lines = read_json_lines(trace_log)
    lookups = read_json_lines(dns_log)

    for index, (value, expectation) in enumerate(DESTINATIONS):
        filled = value.replace("MARKER", marker)
        response = answers.get(f"trace:{index}") or {}
        error = (response.get("error") or {}).get("message", "")
        result = (response.get("result") or {}).get("structuredContent") or {}
        if expectation == "reject":
            if response.get("error") is None:
                problems.append(failure(label, f"destination {value!r} was not refused: {str(result)[:120]}"))
            elif "destination must be" not in error:
                problems.append(failure(label, f"destination {value!r} was refused with {error!r}"))
            if [filled] in argv_lines:
                problems.append(failure(label, f"destination {value!r} reached argv"))
        else:
            if response.get("error") is not None:
                problems.append(failure(label, f"destination {value!r} was refused with {error!r}"))
            elif result.get("status") != "ok":
                problems.append(failure(label, f"destination {value!r} returned {str(result)[:120]}"))
            if [filled] not in argv_lines:
                problems.append(failure(label, f"destination {value!r} was not passed as one argument"))

    for argv in argv_lines:
        if len(argv) != 1 or argv[0].startswith("-"):
            problems.append(failure(label, f"traceroute received {argv!r}, expected exactly one non-flag argument"))

    for index, (value, expectation) in enumerate(DOMAINS):
        filled = value.replace("MARKER", marker)
        response = answers.get(f"dns:{index}") or {}
        error = (response.get("error") or {}).get("message", "")
        if expectation == "reject":
            if response.get("error") is None:
                problems.append(failure(label, f"domain {value!r} was not refused"))
            elif "domain must be" not in error:
                problems.append(failure(label, f"domain {value!r} was refused with {error!r}"))
            if filled in lookups:
                problems.append(failure(label, f"domain {value!r} reached the resolver"))
        elif expectation == "invalid":
            result = (response.get("result") or {}).get("structuredContent") or {}
            if result.get("error") != "domain is not a valid hostname":
                problems.append(failure(label, f"domain {value!r} returned {str(result)[:120]}"))
            if result.get("domain") != filled:
                problems.append(failure(label, f"domain {value!r} echoed {result.get('domain')!r}"))
            if filled in lookups:
                problems.append(failure(label, f"domain {value!r} reached the resolver"))
        else:
            if response.get("error") is not None:
                problems.append(failure(label, f"domain {value!r} was refused with {error!r}"))
            if filled not in lookups:
                problems.append(failure(label, f"domain {value!r} did not reach the resolver as one name"))
            result = (response.get("result") or {}).get("structuredContent") or {}
            if result.get("addresses") != ["192.0.2.55"]:
                problems.append(failure(label, f"domain {value!r} returned {str(result)[:120]}"))

    if Path(marker).exists():
        problems.append(failure(label, "a payload created the marker file, so something ran it as a command"))
    if len(argv_lines) != EXECUTED:
        problems.append(failure(label, f"traceroute ran {len(argv_lines)} time(s), expected {EXECUTED}"))
    return problems


def build_env(workdir, trace_log, dns_log):
    env = {**os.environ}
    # `/usr/bin` and `/bin` stay on PATH so a payload that did reach a shell could still
    # create the marker; an empty PATH would hide that failure instead of catching it.
    env["PATH"] = os.pathsep.join((str(workdir / "bin"), "/usr/bin", "/bin"))
    env["PYTHONPATH"] = os.pathsep.join((str(workdir / "python"), env.get("PYTHONPATH", "")))
    env["NODE_OPTIONS"] = " ".join(filter(None, (env.get("NODE_OPTIONS"), f'--require "{workdir / "node-resolver-stub.cjs"}"')))
    env["INJECTION_TRACE_LOG"] = str(trace_log)
    env["INJECTION_DNS_LOG"] = str(dns_log)
    return env


def main():
    node = shutil.which("node")
    if node is None:
        sys.exit("node was not found on PATH, so neither server can be tested")
    problems = []
    with tempfile.TemporaryDirectory() as temporary:
        workdir = Path(temporary)
        for directory in ("bin", "python"):
            (workdir / directory).mkdir()
        marker = str(workdir / "marker")
        (workdir / "python" / "sitecustomize.py").write_text(PYTHON_RESOLVER_STUB, encoding="utf-8")
        (workdir / "node-resolver-stub.cjs").write_text(NODE_RESOLVER_STUB, encoding="utf-8")
        fake = workdir / "bin" / "traceroute"
        fake.write_text(FAKE_TRACEROUTE.replace("{python}", sys.executable), encoding="utf-8")
        fake.chmod(0o755)

        stdin = "\n".join(json.dumps(message) for message in requests_for(marker)) + "\n"
        for label, command in (
            ("server/index.py", [sys.executable, str(REPO_ROOT / "server" / "index.py")]),
            ("server/index.js", [node, str(REPO_ROOT / "server" / "index.js")]),
        ):
            trace_log = workdir / f"trace-{label.replace('/', '-')}.jsonl"
            dns_log = workdir / f"dns-{label.replace('/', '-')}.jsonl"
            completed = subprocess.run(command, input=stdin, capture_output=True, text=True, env=build_env(workdir, trace_log, dns_log), timeout=120)
            problems += check_server(label, completed, trace_log, dns_log, marker)

    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} injection check(s) failed")
    print(f"ok {len(DESTINATIONS)} destinations and {len(DOMAINS)} domains stay data on both servers")


if __name__ == "__main__":
    main()
