# Cloudflare Network Diagnostic Tool — Release Notes v1.0.0

**Release date:** 2026-06-19 (date of the first server commit in this repository; v1.0.0 itself was never tagged)
**Status:** initial release

## Overview

v1.0.0 provides network diagnostics over the Model Context Protocol: two stdio
servers — Node.js and Python — that expose the same five tools, installers that put
a server and a ready-to-use client config in a user-scoped directory, and the
documentation to run them.

## What's in this release

### MCP servers

- `server/index.js` — Node.js 18+, ES module, no runtime dependencies
- `server/index.py` — Python 3.8+, standard library only
- JSON-RPC 2.0 over stdio, one message per line, protocol version `2024-11-05`
- Methods: `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`
- Results carry `content[0].text`, `structuredContent` and `isError`

### Tools (identical on both servers)

| Tool | What it does | Bound |
|---|---|---|
| `dns_check` | A/AAAA resolution for a domain | resolver default |
| `doh_test` | GET to a DNS-over-HTTPS endpoint | 5 s |
| `trace_route` | system `traceroute` / `tracepath`, `tracert` on Windows | 20 s |
| `health_score` | TCP probe to `1.1.1.1:443` | 3 s |
| `export_results` | format a result object as JSON or CSV | none |

Details, schemas and failure modes: [docs/Modules.md](../../docs/Modules.md).

### Installers

| Installer | Platform | Installs |
|---|---|---|
| `installers/install-mcp-server.sh` | macOS/Linux | Python server |
| `installers/install-mcp-unified.sh` | macOS/Linux | Python and/or Node |
| `installers/install-mcp-server.ps1` | Windows | Python server |
| `installers/install-mcp-unified.ps1` | Windows | Python and/or Node |
| `installers/install-mcp-server.py` | any | Python server |
| `installers/cli.js` | any | Node server, with `install` / `status` / `start` |

Install directories are `~/.local/cloudflare-mcp` (macOS/Linux) and
`%APPDATA%\Cloudflare-MCP` (Windows). Generated configs use absolute paths, and the
Node install needs only a `{"type": "module"}` manifest — there is no `npm install`
step.

### Validation and CI

- `server/smoke_test.py` — JSON-RPC smoke test without network access
- `Tools/validate-json.py`, `Tools/check-installers.py` / `.ps1`, `Tools/check-links.py`
- `.github/workflows/ci.yml` — `validate` job (syntax, smoke test, Python/Node
  conformance, JSON, docs links, installer configs), a `package` job for the release
  archive, and a `windows` job (PowerShell parser, a real `tracert` trace, archive
  install)
- CodeQL, dependency review, security scan and release workflows

## Installation

Run the installers **from a checkout**. They locate the server sources relative to
themselves, so piping a script from a URL does not work.

```bash
git clone https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0.git
cd Cloudflare-Network-Diagnostic-Tool-v1.0
bash installers/install-mcp-unified.sh
```

```powershell
git clone https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0.git
cd Cloudflare-Network-Diagnostic-Tool-v1.0
.\installers\install-mcp-unified.ps1
```

Node CLI instead of an installer:

```bash
node installers/cli.js install
node installers/cli.js status
```

Then point your MCP client at `config/mcp-server.json` inside the install directory.

## Requirements

- **Node.js** 18+ **or** **Python** 3.8+ (either runtime is enough)
- **Windows** 10/11, **macOS**, or **Linux** with bash for the shell installers
- No third-party packages; nothing is published to npm or PyPI for this release

## Known issues

1. DoH body handling differs: Python refuses bodies over 64 KiB, Node reads them in
   full (truncating non-JSON bodies to 4096 characters). Fixed in v1.0.1: both
   servers now cap the body at 64 KiB and return a tool result.
2. Timestamps differ between implementations (`…Z` vs `…+00:00`), and `doh_test`
   echoes the URL as supplied in Python but normalised in Node.
3. `dns_check` returns the same addresses in a different order: sorted in Python,
   resolver order in Node.
4. Neither server caps incoming request-line size; `export_results` has no output cap.
5. DoH providers may rate limit (`403`/`429`); the tool always sends `GET`.
6. `health_score` is a single TCP probe and reports a fixed 95 or 64 — it is not a
   composite score.
7. v1.0.0 was never tagged in this repository.

## Not in this release

Earlier drafts of these notes listed features that do not exist in the repository
and never shipped: a SwiftUI application, an AppMaker generator, WARP diagnostics,
resolver benchmarking, DNSSEC and MX/NS/SOA lookups, PDF export, a Cloudflare API
client, a `cndt` CLI, a plugin system, and pip/npm packages. Planned work is tracked
in [ROADMAP.md](../../ROADMAP.md).

## Performance

No benchmarks are recorded for this release. Both servers handle one request at a
time, so a `trace_route` call can hold a session for up to 20 seconds; see
[PERFORMANCE-GUIDE.md](../../PERFORMANCE-GUIDE.md) for the timeouts, payload bounds
and how to measure locally.

## Support

- **Documentation:** [docs/](../../docs/)
- **Issues:** [GitHub Issues](https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/issues)
- **Security:** [SECURITY.md](../../SECURITY.md)
- **Contributing:** [CONTRIBUTING.md](../../CONTRIBUTING.md)

## Credits

Developed by **hyrated117**. Licensing: [LICENSE](../../LICENSE) — personal,
non-commercial use.

## Next steps

- Report bugs and protocol edge cases on GitHub
- Contribute improvements via pull requests (see [CONTRIBUTING.md](../../CONTRIBUTING.md))
- Follow [ROADMAP.md](../../ROADMAP.md) for planned tools and packaging
