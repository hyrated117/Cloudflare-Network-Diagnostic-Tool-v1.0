#!/usr/bin/env python3
"""Test the Windows branch of `trace_route` without Windows.

Both servers pick `tracert` only when the platform is Windows, so on Linux — which is
where every pull request is validated — the command shape the Windows CI job runs is
never exercised until that job starts. This test forces the branch and puts a fake
`tracert` on `PATH`, so it runs on every pull request with no network:

- a shim that prints a real three-line `tracert` transcript must make both servers return
  `status: ok` with the destination in the output, and must be invoked as exactly
  `tracert -d -h 15 -w 300 <destination>` — the flags bound reverse DNS and the run;
- a shim that exits 1 with the message Windows writes when the route fails must surface
  as `status: error` in both servers, with Python's `returnCode: 1` and Node's `error`
  carrying the text;
- with no `tracert` on `PATH` at all, both servers must say `unavailable` rather than
  claim a trace.

What it does not prove, and the Windows job still has to: a real `tracert` on a real
Windows host, Windows PowerShell 5.1 parsing the installers, and the runner's own
`pwsh`. `Validate` runs this as `Test the Windows tracert branch`.

    python3 Tools/test_windows_trace_route.py

Stdlib plus node, which `Validate` sets up.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_PY = ROOT / "server" / "index.py"
SERVER_JS = ROOT / "server" / "index.js"
DESTINATION = "127.0.0.1"
EXPECTED_ARGV = ["-d", "-h", "15", "-w", "300", DESTINATION]
GOOD_OUTPUT = (
    "Tracing route to 127.0.0.1 over a maximum of 15 hops\n"
    "  1     0 ms     0 ms     0 ms  127.0.0.1\n"
    "Trace complete."
)
FAILURE_TEXT = "tracert: write error: The semaphore timeout period has expired."

failures = []


def expect(condition, label, detail=""):
    if condition:
        print(f"ok {label}")
    else:
        failures.append(f"{label}{': ' + detail if detail else ''}")
        print(f"FAIL {label}{': ' + detail if detail else ''}", file=sys.stderr)


def shim(directory, body):
    path = directory / "tracert"
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def trace_with_python(platform="win32"):
    """`trace_route` from the Python server, with the platform forced for the call."""
    spec = importlib.util.spec_from_file_location("diagnostic_server", SERVER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = sys.platform
    sys.platform = platform
    try:
        return module.DiagnosticServer().trace_route(DESTINATION)
    finally:
        sys.platform = original


def trace_with_node(directory):
    harness = directory / "harness.mjs"
    harness.write_text(
        "import DiagnosticServer from "
        + json.dumps(SERVER_JS.as_uri())
        + ";\n"
        "Object.defineProperty(process, 'platform', { value: 'win32' });\n"
        "const result = await new DiagnosticServer().traceRoute("
        + json.dumps(DESTINATION)
        + ");\n"
        "process.stdout.write(JSON.stringify(result));\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(harness)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"node harness exited {completed.returncode}: {completed.stderr.strip()[:400]}"
        )
    return json.loads(completed.stdout)


def main():
    if shutil.which("node") is None:
        print("FAIL: node is not on PATH; Validate sets it up", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        bindir = directory / "bin"
        bindir.mkdir()
        log = directory / "argv.log"
        original_path = os.environ["PATH"]

        # 1. A working tracert: both servers trace, with the Windows flags.
        shim(
            bindir,
            'echo "$@" >> ' + str(log) + "\ncat <<'OUT'\n" + GOOD_OUTPUT + "\nOUT",
        )
        os.environ["PATH"] = f"{bindir}{os.pathsep}{original_path}"
        try:
            python_ok = trace_with_python()
            node_ok = trace_with_node(directory)
        finally:
            os.environ["PATH"] = original_path
        argv_calls = [line.strip() for line in log.read_text(encoding="utf-8").splitlines()]
        expect(
            len(argv_calls) == 2 and all(call == " ".join(EXPECTED_ARGV) for call in argv_calls),
            "both servers invoke tracert with the Windows flags",
            f"argv was {argv_calls}",
        )
        expect(
            python_ok.get("status") == "ok" and python_ok.get("returnCode") == 0,
            "python trace succeeds",
            json.dumps(python_ok),
        )
        expect(
            DESTINATION in python_ok.get("output", ""),
            "python output mentions the destination",
            json.dumps(python_ok),
        )
        expect(
            node_ok.get("status") == "ok" and DESTINATION in node_ok.get("output", ""),
            "node trace succeeds",
            json.dumps(node_ok),
        )

        # 2. A tracert that fails: both servers report the failure, not a trace.
        shim(bindir, f'echo "{FAILURE_TEXT}" >&2\nexit 1')
        os.environ["PATH"] = f"{bindir}{os.pathsep}{original_path}"
        try:
            python_failed = trace_with_python()
            node_failed = trace_with_node(directory)
        finally:
            os.environ["PATH"] = original_path
        expect(
            python_failed.get("status") == "error" and python_failed.get("returnCode") == 1,
            "python reports the failed trace",
            json.dumps(python_failed),
        )
        expect(
            FAILURE_TEXT in python_failed.get("output", ""),
            "python surfaces tracert's message",
            json.dumps(python_failed),
        )
        expect(
            node_failed.get("status") == "error" and FAILURE_TEXT in node_failed.get("error", ""),
            "node reports the failed trace with its message",
            json.dumps(node_failed),
        )

        # 3. No tracert at all: both say unavailable rather than inventing a trace.
        (bindir / "tracert").unlink()
        os.environ["PATH"] = f"{bindir}{os.pathsep}{original_path}"
        try:
            python_missing = trace_with_python()
            node_missing = trace_with_node(directory)
        finally:
            os.environ["PATH"] = original_path
        expect(
            python_missing.get("status") == "unavailable"
            and node_missing.get("status") == "unavailable",
            "both servers say unavailable when tracert is missing",
            f"{json.dumps(python_missing)} / {json.dumps(node_missing)}",
        )

    if failures:
        print(f"{len(failures)} failure(s)", file=sys.stderr)
        return 1
    print("Windows tracert branch: both servers build the flags and report all three outcomes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
