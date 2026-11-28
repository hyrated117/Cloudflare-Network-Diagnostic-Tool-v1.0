# Diagnostic Tools

The project ships two MCP servers that expose the **same five tools**. There is no
SwiftUI application, WARP module, DNSSEC module or resolver benchmark in this
repository — see [Planned tools](#planned-tools-not-implemented).

| Server | Runtime | Entry point | Dependencies |
|---|---|---|---|
| Node | Node.js 18+, ES module | `server/index.js` | none — `node:child_process`, `node:dns`, `node:net`, `node:url` only |
| Python | Python 3.8+ | `server/index.py` | none — standard library only |

Both implement JSON-RPC 2.0 over newline-delimited stdio (`initialize`, `ping`,
`tools/list`, `tools/call`); see [Architecture](./Architecture.md) for the transport
details. Every response is JSON-RPC and stdout carries nothing else; the servers
make no logging calls, so stderr stays empty unless startup fails.

## Tool summary

| Tool | Arguments | Result status values |
|---|---|---|
| `dns_check` | `domain` (string, required) | `ok`, `error` |
| `doh_test` | `url` (HTTP(S) URL, required) | `ok`, `error` |
| `trace_route` | `destination` (host or IP, required) | `ok`, `error`, `unavailable` |
| `health_score` | none | `healthy`, `degraded` |
| `export_results` | `format` (`json`\|`csv`), `results` (object) | `ok` |

All results carry `tool` and an ISO-8601 `timestamp` in UTC with milliseconds, for
example `2026-11-24T23:10:02.578Z`. Both servers emit that same shape;
`Tools/check-conformance.py` and `Tools/test_parity.py` assert the format instead of
ignoring the field.

---

## dns_check

Resolves a domain to IPv4 and IPv6 addresses.

- **Node:** `dns.promises.resolve4` and `resolve6` run concurrently; addresses are
  de-duplicated and results merged.
- **Python:** `socket.getaddrinfo` returns all address families.
- **Both:** a Unicode domain is converted to ASCII before resolution. Case is lowered and
  the name is NFC-normalised first, then Python's `idna` codec (IDNA2003) and Node's
  `domainToASCII` (UTS#46) encode it. Most names come out the same (`münchen.test` is
  `xn--mnchen-3ya.test` on both), but the two standards map a few characters differently:
  `faß.test` is `fass.test` in Python and `xn--fa-hia.test` in Node, and `ς.test` is
  `xn--4xa.test` and `xn--3xa.test`. Each server reports the name it resolved. A name that
  needed conversion but is not a valid hostname (empty label, a label over 63 characters,
  a leading or trailing hyphen) is refused with `domain is not a valid hostname` and the
  name as typed, before any lookup. A plain ASCII name still goes to the resolver; if the
  resolver rejects it and the labels are malformed (an empty label, one over 63
  characters), both servers report the same `domain is not a valid hostname` result
  instead of the resolver's own wording, which differs between the two runtimes.

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"dns_check","arguments":{"domain":"example.com"}}}
```

```json
{"tool":"dns_check","domain":"example.com","status":"ok",
 "addresses":["93.184.215.14"],"timestamp":"2026-11-24T23:10:02.578Z"}
```

A domain that resolves nothing returns `"status": "error"` with an `error` string
containing the resolver message. Only A/AAAA lookups are performed — MX, NS, SOA
and TXT records are not queried.

## doh_test

Sends a GET request to a caller-supplied DNS-over-HTTPS endpoint.

- Accepts `http` and `https` only; URLs containing credentials are rejected.
- Sends `Accept: application/dns-json` and `User-Agent: Cloudflare-Diagnostic-Tool/1.0`.
- 5 second timeout. The body is parsed as JSON; non-JSON bodies are returned as a
  `raw` string (Node keeps at most the first 4096 characters, Python the whole body).
- Both servers stop reading at 64 KiB. A larger body returns a normal result with
  `"status": "error"`, the HTTP `statusCode` and the message
  `DoH response exceeded 64 KiB limit` — a tool result rather than a JSON-RPC error,
  because the body size is the remote endpoint's choice.

```json
{"name":"doh_test","arguments":{"url":"https://cloudflare-dns.com/dns-query?name=example.com&type=A"}}
```

The result includes `statusCode` and the decoded `response`. Note that any HTTP(S)
URL is fetched, not only Cloudflare endpoints — treat the tool as a general request
helper when reviewing what a client can reach.

## trace_route

Runs the platform's traceroute: `traceroute`, falling back to `tracepath` on
Linux/macOS, and `tracert -d -h 15 -w 300` on Windows.

- 20 second timeout, argv array (no shell), destination must contain no whitespace
  and must not start with `-`.
- `status: "unavailable"` when the platform's utility is missing.

Node returns the tracer's stdout, and on failure puts the failure text in `error`
with no `returnCode`. Python returns `returnCode` plus stdout, or stderr when stdout
is empty, and reports `status: "error"` for a non-zero exit.

## health_score

A single TCP connect to `1.1.1.1:443` with a 3 second timeout — it is a reachability
probe, not a composite score:

```json
{"tool":"health_score","score":95,"status":"healthy","reachable":true,"timestamp":"…"}
```

`95`/`healthy` when the connection succeeds, `64`/`degraded` when it fails. No DNS
latency, WARP status or location data feeds into this value.

## export_results

Formats a caller-supplied result object. It never writes files — the formatted text
is returned in `content`. See [Export](./Export.md).

---

## Behavioural differences between the two servers

Both servers accept the same requests and return the same result shape. Unknown
tools, missing required arguments and unexpected arguments are rejected by both
with `-32602`. These differences remain:

| Area | Node | Python |
|---|---|---|
| `trace_route` failure | `error` with the failure text, no `returnCode` | `error` with `returnCode` and the captured output |
| `doh_test` echoed `url` | normalised (`https://host` becomes `https://host/`) | exactly as supplied |
| `dns_check` address order | resolver order | sorted |

## Planned tools (not implemented)

The following appeared in earlier versions of this documentation and have **no code
in the repository**: DNSSEC validation, resolver benchmarking, WARP diagnostics,
MX/NS/SOA queries, Cloudflare API/WAF/Radar/Zero Trust integration, plugin manifests
and a composite health score. They are tracked as future work in
[docs/ROADMAP.md](./ROADMAP.md) and are not available from either server.
