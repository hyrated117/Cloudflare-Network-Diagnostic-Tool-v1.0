# Troubleshooting

Everything here applies to the two MCP stdio servers (`server/index.js`,
`server/index.py`), their installers and the Node CLI. Tool behaviour is documented
in [Modules](./Modules.md); install and usage steps are in the
[README](../README.md).

## First checks

```bash
# Does the server answer a handshake at all? (no network needed)
python3 server/smoke_test.py

# Is a config pointing at a script that exists and runs?
python3 Tools/check-installers.py          # macOS/Linux
./Tools/check-installers.ps1               # Windows

# Send one frame by hand and read stdout
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  | python3 server/index.py
```

If the handshake above prints a `serverInfo` object, the server is fine and the
problem is in the client configuration.

## The server does not start

| Symptom | Cause | Fix |
|---|---|---|
| `can't open file '…/index.py'` or `Cannot find module` | config `args[0]` is a relative path | use an absolute path; re-run an installer to regenerate the config |
| `python3: command not found` / `node: not found` | runtime missing for the configured `command` | install Python 3.8+ or Node 18+, or regenerate with the other runtime |
| `SyntaxError: Cannot use import statement outside a module` | `index.js` copied without a `{"type": "module"}` manifest beside it | let an installer copy it, or add that manifest |
| Nothing on stdout, client says "server exited" | messages written to stderr instead of protocol frames | check stderr; only JSON-RPC frames belong on stdout |
| Windows: `running scripts is disabled on this system` | PowerShell execution policy | `powershell -ExecutionPolicy Bypass -File .\installers\install-mcp-unified.ps1` |

Clients resolve `args` against their **own** working directory, not the config
file's directory — that is why every installer writes absolute paths.

## Protocol errors

The servers speak JSON-RPC 2.0, one message per line:

| Code | Message | Usual cause |
|---|---|---|
| `-32700` | Parse error | not valid JSON, or a frame split across lines |
| `-32600` | Invalid Request | missing `"jsonrpc": "2.0"` or a non-string `method` |
| `-32601` | Method not found | only `initialize`, `ping`, `tools/list`, `tools/call` exist |
| `-32602` | Invalid params | missing required argument, unexpected argument, malformed URL, wrong `format` |

Notifications (messages without `id`) never get a reply — that is expected, so do
not wait for one.

## Tool errors

A tool that completes but fails returns a normal result with
`"status": "error"` and `isError: true`.

### dns_check

- `status: "error"` with a resolver message means the name did not resolve
  (typo, NXDOMAIN, or no connectivity). Only A/AAAA lookups are made.
- Node resolves IPv4 and IPv6 independently, so a host with only A records still
  reports `ok`. Both servers de-duplicate and sort the merged list.
- There is no configurable timeout for resolution — it follows the system resolver.
- A Unicode domain is converted to ASCII and reported in that form
  (`münchen.test` becomes `xn--mnchen-3ya.test`), not as the name you typed. Case and
  composition do not change the result, but the two servers use different IDNA standards
  for a few characters, so `faß.test` is `fass.test` in Python and `xn--fa-hia.test` in
  Node — see the differences table below.
- `domain is not a valid hostname` means a name that needed IDNA conversion has an empty
  label, a label over 63 characters or a leading/trailing hyphen. It is refused before the
  resolver is asked, and the result echoes the name as typed. A plain ASCII name is still
  sent to the resolver, but if the resolver rejects a malformed one (an empty or over-long
  label) both servers report this same message rather than the resolver's wording.

### doh_test

- `403`/`429` usually means rate limiting or a provider that expects `POST`; this
  tool always sends `GET` with `Accept: application/dns-json`.
- `status: "error"` also covers TLS failures and the 5 second timeout.
- Non-JSON bodies come back as `{"raw": …}`, cut to the first 4096 characters on both
  servers. Both stop reading at 64 KiB and return
  `status: "error"` with the HTTP `statusCode` for a larger body.
- URLs with embedded credentials are rejected before any request is made.

### trace_route

- `status: "unavailable"` means the utility for this platform is missing:
  `traceroute` or `tracepath` on Linux/macOS, `tracert` on Windows. `tracert` ships
  with Windows, so `unavailable` there means it was removed from `PATH`.
- On Linux/macOS, install one (`traceroute` or `iputils-tracepath`) to get results.
- Windows runs `tracert -d -h 15 -w 300`: no reverse DNS, at most 15 hops, 300 ms
  per probe, so a run fits inside the 20 second timeout.
- The command is bounded at 20 seconds; a slow path returns `status: "error"` with
  the timeout message and no `returnCode`. Because Node runs it synchronously, later
  requests in the same session wait for it.
- A run that completes returns `returnCode` and `output` on both servers, including a
  non-zero exit, which is `status: "error"` with the captured output.

### health_score

- `degraded` with `reachable: false` means the TCP connect to `1.1.1.1:443` failed
  (blocked by firewall, offline, or 1.1.1.1 unreachable from that network).
- The score is a fixed pair (95 / 64); it is not a measurement of latency or
  quality, and it does not include DNS, DoH or trace results.

### export_results

- `results` must be a JSON object — arrays produce `-32602`.
- `format` must be `json` or `csv`.
- Very large inputs produce a very large single response frame; there is no output
  size limit.

## Logging

- Servers write **nothing** to stderr during normal operation: neither
  implementation makes a logging call, so an empty stderr alongside a working
  handshake is expected, not a fault. stdout carries protocol frames and nothing
  else.
- The one exception is a fatal startup error — Node prints `Server error: …` and
  Python a traceback — so capture stderr (`2>/dev/null` hides exactly that).
- `PYTHONUNBUFFERED=1` (the installers set it) only affects output buffering; it
  does not enable logging. Timestamps appear inside tool results, not in logs.
- Only three installers log, and they write `install.log` inside
  `~/.local/cloudflare-mcp/`: `install-mcp-server.py`, `installers/cli.js` and
  `install-mcp-unified.sh`. `install-mcp-server.sh` and both PowerShell installers
  write no log, so `%APPDATA%\Cloudflare-MCP\install.log` never appears.

## Performance

- Requests are handled one at a time per process; a 20 second `trace_route` blocks
  the queue. Start a second server process if you need parallelism.
- No results are cached or retained between calls, so repeated runs repeat the
  network work.
- Both servers cap a DoH response at 64 KiB and do not buffer a larger body.

## Node and Python differences

| Behaviour | Node | Python |
|---|---|---|
| CSV cell holding a number | `JSON.stringify`, so `1.0` becomes `1` | `json.dumps`, so `1.0` stays `1.0` |
| `dns_check` with `ß` or `ς` | UTS#46: `xn--fa-hia.test`, `xn--3xa.test` | IDNA2003: `fass.test`, `xn--4xa.test` |

Timestamps are not a difference: both servers stamp results
`YYYY-MM-DDTHH:MM:SS.mmmZ` (UTC, milliseconds), `doh_test` echoes the `url` exactly as
supplied on both (`https://host` keeps no trailing slash), and `dns_check` addresses are
de-duplicated and sorted on both.

If a client validates result payloads strictly, run the same check against both
servers before filing a bug.

## Getting help

1. Search [existing issues](https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/issues).
2. Review [Architecture](./Architecture.md) and [Modules](./Modules.md).
3. Open an issue with the request frame, the response (or stderr) and your
   runtime versions.
4. Security problems: follow [SECURITY.md](../SECURITY.md) instead of a public issue.
