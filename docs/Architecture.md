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
- Methods: `initialize` (reports `protocolVersion: 2024-11-05`, `capabilities.tools`),
  `notifications/initialized`, `ping`, `tools/list`, `tools/call`.
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
| `dns_check` | `dns.resolve4/resolve6` (Node), `getaddrinfo` (Python) | resolver default |
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
- `Tools/check-installers.py` / `Tools/check-installers.ps1` — run the shell,
  unified-shell and Node CLI installers (or the two PowerShell installers) into a
  temporary directory and confirm the generated config launches the server. Neither
  check runs `installers/install-mcp-server.py`.
- `Tools/validate-json.py` — JSON syntax validation.
- `.github/workflows/ci.yml` — `validate` job (syntax, smoke test, conformance,
  JSON, documentation links, installer configs), a `package` job (build the archive,
  check it, install from the extracted copy) and a `windows` job (PowerShell parser,
  a real `tracert` trace, and the same archive installed with the `.ps1` installers).
