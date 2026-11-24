# Changelog
All notable changes to this project will be documented in this file.

The format is based on **Keep a Changelog**, and this project adheres to **Semantic Versioning 2.0.0**.

Earlier revisions of this file listed a `1.1.0` release and a `0.1.0` prototype that
described a SwiftUI application, an AppMaker generator, a `cndt` CLI and a
Cloudflare API client. None of that was implemented, released or tagged, so those
entries have been removed. The first version in this repository is `1.0.0`.

---

## [Unreleased]

### Added
- `Tools/check-links.py` plus a CI step that fails the build on broken relative
  links and unsupported schemes (such as `ca://`) in the documentation
- Windows CI job that parses `installers/*.ps1` and runs `Tools/check-installers.ps1`

### Changed
- `ci.yml` replaced the checkout-only workflow with syntax, smoke test, JSON,
  documentation-link and installer checks on Linux
- Documentation rewritten to match the shipped code: `README.md`,
  `docs/Architecture.md`, `docs/Modules.md`, `docs/Export.md`, `docs/Privacy.md`,
  `docs/AppMaker.md` (now a status page), `docs/TROUBLESHOOTING.md`,
  `docs/ROADMAP.md`, `ROADMAP.md`, `PERFORMANCE-GUIDE.md`, `SECURITY.md` and
  `CONTRIBUTING.md`

### Fixed
- Generated MCP configs now use the installed script's absolute path; clients no
  longer receive a relative `index.py` that resolves against their own working
  directory
- Unused `axios` dependency removed, so the unified installers write a
  `{"type": "module"}` manifest instead of running `npm install`
- Broken relative links in `docs/README.md` and `release/v1.0.0/release-notes.md`,
  and leftover `ca://` links in `docs/Architecture.md` and `docs/ROADMAP.md`

### Removed
- `docs/Troubleshooting.md`, a duplicate performance guide that differed from
  `docs/TROUBLESHOOTING.md` only by case
- `server/mcp-server.json` and `server/mcp-client.json`, the static config templates
  that carried the relative path
- `installers/ish-gh-installer.sh`, an unrelated Alpine script that built the GitHub
  CLI from source and had no connection to this project
- `.devcontainer/`, a corrupted directory holding a stray feature file and no
  `devcontainer.json`

---

## [1.0.0] - 2026-06-19

First version committed to this repository (no git tag exists yet).

### Added
- Node.js MCP stdio server (`server/index.js`), ES module, no runtime dependencies
- Python MCP stdio server (`server/index.py`), standard library only
- Five diagnostic tools on both servers: `dns_check`, `doh_test`, `trace_route`,
  `health_score`, `export_results`
- Installers for macOS/Linux (`install-mcp-server.sh`, `install-mcp-unified.sh`),
  Windows (`install-mcp-server.ps1`, `install-mcp-unified.ps1`), Python
  (`install-mcp-server.py`) and the `installers/cli.js` Node CLI
- Client configuration (`mcp-server.json`, `mcp-client.json`) written by the
  installers into user-scoped directories
- Protocol smoke test (`server/smoke_test.py`) and JSON validation utility
- Documentation set: architecture, tools, export, privacy, troubleshooting, security
  and release notes
