# Roadmap — Cloudflare Network Diagnostic Tool v1.0

## Shipped today

- **MCP servers** over newline-delimited JSON-RPC on stdio: `server/index.js`
  (Node.js 18+, ES module, no dependencies) and `server/index.py` (Python 3.8+,
  standard library only)
- **Five tools**: `dns_check`, `doh_test`, `trace_route`, `health_score`,
  `export_results`
- **Installers**: `install-mcp-server.sh` / `install-mcp-unified.sh` (macOS/Linux),
  `install-mcp-server.ps1` / `install-mcp-unified.ps1` (Windows),
  `install-mcp-server.py`, and the `installers/cli.js` Node CLI
- **Client configs** generated with absolute paths; the Node server needs no
  `npm install`
- **Validation**: protocol smoke test, JSON validation, installer checks on Linux
  and a PowerShell/packaging check on Windows via CI
- **Documentation** covering architecture, tools, export, privacy and troubleshooting

## Not implemented

Earlier versions of this roadmap listed the following as completed. None of them
exist in this repository:

- SwiftUI diagnostic application, theming and result dashboard
- AppMaker generator (project scaffolding, module injection, ZIP packaging)
- WARP module and resolver benchmarking
- DNSSEC validation and MX/NS/SOA queries
- PDF export
- Cloudflare API integration (WAF, Firewall, Analytics, Radar, Zero Trust)
- Plugin system and plugin manifest validation
- Distributed node agent / predictive routing engine

## Planned

### Near term

- Bring the Node and Python servers to full behavioural parity (extra-argument
  handling, DoH body limits, timestamp format)
- Conformance tests for every tool plus malformed-input cases in CI
- Clearer timeout configuration instead of fixed values

### Mid term

- New tools: MX/NS/SOA lookups, DNSSEC validation, resolver benchmarking
- A composite `health_score` that combines DNS, DoH and trace results
- Optional file output for `export_results` (currently returns text only)
- Packaged releases for npm and PyPI with the same dependency-free servers

### Longer term / exploratory

- A native desktop UI (the earlier SwiftUI design) — not started
- An AppMaker-style project generator — not started, see
  [docs/AppMaker.md](./docs/AppMaker.md)
- Cloudflare API integration for zone and analytics checks

Detailed, dated planning lives in [docs/ROADMAP.md](./docs/ROADMAP.md).
