# Cloudflare Network Diagnostic Tool — Release Notes v1.0.1

**Release date:** 2026-11-25
**Status:** patch release; v1.0.0 was dated in the changelog but never tagged

## Overview

v1.0.1 is the same two stdio MCP servers — Node.js and Python — exposing the same
five tools, plus the installer, packaging and documentation work that landed since
the first commit. No tool was added or removed; the protocol surface is unchanged.

## Changes since v1.0.0

### Fixed

- **DoH body size is capped identically in both servers.** `doh_test` stops reading
  at 64 KiB in both implementations. A larger body returns a normal tool result with
  `"status": "error"`, the endpoint's HTTP `statusCode` and the message
  `DoH response exceeded 64 KiB limit`. Previously Node buffered the whole body with
  no limit and Python turned the same condition into a JSON-RPC `-32602` error.
- **CSV quoting matches on carriage returns.** The Node CSV writer now quotes a
  cell that contains a carriage return, as Python's `csv` module already did, so a
  value with a bare CR no longer splits the row for readers that treat CR as a line
  ending. Non-string cells still go through each runtime's JSON writer, so `1.0`
  stays `1.0` in Python and becomes `1` in Node (see known issues).
- **`trace_route` works on Windows.** Both servers run `tracert -d -h 15 -w 300`
  there instead of looking only for `traceroute`/`tracepath`, which Windows does not
  ship. Destinations starting with `-` are rejected in both servers.
- **Installed MCP configs use the server script's absolute path**, so clients no
  longer receive a relative `index.py` resolved against their own working directory.
- **Timestamps use one format in both servers.** Results are stamped
  `YYYY-MM-DDTHH:MM:SS.mmmZ` (UTC, milliseconds) in Node and Python alike; Python
  previously wrote `…+00:00` with microseconds of varying length. The conformance and
  differential checks now assert that shape instead of dropping the field.
- **`doh_test` echoes the URL exactly as supplied in both servers.** Node returned the
  parsed URL, so `https://host` became `https://host/` and the host was normalised; it
  now echoes the request string like Python does, and the differential check compares
  the echo with the URL it sent.
- **`dns_check` sorts addresses in both servers.** Node reported the resolver's order
  where Python sorted the list; both now de-duplicate and sort, and the differential
  check compares every list with a sorted copy of itself.

### Changed

- **The DoH over-cap result is a tool result, not a protocol error.** Clients that
  matched on JSON-RPC error `-32602` for an oversized DoH body must instead read
  `result.isError` / `structuredContent.status`, the way they already handle a DoH
  timeout or a refused connection.
- Version strings now report `1.0.1` in both servers' `initialize` response, both
  `package.json` files, `installers/cli.js`, `installers/install-mcp-server.py` and
  the client configs written by the shell and PowerShell installers.
- The release archive ships `LICENSE`, `README.md` and `VERSION` alongside
  `installers/`, `server/` and `docs/`, and `Tools/build-package.sh` builds it for both
  the release workflow and CI so the two cannot drift apart.
- `installers/package.json` no longer points `main`, `start` and `dev` at an
  `index.js` that does not exist, and the unused `axios`, `express`, `dotenv` and
  `eslint` dependencies are gone.

### Checks and packaging

- `Tools/check-conformance.py` sends the same requests to both servers and fails on
  any difference. Its DoH cases are served by a loopback fixture at 64 KiB and
  64 KiB + 1 byte, and the CSV case covers CR, CRLF, commas and quotes.
- `Tools/check-links.py`, `Tools/check-archive.py` and the installer checks run in
  CI; the archive is built once on Linux and downloaded by the Windows job so both
  platforms exercise identical bytes, including a real `tracert` run.
- `Tools/check-version.py` fails when a hand-maintained version string, the
  changelog's newest release section and these notes disagree.
- The workflow files and shell scripts are linted with `actionlint` and a pinned
  `shellcheck` 0.11.0, and `release.yml` runs this same CI workflow as a `checks` job
  before it publishes, so a tag cannot release a commit that fails the tests, the
  version checks or lint.
- Documentation rewritten against the shipped code: `README.md`,
  `docs/Architecture.md`, `docs/Modules.md`, `docs/Export.md`,
  `docs/TROUBLESHOOTING.md`, `docs/Privacy.md`, `docs/AppMaker.md` (now a status
  page), `docs/PERFORMANCE-OPTIMIZATION.md`, `docs/ROADMAP.md`, `ROADMAP.md`,
  `PERFORMANCE-GUIDE.md`, `SECURITY.md` and `CONTRIBUTING.md`. The wider changes are
  listed in [CHANGELOG.md](../../CHANGELOG.md).

## Upgrade notes

- Re-run your installer (or `node installers/cli.js install`) to rewrite the client
  config with the current script path and `1.0.1`.
- Nothing else needs migrating: there is no database, cache or state on disk, and no
  configuration key changed.
- If you pinned the `-32602` DoH error, update that handling as described above.

## Requirements

- **Node.js** 18+ **or** **Python** 3.8+ (either runtime is enough)
- **Windows** with PowerShell, **macOS**, or **Linux** with bash for the shell
  installers
- No third-party packages; nothing is published to npm or PyPI

## Known issues

1. A CSV cell holding a non-string value is rendered by each runtime's JSON writer,
   so `1.0` stays `1.0` in Python and becomes `1` in Node; Node also parses request
   numbers as doubles, so an integer above 2^53 loses precision before any tool sees
   it.
2. Neither server caps incoming request-line size; `export_results` has no output cap.
3. DoH providers may rate limit (`403`/`429`); `doh_test` always sends `GET`.
4. `health_score` is a single TCP probe and reports a fixed 95 or 64 — it is not a
   composite score.
5. v1.0.0 was dated in the changelog but never tagged; its notes in
   [release/v1.0.0](../v1.0.0/release-notes.md) describe the original code and its
   known issues, including the DoH difference fixed here.

Tool details and failure modes: [docs/Modules.md](../../docs/Modules.md) and
[docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md).
