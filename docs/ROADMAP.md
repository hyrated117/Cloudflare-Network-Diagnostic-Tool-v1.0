# 🗺️ Project Roadmap  
MCP Server • Installers • Documentation

This roadmap covers the components that exist: the two MCP stdio servers
(`server/index.js`, `server/index.py`), their installers and the documentation.
It replaces an earlier version that described a SwiftUI app and an AppMaker
generator as current work.

**Today:** five tools (`dns_check`, `doh_test`, `trace_route`, `health_score`,
`export_results`) over JSON-RPC on stdio, `initialize` negotiating the protocol version
(`2024-11-05`; any other requested version is answered with it), macOS/Linux and
Windows installers, and CI on both platforms. See [Modules](./Modules.md) for the tool
reference and [Architecture](./Architecture.md) for the design.

---

# 🚀 Near term

### Servers
- Full behavioural parity between the Node and Python implementations
  (extra-argument rejection, DoH body size limits, timestamp format)
- Conformance tests per tool, including malformed input and offline behaviour, run
  in CI on both platforms

### Installers
- One config shape across all six installers, verified by the existing
  `Tools/check-installers.py` / `.ps1` checks
- Optional uninstall path and clearer `status` output in the Node CLI

### Documentation
- Keep every page matched to the code; remove remaining references to features
  that do not exist
- Publish a short migration note for clients moving from the old config layout

---

# 🔧 Mid term

### New diagnostics
- MX/NS/SOA record lookups alongside the existing A/AAAA resolution
- DNSSEC validation against a DoH resolver
- Resolver benchmarking across a configurable resolver list
- A composite `health_score` built from DNS, DoH and trace results

### Output
- Optional file output for `export_results` (today it returns text only)
- Structured CSV for nested results instead of JSON-in-cell

### Distribution
- npm and PyPI packages for the dependency-free servers
- Example client configurations (Claude Desktop, VS Code, generic stdio)

---

# 🌐 Longer term — exploratory

- **Desktop application:** the SwiftUI UI that earlier docs described is not
  started and has no code in this repository.
- **AppMaker generator:** project scaffolding for the above — also not started;
  see [AppMaker](./AppMaker.md).
- **Cloudflare API integration:** zone, WAF and analytics checks (requires
  credentials and a design for their safe storage — not started).

---

# 🧩 Community

- More tools and installers, as long as each ships with tests
- Bug reports and protocol edge cases are welcome

---

# ❤️ Contributions Welcome

See the [Contributing Guide](../CONTRIBUTING.md).
