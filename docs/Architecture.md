# Architecture

## Components

```
┌──────────────────────────┐        ┌──────────────────────────┐
│ MCP client (any)         │        │ Installers / CLI         │
│  · JSON-RPC 2.0 on stdio │        │  · shell, PowerShell,    │
└───────────┬──────────────┘        │    Python, Node CLI      │
            │                       └────────────┬─────────────┘
            │                                    │ copies server +
            ▼                                    ▼ writes mcp-*.json
┌──────────────────────────────────────────────────────────────┐
│ server/index.js (Node 18+, ESM)   server/index.py (3.8+)      │
│   protocol → tool dispatch → diagnostics → JSON result        │
└──────────────────────────────────────────────────────────────┘
```

There is no SwiftUI app, Cloudflare API layer, plugin system or AppMaker generator
in this repository; those were described by older documentation and are tracked as
planned work in [docs/ROADMAP.md](./ROADMAP.md). AppMaker has its own
[status page](./AppMaker.md).

## Transport and protocol

- JSON-RPC 2.0, one message per line, over stdio (stdin/stdout).
- Methods: `initialize` (reports `protocolVersion` and `capabilities.tools`),
  `notifications/initialized`, `ping`, `tools/list`, `tools/call`.
- Protocol version: both servers speak `2024-11-05`. `initialize` echoes that version
  when the client asks for it and answers with it for any other request — a newer or
  older MCP version, or a value that is not a string — so a client is never told a
  version the server does not speak.
- No MCP resources or prompts are served.
- Error codes: `-32700` parse error, `-32600` invalid request, `-32601` method not
  found, `-32602` invalid parameters. Notifications never receive a response.
- stdout carries protocol frames only. The servers make no logging calls, so
  stderr stays empty unless startup fails.

## Tool dispatch

Each server keeps a table of tools with a description, an input schema and a
handler. `tools/call` validates the arguments, runs the handler and returns:

- `content[0].text` — the result serialised as JSON
- `structuredContent` — the same object, structured
- `isError` — true when the result's `status` is `"error"`

Tool behaviour and per-server differences are documented in [Modules](./Modules.md).

## Diagnostics

All diagnostics use the standard library or the operating system's utilities:

| Tool | Mechanism | Timeout |
|---|---|---|
| `dns_check` | `dns.resolve4/resolve6` (Node), `getaddrinfo` (Python); IDNA-encoded first | resolver default |
| `doh_test` | `fetch` (Node), `urllib` (Python) | 5 s |
| `trace_route` | `traceroute`, then `tracepath`; `tracert -d -h 15 -w 300` on Windows | 20 s |
| `health_score` | TCP connect to `1.1.1.1:443` | 3 s |
| `export_results` | in-process string formatting | none |

## Installation and configuration

Installers copy the server into a user-scoped directory and generate client
configuration with **absolute** paths (a relative path would be resolved against
the client's working directory):

| Installer | Platform | Installs | Config directory |
|---|---|---|---|
| `installers/install-mcp-server.sh` | macOS/Linux | Python server | `~/.local/cloudflare-mcp/config` |
| `installers/install-mcp-unified.sh` | macOS/Linux | Python and/or Node | same |
| `installers/install-mcp-server.ps1` | Windows | Python server | `%APPDATA%\Cloudflare-MCP\config` |
| `installers/install-mcp-unified.ps1` | Windows | Python and/or Node | same |
| `installers/install-mcp-server.py` | any | Python server | `~/.local/cloudflare-mcp/config` |
| `installers/cli.js` | any | Node server, `install`/`start`/`status` | same |

The Node server needs no dependencies; the unified installers write a
`{"type": "module"}` manifest beside `index.js` and never invoke `npm`.

## Verification

- `server/smoke_test.py` — protocol smoke test without network access.
- `Tools/check-conformance.py` — feeds the same requests to both servers and fails on
  any difference except the instant a timestamp records (the format is asserted and
  compared); `--live-trace` adds one real trace.
- `Tools/test_parity.py` — the same comparison over a seeded random corpus and a fixed
  edge list: odd argument types, missing and extra keys, nulls, malformed lines, bad DoH
  URLs, a NUL byte in a destination and non-ASCII exports. Name resolution is stubbed in
  both runtimes from one table, which also holds Unicode names: case and NFC variants that
  must encode identically, a malformed label both servers refuse, and `faß.test`/`ς.test`,
  which the two IDNA standards encode differently and the test pins as deliberate, plus
  structurally invalid ASCII names the resolver rejects and both servers must report with
  one shared message. DoH is served by a loopback fixture, so the success and
  error results that normally need a network are compared and asserted too. Timestamps are
  compared by shape (`YYYY-MM-DDTHH:MM:SS.mmmZ`) rather than ignored. Deterministic;
  `Validate` runs it as `Diff the servers on randomized requests`.
- `Tools/check-version.py` — `VERSION`, the twelve stamped sites and the newest changelog
  section agree, and the release notes exist and name that version.
- `Tools/validate-json.py` — JSON syntax validation.
- `Tools/check-dependabot.py` — `.github/dependabot.yml` parses and holds the keys
  Dependabot needs.
- `Tools/check-runtimes.py` and `Tools/test_check_runtimes.py` — the `validate` matrix is
  tied to the minimums `README.md` promises: a leg must run the exact Node minimum and a
  leg the exact Python minimum (the same leg may cover both), the setup steps must read the
  versions from the matrix rather than hardcode them, and an unquoted `3.10` — which YAML
  reads back as `3.1` — is refused.
- `Tools/check-workflows.py` and `Tools/test_check_workflows.py` — every pull request
  triggers a run, every job sets a timeout, every `uses:` is pinned, and no `run:` line
  hides a continuation character behind whitespace.
- `Tools/check-pins.py` and `Tools/test_check_pins.py` — every action's release comment
  resolves to its pinned commit through the GitHub API, and the actionlint image digest
  through Docker Hub. The audit needs network access, so `Validate` runs its self-test.
- `Tools/check-actionlint-image.py` and `Tools/test_check_actionlint_image.py` — the
  image `lint` runs, pulled by its pinned digest and executed from its extracted
  binaries, so the Docker step is reproducible without a daemon; its rules run offline.
- `Tools/test_injection.py` — a fake `traceroute` first on `PATH` records its argv and
  resolver stubs record names; flag-shaped and shell-shaped destinations and domains must
  be refused or arrive as one literal argument, never as extra flags or shell code.
- `Tools/test_windows_trace_route.py` — forces the `tracert` branch of `trace_route` in
  both servers with a shim on `PATH`, so its flags and its success, failure and missing
  outcomes are validated on Linux instead of only by the Windows job.
- `Tools/check-stack.py` and `Tools/test_check_stack.py` — the five stacked branches are
  pre-flighted before review: each base must be the previous tip, and the branches are
  merged into a simulated `main` to prove the sequence is conflict-free. It needs the
  branch refs, so `Validate` runs its self-test. It reports "already merged" or "nothing
  to rehearse" and exits 0 once the stack is gone, and should be deleted with its
  self-test and `Validate` step after PR 5 merges.
- `Tools/check-links.py` — relative documentation links resolve.
- `Tools/check-installers.py` / `Tools/check-installers.ps1` — run the shell,
  unified-shell, Python and Node CLI installers (or the two PowerShell installers) into
  a temporary directory and confirm the generated config launches the server.
- `.github/workflows/ci.yml` — `validate` job (syntax, smoke test, conformance,
  version consistency, JSON, the pinned PyYAML with the runtime-matrix check and its
  self-test, the Dependabot check and its self-test, the workflow checks and their
  self-test, the version self-tests, the
  archive self-test, documentation links, installer configs) on a matrix that runs the
  release environment (Node 20, Python 3.12) and the floor the README promises
  (Node 18, Python 3.8), a `package` job (build
  the archive, check it, install from the extracted copy), a `lint` job (actionlint
  with its bundled shellcheck, then pinned shellcheck over `installers/*.sh` and
  `Tools/*.sh`), a `windows` job (PowerShell parser, a real `tracert` trace, and the
  same archive installed with the `.ps1` installers) and a `macos` job (syntax checks,
  smoke test, conformance, differential test and injection test on `macos-latest`).
