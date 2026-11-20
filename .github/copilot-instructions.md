# Copilot Instructions

## Repository scope

- This repository contains a Windows-first network diagnostic application, MCP-style diagnostic servers, support scripts, installers, documentation, and release assets.
- Preserve existing features and backwards compatibility when changing behavior.
- Keep changes minimal and focused; prefer a small fix over broad refactoring.
- Follow the conventions already used in each component rather than imposing a new framework or structure.

## General engineering

- Use clear function and variable names and keep functions focused on one responsibility.
- Add comments only for non-obvious logic, platform constraints, or complex protocol handling.
- Avoid duplicate implementations; check whether Python, JavaScript, Swift, or PowerShell already provides equivalent behavior before adding a new helper.
- Avoid new external dependencies unless they are necessary. Prefer standard libraries and PowerShell-native commands.
- Do not store credentials, tokens, secrets, addresses that reveal private infrastructure, or collected diagnostic data in source control.

## Network diagnostics

- Validate all user and RPC inputs before executing commands or network operations.
- Reject malformed hosts, URLs with credentials, unexpected whitespace, and unexpected or out-of-range values.
- Apply explicit timeouts to DNS, HTTP/DNS-over-HTTPS, TCP, traceroute, and other network operations.
- Handle DNS failures, refused connections, unreachable hosts, missing system utilities, and offline mode without terminating unexpectedly.
- Return clear `ok`, `error`, `degraded`, or `unavailable` status values and include actionable error text.
- Do not claim a network check succeeded unless the operation actually completed successfully.
- Keep diagnostic output useful and readable, including verbose details where appropriate.
- Preserve compatibility with Windows 10 and Windows 11. Account for platform differences when invoking system commands.

## Swift

- Match the existing Swift and SwiftUI naming, file layout, and state-management patterns.
- Keep UI changes accessible and responsive, and avoid blocking the main thread on network or process work.
- Preserve app behavior and data formats across releases.
- Test Windows 10/11-compatible SwiftUI behavior when Swift changes affect the UI or platform integration.

## JavaScript MCP server

- The Node server in `server/index.js` uses newline-delimited JSON-RPC over stdio and is published as an ES module.
- Preserve JSON-RPC 2.0 notification and response behavior, including parse, invalid request, method, and parameter errors.
- Keep tool names, input schemas, structured result fields, and return statuses backward-compatible.
- Do not log protocol responses to stdout; keep operational logging on stderr.
- Validate tool arguments and safely handle process, DNS, HTTP, and socket failures.
- The server package in `server/package.json` is private and uses Node's ES module mode; update scripts and dependency declarations consistently.

## Python MCP server

- The Python implementation in `server/index.py` mirrors the diagnostic tool protocol and tools.
- Keep Python and JavaScript implementations behaviorally consistent when both implement the same tool.
- Use the standard library unless an existing dependency is required.
- Preserve newline-delimited JSON-RPC behavior and JSON response shape.
- Catch expected network, timeout, subprocess, decoding, and malformed-input exceptions rather than allowing stack traces or abrupt exits.

## PowerShell and shell scripts

- Prefer PowerShell-native commands for Windows diagnostics and scripts.
- Use explicit exit handling and meaningful success or failure messages.
- Validate inputs before passing values to native commands.
- Be careful with quoting and shell metacharacters, especially for destinations and paths.
- Keep shell scripts portable to the environments described by the repository and avoid hard-coded machine-specific paths.

## Documentation and assets

- Document new or changed user-facing features in `README.md` and the relevant file under `docs/`.
- Keep `CONTRIBUTING.md`, the implementation checklist, roadmap, architecture, and module documentation consistent with meaningful architectural or feature changes.
- Do not overwrite generated installers or release artifacts unless the task explicitly requires a release change.
- For UI changes, include screenshots in the pull request when practical.

## Testing and verification

- Follow existing test conventions and add or update tests when behavior changes.
- Where relevant, verify DNS resolution, DNS-over-HTTPS requests, Cloudflare endpoint reachability, TCP health checks, and traceroute/tracepath behavior.
- Test malformed inputs and offline or unavailable-network conditions. Scripts and servers must return meaningful errors rather than terminate unexpectedly.
- Run the most focused checks first, then relevant repository checks:
  - JavaScript syntax: `cd server && npm run check`
  - Python server smoke tests: use `python server/smoke_test.py` when appropriate
  - Shell and PowerShell scripts: run in their supported environment and inspect exit codes and output
- Report tests that cannot be run and explain any environment or network limitation.

## Pull requests

- Include a concise summary of the changes, the reason for them, and testing performed.
- Call out compatibility risks, protocol changes, platform-specific behavior, and documentation updates.
- Keep unrelated formatting or cleanup out of the same change.
