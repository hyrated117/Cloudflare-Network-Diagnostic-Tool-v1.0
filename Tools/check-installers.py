#!/usr/bin/env python3
"""Regression check for the MCP installers.

Every installer must write config files whose "command" and first "args" entry
point at a real, absolute script that answers a JSON-RPC handshake. The
installers once wrote a relative "index.py", which MCP clients resolved
against their own working directory and could not launch.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HANDSHAKE = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
CLIENT_ENTRY = ("servers", "cloudflare-diagnostics")
failures = []


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    failures.append(message)


def check_config(label, path, keys=()):
    if not path.is_file():
        return fail(f"{label}: {path} was not written")
    entry = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        entry = entry[key]

    launcher, script = entry["command"], entry["args"][0]
    if not Path(script).is_absolute():
        return fail(f"{label}: args[0] must be an absolute path, got {script!r}")
    if not Path(script).is_file():
        return fail(f"{label}: args[0] does not exist: {script}")
    if not (shutil.which(launcher) or os.access(launcher, os.X_OK)):
        return fail(f"{label}: command is not executable: {launcher}")

    completed = subprocess.run(
        [launcher, script], input=HANDSHAKE, capture_output=True, text=True, timeout=20
    )
    if '"serverInfo"' not in completed.stdout:
        return fail(f"{label}: no initialize response from {launcher} {script}")
    print(f"ok {label}: {launcher} {script}")


def run_installer(label, command, workdir, client_config=True):
    home = workdir / label
    home.mkdir()
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return fail(f"{label}: installer exited {completed.returncode}: {completed.stderr.strip()}")

    config_dir = home / ".local" / "cloudflare-mcp" / "config"
    check_config(f"{label} server config", config_dir / "mcp-server.json")
    if client_config:
        check_config(f"{label} client config", config_dir / "mcp-client.json", CLIENT_ENTRY)


with tempfile.TemporaryDirectory() as tmp:
    workdir = Path(tmp)
    run_installer("install-mcp-server.sh", ["bash", "installers/install-mcp-server.sh"], workdir)
    run_installer("install-mcp-unified.sh", ["bash", "installers/install-mcp-unified.sh"], workdir)
    node = shutil.which("node")
    if node:
        run_installer("cli.js", [node, "installers/cli.js", "install"], workdir, client_config=False)

if failures:
    sys.exit(f"{len(failures)} installer check(s) failed")

print("All installer configs point at a launchable server")
