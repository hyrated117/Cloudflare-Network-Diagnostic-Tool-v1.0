#!/usr/bin/env python3
"""Install the Python MCP server and configuration files."""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

VERSION = "1.0.1"
PROJECT_NAME = "Cloudflare Network Diagnostic Tool"


class MCPInstaller:
    def __init__(self, install_dir=None):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.install_dir = (
            Path(install_dir).expanduser().resolve()
            if install_dir
            else Path.home() / ".local" / "cloudflare-mcp"
        )
        self.server_dir = self.install_dir / "server"
        self.config_dir = self.install_dir / "config"
        self.log_file = self.install_dir / "install.log"

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{timestamp}] [{level}] {message}"
        print(msg, file=sys.stderr if level == "ERROR" else sys.stdout)
        self.install_dir.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as log_file:
            log_file.write(msg + "\n")

    def install(self):
        if sys.version_info < (3, 8):
            self.log("Python 3.8+ is required", "ERROR")
            return 1

        source = self.repo_root / "server" / "index.py"
        if not source.is_file():
            self.log(f"Server file not found: {source}", "ERROR")
            return 1

        try:
            self.server_dir.mkdir(parents=True, exist_ok=True)
            self.config_dir.mkdir(parents=True, exist_ok=True)
            destination = self.server_dir / "index.py"
            shutil.copy2(source, destination)
            if sys.platform != "win32":
                destination.chmod(0o755)

            server_config = {
                "name": PROJECT_NAME,
                "version": VERSION,
                "description": "MCP server for Cloudflare network diagnostics",
                "type": "stdio",
                "command": sys.executable,
                "args": [str(destination)],
                "env": {"PYTHONUNBUFFERED": "1"},
            }
            (self.config_dir / "mcp-server.json").write_text(
                json.dumps(server_config, indent=2) + "\n", encoding="utf-8"
            )
            client_config = {
                "name": "Cloudflare Diagnostic Client",
                "version": VERSION,
                "description": "MCP Client configuration for Cloudflare Network Diagnostic Tool",
                "servers": {
                    "cloudflare-diagnostics": {
                        "command": sys.executable,
                        "args": [str(destination)],
                        "env": {"PYTHONUNBUFFERED": "1"},
                    }
                },
            }
            (self.config_dir / "mcp-client.json").write_text(
                json.dumps(client_config, indent=2) + "\n", encoding="utf-8"
            )
            self.log(f"Installed Python server to {destination}")
            self.log(f"{PROJECT_NAME} v{VERSION} installation complete")
            return 0
        except OSError as exc:
            self.log(f"Installation failed: {exc}", "ERROR")
            return 1


if __name__ == "__main__":
    sys.exit(MCPInstaller().install())
