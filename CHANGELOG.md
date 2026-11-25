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
- `VERSION` at the repository root as the one place the version is written, plus
  `Tools/stamp-version.py`, which stamps it into all twelve hand-maintained sites in
  ten files; `Tools/check-version.py` now fails when any site drifts from
  `VERSION`, so a bump is one edit and one command instead of twelve edits

### Changed
- `release.yml` refuses a tag that disagrees with `VERSION` (including suffixes such as
  `-rc1`), builds `dist/v<version>` from `VERSION`, runs `check-version.py` before
  packaging and `check-archive.py` on the built pack before uploading, so a release
  cannot publish a pack whose name and stamped sites disagree
- The release archive ships `VERSION`, and `Tools/check-archive.py` fails when it
  disagrees with the version in the packaged server and unified installer, so an
  archive cannot be published under a stale version

### Fixed
- `release.yml` no longer appends the repository's whole history to a first tag's
  release body: with no earlier tag the curated notes stand alone and a notice is
  logged, and otherwise only the commits since that tag are listed
- `Tools/check-links.py` checks the Markdown files git tracks, so ignored build output
  and untracked scratch trees no longer fail the link check or change its count

## [1.0.1] - 2026-11-25

Patch release: the two servers now answer identically for the two remaining
differences that were bugs rather than design, and the version strings finally match
a released version. See [release/v1.0.1/release-notes.md](release/v1.0.1/release-notes.md).

### Added
- `Tools/check-links.py` plus a CI step that fails the build on broken relative
  links and unsupported schemes (such as `ca://`) in the documentation
- `Tools/check-conformance.py`, which sends the same requests to both servers and
  fails on any difference, plus a `--live-trace` mode the Windows CI job uses to run
  a real `trace_route` through the `tracert` path; its DoH cases are served by a
  loopback fixture at 64 KiB and 64 KiB + 1 byte, so the shared cap is asserted
  without contacting a DoH provider, and a CSV case covers CR, CRLF and quoting
- `Tools/check-version.py`, which fails when any hand-maintained version string, the
  changelog's newest release section and `release/v<version>/release-notes.md`
  disagree, so a bump cannot land in only some of them
- `Tools/check-archive.py`, the only place the archive's file list is written down:
it checks the contents, verifies `SHA256SUMS` and extracts, on either platform
- `--installers-root` / `-InstallersRoot` on the installer checks, so the packaged
copy of an extracted archive can be installed and handshaked; their session now also
asserts the protocol version, the five tool names and `ping`
- A CI packaging job, plus a Windows job that downloads the same archive the Linux
job built, so the Windows installers are exercised on every push against identical
bytes
- Windows CI job that parses `installers/*.ps1` and runs `Tools/check-installers.ps1`

### Changed
- Version strings now report `1.0.1` in both servers (`initialize`), both
  `package.json` files, `installers/cli.js`, `installers/install-mcp-server.py` and
  the client configs written by the shell and PowerShell installers, so an installed
  config and a running server agree with the release they came from
- `ci.yml` replaced the checkout-only workflow with syntax, smoke test, JSON,
  documentation-link and installer checks on Linux
- The release archive now ships `LICENSE` and `README.md` alongside `installers/`,
  `server/` and `docs/`
- `Tools/build-package.sh` builds the archive for both `release.yml` and CI, so the
  two cannot drift apart
- Documentation rewritten to match the shipped code: `README.md`,
  `docs/Architecture.md`, `docs/Modules.md`, `docs/Export.md`, `docs/Privacy.md`,
  `docs/AppMaker.md` (now a status page), `docs/TROUBLESHOOTING.md`,
  `docs/ROADMAP.md`, `ROADMAP.md`, `PERFORMANCE-GUIDE.md`, `SECURITY.md` and
  `CONTRIBUTING.md`

### Fixed
- `doh_test` applies the same 64 KiB response cap in both servers: a larger body now
  returns a normal result with `status: "error"`, the HTTP `statusCode` and
  `DoH response exceeded 64 KiB limit` instead of Python's `-32602` and Node reading
  the whole body; Node stops reading at the cap, so neither server buffers a larger
  response
- `export_results` CSV quotes a cell containing a carriage return in Node as well as
  Python, so both servers quote it the same way instead of Node writing a bare CR
  that split the row for any reader that treats CR as a line ending
- `trace_route` works on Windows: both servers run `tracert -d -h 15 -w 300` there
  instead of looking only for `traceroute`/`tracepath`, which Windows does not ship,
  so the tool no longer always returns `unavailable`; destinations starting with `-`
  are rejected in both servers
- Generated MCP configs now use the installed script's absolute path; clients no
  longer receive a relative `index.py` that resolves against their own working
  directory
- Unused `axios` dependency removed, so the unified installers write a
  `{"type": "module"}` manifest instead of running `npm install`
- `installers/package.json` no longer points `main`, `start` and `dev` at an
  `index.js` that does not exist; it points at `cli.js` and declares no
  dependencies (unused `express`, `dotenv` and `eslint` removed)
- CodeQL no longer analyses Swift, which the repository does not contain, so the
  analysis job runs on Linux only
- The bug report template asks for OS, runtime and MCP client instead of Windows and
  PowerShell only
- Deleted the shadowed lowercase `issue_template/bug_report.md` duplicate, which
  asked for a Swift version and a v1.1.0 release that never existed
- The release workflow uploaded from `dist/vvX.Y.Z` while the build wrote
  `dist/vX.Y.Z`; the upload paths now match the archive that is built
- `docs/PERFORMANCE-OPTIMIZATION.md` was a Swift/NSCache/Instruments guide; it now
  documents the servers' real timeouts, payload bounds and measurement method
- Broken relative links in `docs/README.md` and `release/v1.0.0/release-notes.md`,
  and leftover `ca://` links in `docs/Architecture.md` and `docs/ROADMAP.md`

### Removed
- `docs/Troubleshooting.md`, a mislabeled Swift performance guide whose name
  collided with `docs/TROUBLESHOOTING.md` on case-insensitive filesystems
- `server/mcp-server.json` and `server/mcp-client.json`, the static config templates
  that carried the relative path
- `installers/ish-gh-installer.sh`, an unrelated Alpine script that built the GitHub
  CLI from source and had no connection to this project
- `.devcontainer/`, a corrupted directory holding a stray feature file and no
  `devcontainer.json`
- `reference/`, five optimisation write-ups for the SwiftUI app that never existed
  (four Swift files and a `.cflog` logging design the servers do not use)
- `.setup-github-agent.ps1`, a scaffold that regenerated the Copilot instructions,
  issue templates, `CONTRIBUTING.md` and `ci.yml` with Windows-first content
- `Tools/icon-resizer.sh` (iOS/macOS icon sizes; the repository has no icons) and
  `Tools/cleanup-logs.sh` (a generic `*.log` vacuum; nothing here writes `*.log`)

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
