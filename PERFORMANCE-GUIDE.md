# ⚡ Performance Guide  
Cloudflare Network Diagnostic Tool • MCP Servers • Installers

This guide describes how the shipped components behave under load: the two MCP
stdio servers, the installers and the Node CLI. There is no SwiftUI application,
AppMaker generator, caching layer or streaming transport in this repository — see
[Planned (not implemented)](#planned-not-implemented).

---

## What the servers are

| Server | Startup work | Dependencies |
|---|---|---|
| `server/index.js` | loads `node:` built-ins, builds the tool table | none |
| `server/index.py` | imports the standard library, builds the tool table | none |

Both are single processes that handle requests one at a time in arrival order.
There is no warm-up phase, worker pool, database or background thread, and neither
runtime needs an install step or a package manager.

Serialization is the standard library: `JSON.stringify` in Node, `json.dumps` in
Python. No optional accelerators (such as `orjson`) are imported or required.

---

## Timeouts and bounds

Every network or process operation is bounded:

| Tool | Operation | Bound |
|---|---|---|
| `dns_check` | system resolver | resolver defaults — no explicit timeout |
| `doh_test` | HTTP(S) request | 5 s |
| `trace_route` | `traceroute` / `tracepath` (`tracert` on Windows) | 20 s |
| `health_score` | TCP connect to `1.1.1.1:443` | 3 s |
| `export_results` | in-process formatting | none — see payload sizes |

The 5 s and 20 s bounds are enforced in both implementations; check the tool
descriptions in [docs/Modules.md](docs/Modules.md) for the exact error text a
timeout produces.

---

## Sequential dispatch

Each server processes one request at a time. `trace_route` is the worst case: Node
uses `execFileSync`, so a trace blocks that process for up to 20 s and later
requests queue behind it. Python uses `subprocess.run` with the same bound; neither
implementation runs traces concurrently.

Clients that need parallel diagnostics should start more than one server process.

---

## Payload sizes

- Frames are newline-delimited JSON: one response per request, nothing streamed or
  chunked.
- `doh_test` is the one place a large response costs memory. Node reads the whole
  body and keeps the first 4096 characters when it is not JSON; Python refuses
  bodies larger than 64 KiB.
- `export_results` has no output limit — the formatted string goes out in a single
  frame, so a large input produces a large frame on stdout.
- No size cap is applied to incoming request lines in either server.

---

## Memory behaviour

- Handlers return their result and retain nothing: no result history, no caches, no
  diagnostic archive.
- The tool table and input schemas are built once at startup.
- Long sessions do not accumulate state, because there is none to accumulate.

---

## Installer performance

Installation is file copying plus two small JSON writes:

- One server file per runtime is copied; the Node server needs only a
  `{"type": "module"}` manifest beside it, so `install-mcp-unified.sh` never runs
  `npm install` and works offline.
- Dependency checks are a handful of `command -v` lookups (`python3`, `node`); npm
  is not required.
- The Python installer, the Node CLI and the unified shell installer append to
  `install.log` in the install directory; the other installers write no log.
- Nothing is downloaded and no system directory is touched.

---

## Measuring locally

No performance numbers are tracked in CI, so measure on the host you care about:

```bash
# Cold start plus one tool call, end to end
time (printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"export_results","arguments":{}}}' \
  | node server/index.js > /dev/null)

# Protocol-only smoke test, no network access
python3 server/smoke_test.py
```

Compare like with like: the per-tool timeouts above cap the worst case, and any
timing that includes `trace_route` or a remote DoH endpoint is dominated by the
network rather than by the server.

---

## Planned (not implemented)

Earlier revisions of this guide set targets for components that do not exist:

- SwiftUI app launch time, frame rate and memory targets
- AppMaker project generation, module injection and ZIP compression timings
- Streaming MCP responses, resource preloading and multi-level caches
- `orjson` acceleration and Swift value-type data models

None of these are in the repository. AppMaker's status is documented in
[docs/AppMaker.md](docs/AppMaker.md); current and planned tools are listed in
[docs/Modules.md](docs/Modules.md) and [docs/ROADMAP.md](docs/ROADMAP.md).
