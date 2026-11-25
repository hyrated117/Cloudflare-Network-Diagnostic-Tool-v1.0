#!/usr/bin/env python3
"""Verify that the release archive installs and launches the server.

Takes an mcp-installer-pack.tar.gz (see Tools/build-package.sh), checks that it
carries the files a release needs and nothing generated, extracts it, runs the
unified installer with a temporary HOME, then launches the installed server from the
generated client config and speaks JSON-RPC to it.

Run it on every push so packaging breakage fails there instead of at tag time.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REQUIRED_ENTRIES = ("LICENSE", "README.md", "installers/", "server/", "docs/")
JUNK = ("__pycache__/", "node_modules/", ".git/", ".DS_Store")
EXPECTED_TOOLS = ["dns_check", "doh_test", "trace_route", "health_score", "export_results"]
PROTOCOL = "2024-11-05"
INSTALLED_FILES = (
    "config/mcp-server.json",
    "config/mcp-client.json",
    "server/python/index.py",
    "server/node/index.js",
    "server/node/package.json",
)


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def archive_names(archive):
    with tarfile.open(archive) as tar:
        return tar.getnames()


def check_entries(archive):
    names = archive_names(archive)
    for required in REQUIRED_ENTRIES:
        if not any(name == required or name.startswith(required) for name in names):
            fail(f"archive is missing {required}")
    if not any(name == "installers/install-mcp-unified.sh" for name in names):
        fail("archive is missing installers/install-mcp-unified.sh")
    junk = [name for name in names if any(marker in name for marker in JUNK)]
    if junk:
        fail(f"archive carries generated files: {junk[:3]}")
    print(f"archive: {len(names)} entries, required files present, no build junk")


def extract(archive, destination):
    with tarfile.open(archive) as tar:
        try:
            tar.extractall(destination, filter="data")
        except TypeError:  # Python < 3.12
            tar.extractall(destination)


def install(pack_dir, home):
    installer = pack_dir / "installers" / "install-mcp-unified.sh"
    result = subprocess.run(
        ["bash", str(installer)],
        env=dict(os.environ, HOME=str(home)),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(
            f"installer exited {result.returncode}\n"
            f"--- stdout ---\n{result.stdout[-2000:]}\n--- stderr ---\n{result.stderr[-2000:]}"
        )
    install_dir = home / ".local" / "cloudflare-mcp"
    missing = [name for name in INSTALLED_FILES if not (install_dir / name).is_file()]
    if missing:
        fail(f"installer did not create: {', '.join(missing)}")
    print(f"installer: exit 0, {len(INSTALLED_FILES)} expected files in {install_dir}")


def load_entry(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    entry = config if "command" in config and "args" in config else None
    if entry is None:
        for value in config.values():
            if isinstance(value, dict) and "command" in value and "args" in value:
                entry = value
                break
    if entry is None:
        fail(f"{config_path} has no command/args entry")
    command, script = entry["command"], entry["args"][0]
    if not os.path.isabs(script):
        fail(f"{config_path} points at a relative script: {script}")
    if not Path(script).is_file():
        fail(f"{config_path} points at a missing script: {script}")
    if not (os.path.isabs(command) and Path(command).exists()):
        fail(f"{config_path} points at a missing command: {command}")
    return entry


def handshake(entry, label):
    process = subprocess.Popen(
        [entry["command"]] + entry["args"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, **(entry.get("env") or {})),
    )

    def call(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            process.kill()
            fail(f"{label}: no reply to {message.get('method')}; stderr: {process.stderr.read()[:400]}")
        return json.loads(line)

    try:
        reply = call(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "check-package", "version": "0"},
                },
            }
        )
        result = reply.get("result") or {}
        if result.get("protocolVersion") != PROTOCOL:
            fail(f"{label}: answered protocol {result.get('protocolVersion')!r}, expected {PROTOCOL}")

        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        reply = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = sorted(tool["name"] for tool in reply["result"]["tools"])
        if tools != sorted(EXPECTED_TOOLS):
            fail(f"{label}: tools/list returned {tools}, expected {EXPECTED_TOOLS}")

        reply = call({"jsonrpc": "2.0", "id": 3, "method": "ping"})
        if "result" not in reply:
            fail(f"{label}: ping failed: {reply}")
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        process.wait(timeout=15)

    if process.returncode not in (0, None):
        fail(f"{label}: server exited with {process.returncode}")
    print(f"{label}: initialize {result['serverInfo']['name']} {result['serverInfo'].get('version')}, "
          f"{len(tools)} tools, ping ok")


def main():
    if len(sys.argv) != 2:
        print("usage: check-package.py <mcp-installer-pack.tar.gz>", file=sys.stderr)
        return 2
    if os.name == "nt":
        fail("this check needs bash; run it on Linux or macOS (Windows has Tools/check-installers.ps1)")

    archive = Path(sys.argv[1]).resolve()
    if not archive.is_file():
        fail(f"archive not found: {archive}")

    check_entries(archive)
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        pack_dir, home = temp / "pack", temp / "home"
        pack_dir.mkdir()
        home.mkdir()
        extract(archive, pack_dir)
        install(pack_dir, home)
        handshake(load_entry(home / ".local/cloudflare-mcp/config/mcp-server.json"), "python server")

        node = shutil.which("node")
        if node is None:
            print("node server: skipped, no node on PATH")
        else:
            node_entry = {
                "command": node,
                "args": [str(home / ".local/cloudflare-mcp/server/node/index.js")],
            }
            handshake(node_entry, "node server")

    print("release package: installs and launches from the extracted archive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
