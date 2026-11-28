# Copilot Instructions

## Repository scope

- This repository contains two dependency-free MCP stdio servers, the installers that
  deploy them, a Node CLI, the validation tools and the documentation.
- There is **no** Swift, SwiftUI, AppMaker or Cloudflare API code. Do not add
  guidance, examples or TODOs for components that are not here.
- Keep changes minimal and focused; prefer a small fix over a broad refactor.
- Follow the conventions already used in each component.

## MCP protocol

- `server/index.js` and `server/index.py` speak JSON-RPC 2.0, one message per line,
  over stdio, and both report protocol version `2024-11-05`.
- Protocol frames go to stdout and nothing else: never write logs, diagnostics or
  warnings there. The servers make no logging calls, so stderr stays empty except
  for a fatal startup error.
- Preserve error behaviour: `-32700` parse error, `-32600` invalid request,
  `-32601` method not found, `-32602` invalid params. Notifications receive no reply.
- Keep the result shape: `content[0].text` (the result as a JSON string),
  `structuredContent`, and `isError` when `status == "error"`.
- Tool names, input schemas and status values are part of the interface — keep them
  backward compatible.

## Network diagnostics

- Validate arguments before touching the network: types, required keys, no whitespace
  in destinations, no credentials in URLs, `format` limited to `json`/`csv`.
- Every network or process operation needs a timeout (DoH 5 s, trace 20 s, TCP probe
  3 s today) and must return a status instead of raising.
- Handle DNS failure, refused connections, offline hosts and missing utilities without
  crashing; `trace_route` returns `"unavailable"` when the platform's tracer is
  missing: `traceroute` or `tracepath` on Linux/macOS, `tracert` on Windows. Windows
  ships `tracert`, so `unavailable` there means it is not on `PATH`.
- Do not claim a check succeeded unless it completed.

## Node and Python parity

- Both servers implement the same five tools; keep argument handling, result fields and
  statuses aligned.
- Both servers reject unknown tools, missing required arguments and unexpected
  arguments with `-32602`; keep it that way on both sides.
- Both servers cap DoH bodies at 64 KiB and return a tool-level `status: "error"` for a
  larger body (Node keeps only the first 4096 characters of a non-JSON body within the
  cap). Known differences, which must stay deliberate and documented: timestamps differ
  (`Z` vs `+00:00`); `doh_test` echoes the URL as supplied in Python and normalised in
  Node; `dns_check` sorts addresses in Python and keeps resolver order in Node.
- Use the standard library only. Do not add dependencies to either server.

## Installers

- Install into user-scoped directories only (`~/.local/cloudflare-mcp`,
  `%APPDATA%\Cloudflare-MCP`), never with elevated privileges.
- Write `command`/`args` as absolute paths — clients resolve relative paths against
  their own working directory. Regenerate, do not hand-edit, configs when moving an
  install.
- The Node server is dependency-free: write a `{"type": "module"}` manifest beside
  `index.js` instead of running `npm install`.
- Update the shell and PowerShell installers together and keep
  `Tools/check-installers.py` / `Tools/check-installers.ps1` passing.

## Documentation

- Document only what exists. Planned work belongs in `ROADMAP.md`,
  `docs/ROADMAP.md`, or an explicitly labelled "Planned (not implemented)" section.
- Run `python3 Tools/check-links.py` after editing Markdown; CI fails on broken
  relative links and on unsupported schemes such as `ca://`.
- Keep paths, timeouts, command lines and example output accurate — quote real output
  rather than inventing it.
- Keep `README.md`, `CONTRIBUTING.md`, both roadmaps and the `docs/` pages consistent
  with any behaviour change.

## Testing and verification

Run the same checks as CI:

```bash
node --check server/index.js
node --check installers/cli.js
python3 -m compileall -q server installers Tools
bash -n installers/*.sh Tools/*.sh
python3 server/smoke_test.py
python3 Tools/check-conformance.py
python3 Tools/test_parity.py
python3 Tools/check-version.py
python3 Tools/validate-json.py .
python3 -m pip install --quiet pyyaml==6.0.4   # check-dependabot.py and check-workflows.py
python3 Tools/check-dependabot.py
python3 Tools/test_check_dependabot.py
python3 Tools/check-workflows.py
python3 Tools/test_check_workflows.py
python3 Tools/test_check_pins.py
python3 Tools/test_check_actionlint_image.py
python3 Tools/test_windows_trace_route.py
python3 Tools/test_injection.py
python3 Tools/test_check_stack.py
python3 Tools/test_check_version.py
python3 Tools/test_stamp_version.py
python3 Tools/check-links.py
python3 Tools/check-installers.py
Tools/build-package.sh v0.0.0-ci
python3 Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack
python3 Tools/test_check_archive.py
python3 Tools/check-installers.py --installers-root dist/pack
./Tools/check-installers.ps1 -InstallersRoot dist/pack   # Windows installers
```

The last three build the release archive with the same script `release.yml` runs,
check its contents, then install from the extracted copy and handshake with the
packaged server. The archive's file list lives only in `Tools/check-archive.py`; do
not duplicate it in a workflow.

`node --check` validates one file at a time, so list each file on its own line.

- For PowerShell or Windows installer changes, also run
  `Tools/check-installers.ps1` in PowerShell; if no PowerShell host is available,
  say so instead of assuming it passed.
- Report any check you could not run and why (for example, no network access).

## Pull requests

- Include a concise summary, the reason for the change and the checks performed.
- Call out protocol changes, installer path changes and platform-specific behaviour.
- Keep unrelated formatting or cleanup out of the same change.
