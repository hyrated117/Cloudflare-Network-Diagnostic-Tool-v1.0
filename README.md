# Cloudflare Network Diagnostic Tool v1.0

Network diagnostics over the Model Context Protocol (MCP). Two dependency-free
stdio servers — Node.js (`server/index.js`) and Python (`server/index.py`) — expose
the same five tools to any MCP client, with installers that place a server and a
ready-to-use client config in your home directory.

This repository contains the MCP servers, installers and documentation. It does
**not** contain a SwiftUI app, AppMaker generator or Cloudflare API integration —
those are tracked in [ROADMAP.md](./ROADMAP.md).

## Requirements

- Node.js 18+ **or** Python 3.8+ (either runtime is enough)
- An MCP-capable client, or `stdio` plus JSON-RPC

Neither server uses third-party packages, so no `npm install` or `pip install` is
involved.

## Installation

### macOS / Linux

```bash
# Python and/or Node, whichever is available (Python is preferred for the generated config)
bash installers/install-mcp-unified.sh

# or Python only
bash installers/install-mcp-server.sh
```

Everything lands under `~/.local/cloudflare-mcp/`:

```
server/python/index.py     # when Python was installed
server/node/index.js       # when Node was installed
config/mcp-server.json     # absolute paths for <runtime> <server script>
config/mcp-client.json     # same entry under servers.cloudflare-diagnostics
install.log                # written by install-mcp-unified.sh, the Python installer and the CLI
```

The single-runtime installers place the server at `server/index.py` or
`server/index.js` instead of the `python/` and `node/` subdirectories.

### Windows (PowerShell)

```powershell
.\installers\install-mcp-unified.ps1                        # Python and/or Node, default %APPDATA%\Cloudflare-MCP
.\installers\install-mcp-server.ps1                         # Python only
.\installers\install-mcp-unified.ps1 -InstallDir D:\tools\cloudflare-mcp
```

### Node CLI

```bash
node installers/cli.js install   # copies server/index.js and writes config/mcp-server.json
node installers/cli.js status    # checks the installation
node installers/cli.js start     # runs the installed server on stdio
```

## Usage

Point your MCP client at `config/mcp-server.json`, or copy the equivalent entry
into the client's own configuration:

```json
{
  "mcpServers": {
    "cloudflare-diagnostics": {
      "command": "/usr/bin/python3",
      "args": ["/home/you/.local/cloudflare-mcp/server/python/index.py"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

Paths must be absolute — clients resolve relative paths against their own working
directory, not against the config file.

You can also run a server directly and speak JSON-RPC over stdin:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"dns_check","arguments":{"domain":"example.com"}}}' \
  | node server/index.js
```

```json
{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{…}"}],
 "structuredContent":{"tool":"dns_check","domain":"example.com","status":"ok","addresses":["93.184.215.14"]},"isError":false}}
```

## Tools

| Tool | Purpose |
|---|---|
| `dns_check` | Resolve IPv4 and IPv6 addresses for a domain |
| `doh_test` | Send a request to a DNS-over-HTTPS endpoint |
| `trace_route` | Run the system `traceroute`, `tracepath` or `tracert` |
| `health_score` | TCP reachability probe to `1.1.1.1:443` |
| `export_results` | Format a result object as JSON or CSV |

Arguments, result fields, statuses and timeouts are documented in
[docs/Modules.md](./docs/Modules.md).

## Checks

```bash
node --check server/index.js
node --check installers/cli.js
python3 -m compileall -q server installers Tools
bash -n installers/*.sh Tools/*.sh
python3 server/smoke_test.py        # protocol smoke test, no network access
python3 Tools/check-conformance.py  # Python and Node answer identically
python3 Tools/check-version.py      # VERSION, the stamped sites and the changelog agree
python3 Tools/validate-json.py .    # JSON syntax
python3 -m pip install --quiet pyyaml==6.0.4   # needed by the two checks below
python3 Tools/check-dependabot.py   # .github/dependabot.yml parses and is accepted
python3 Tools/test_check_dependabot.py         # that check's rules, both ways
python3 Tools/check-workflows.py    # triggers, timeouts, pins, broken continuations
python3 Tools/test_check_workflows.py          # each rule, the break and the sound case
python3 Tools/test_check_pins.py               # the pin audit's rules, offline
python3 Tools/test_check_version.py            # every failure the checker promises
python3 Tools/test_stamp_version.py            # a bump writes all sites or none
python3 Tools/test_check_archive.py            # the release gate's rules, on built packs
python3 Tools/check-links.py        # no broken relative links in the docs
python3 Tools/check-installers.py   # shell, Python and CLI installers write launchable configs
```

The `Validate` job runs these on Linux in this order. A `package` job then builds the
release archive and installs from the extracted copy, `lint` runs actionlint and the
pinned shellcheck over the workflows and shell scripts, and a Windows job parses the
PowerShell installers, runs a real `trace_route` through `tracert`, and installs from
the archive the Linux job built — see `.github/workflows/ci.yml`. `Tools/check-pins.py`
re-runs the pin audit against the GitHub API and Docker Hub, which is why it needs
network access and only its self-test is part of CI.

## Documentation

- [docs/README.md](./docs/README.md) — documentation index
- [docs/Architecture.md](./docs/Architecture.md) — components, protocol, configuration
- [docs/Modules.md](./docs/Modules.md) — the five tools
- [docs/Export.md](./docs/Export.md) — `export_results` formats
- [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) — common issues and error codes
- [SECURITY.md](./SECURITY.md) · [CONTRIBUTING.md](./CONTRIBUTING.md) · [ROADMAP.md](./ROADMAP.md)

## License

See [LICENSE](./LICENSE) — personal, non-commercial use.
