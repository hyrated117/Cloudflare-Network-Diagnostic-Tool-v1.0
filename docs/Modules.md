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
  de-duplicated and the results merged.
- **Python:** `socket.getaddrinfo` returns all address families.
- **Both:** addresses are de-duplicated and sorted, so the two servers report the same
  order and `Tools/test_parity.py` checks every list against a sorted copy of itself.
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
- 5 second timeout. The body is parsed as JSON; a non-JSON body is returned as a
  `raw` string, and both servers keep at most the first 4096 characters of it.
- Both servers stop reading at 64 KiB. A larger body returns a normal result with
  `"status": "error"`, the HTTP `statusCode` and the message
  `DoH response exceeded 64 KiB limit` — a tool result rather than a JSON-RPC error,
  because the body size is the remote endpoint's choice.

```json
{"name":"doh_test","arguments":{"url":"https://cloudflare-dns.com/dns-query?name=example.com&type=A"}}
```

The result includes `statusCode` and the decoded `response`. The echoed `url` is the
string the client sent, unchanged — `https://host` keeps no trailing slash — on both
servers. Note that any HTTP(S)
URL is fetched, not only Cloudflare endpoints — treat the tool as a general request
helper when reviewing what a client can reach.

## trace_route

Runs the platform's traceroute: `traceroute`, falling back to `tracepath` on
Linux/macOS, and `tracert -d -h 15 -w 300` on Windows.

- 20 second timeout, argv array (no shell), destination must contain no whitespace
  and must not start with `-`.
- `status: "unavailable"` when the platform's utility is missing.

Both servers run the tracer to completion and return the same fields: `returnCode` and
`output` (stdout, else stderr, else `No output captured`). A non-zero exit is
`status: "error"` with those same fields. If the utility exists but cannot run — a
timeout, or a binary that cannot be executed — the result is `status: "error"` with
`error` instead of a return code.

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

Both servers accept the same requests and return the same result shape, and no result
field differs between them: `doh_test` echoes the URL as supplied, `dns_check`
de-duplicates and sorts addresses, `timestamp` has one format, and `trace_route` reports
`returnCode`/`output` or `error` the same way on both.

Two differences remain in values the servers produce themselves:

| Area | Node | Python |
|---|---|---|
| CSV cell holding a number | `JSON.stringify`, so `1.0` becomes `1` | `json.dumps`, so `1.0` stays `1.0` |
| `dns_check` with `ß` or `ς` | UTS#46: `xn--fa-hia.test`, `xn--3xa.test` | IDNA2003: `fass.test`, `xn--4xa.test` |

The CSV one covers any non-string cell whose JSON form contains a float: a nested object
holding `1.0` renders as `{"a":1}` in Node and `{"a":1.0}` in Python. Node also parses
every request number as a double, so an integer above 2^53 has lost precision before a
tool sees it. String cells are identical on both — see [Export](./Export.md). The IDNA
difference is described under [`dns_check`](#dns_check).

Error text a failed call passes through from the resolver, the DoH endpoint or the
operating system is returned verbatim, so it differs between the runtimes and the parity
corpus only compares failures it can make deterministic.

## Planned tools (not implemented)

The following appeared in earlier versions of this documentation and have **no code
in the repository**: DNSSEC validation, resolver benchmarking, WARP diagnostics,
MX/NS/SOA queries, Cloudflare API/WAF/Radar/Zero Trust integration, plugin manifests
and a composite health score. They are tracked as future work in
[docs/ROADMAP.md](./ROADMAP.md) and are not available from either server.
