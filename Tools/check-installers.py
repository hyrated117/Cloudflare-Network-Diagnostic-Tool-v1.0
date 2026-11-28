#!/usr/bin/env python3
"""Regression check for the MCP installers.

Every installer must write config files whose "command" and first "args" entry
point at a real, absolute script that answers a JSON-RPC session. The installers
once wrote a relative "index.py", which MCP clients resolved against their own
working directory and could not launch.

By default the installers in this repository are checked. Pass --installers-root
to check the copy inside an extracted release archive instead:

    python3 Tools/check-archive.py dist/v1.0.0/mcp-installer-pack.tar.gz --extract-to dist/pack
    python3 Tools/check-installers.py --installers-root dist/pack
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENT_ENTRY = ("servers", "cloudflare-diagnostics")
PROTOCOL = "2024-11-05"
EXPECTED_TOOLS = ["dns_check", "doh_test", "trace_route", "health_score", "export_results"]
SESSION = "".join(
    json.dumps(message) + "\n"
    for message in (
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "check-installers", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "ping"},
    )
)

tree_root = REPO_ROOT
failures = []


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    failures.append(message)


def handshake(label, launcher, script):
    completed = subprocess.run(
        [launcher, script], input=SESSION, capture_output=True, text=True, timeout=30
    )
    replies = {}
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in message:
            replies[message["id"]] = message

    result = replies.get(1, {}).get("result") or {}
    if result.get("protocolVersion") != PROTOCOL:
        return fail(
            f"{label}: answered protocol {result.get('protocolVersion')!r}, expected {PROTOCOL}"
        )
    tools = sorted(
        tool.get("name") for tool in (replies.get(2, {}).get("result") or {}).get("tools", [])
    )
    if tools != sorted(EXPECTED_TOOLS):
        return fail(f"{label}: tools/list returned {tools}, expected {EXPECTED_TOOLS}")
    if "result" not in replies.get(3, {}):
        return fail(f"{label}: ping failed")
    print(f"ok {label}: {launcher} {script} ({len(tools)} tools)")


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

    handshake(label, launcher, script)


def run_installer(label, command, workdir, client_config=True):
    home = workdir / label
    home.mkdir()
    completed = subprocess.run(
        command,
        cwd=tree_root,
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


def main():
    global tree_root

    parser = argparse.ArgumentParser(description="Check that the installers write launchable configs.")
    parser.add_argument(
        "--installers-root",
        metavar="DIR",
        help="check the installers in this tree, for example an extracted release archive",
    )
    args = parser.parse_args()

    if args.installers_root:
        tree_root = Path(args.installers_root).resolve()
    if not (tree_root / "installers").is_dir():
        print(f"FAIL: {tree_root} has no installers directory", file=sys.stderr)
        return 1
    print(f"checking installers in {tree_root}")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        run_installer("install-mcp-server.sh", ["bash", "installers/install-mcp-server.sh"], workdir)
        run_installer("install-mcp-unified.sh", ["bash", "installers/install-mcp-unified.sh"], workdir)
        run_installer(
            "install-mcp-server.py", [sys.executable, "installers/install-mcp-server.py"], workdir
        )
        node = shutil.which("node")
        if node:
            run_installer("cli.js", [node, "installers/cli.js", "install"], workdir, client_config=False)

    if failures:
        print(f"{len(failures)} installer check(s) failed", file=sys.stderr)
        return 1
    print("All installer configs point at a launchable server")
    return 0


if __name__ == "__main__":
    sys.exit(main())
