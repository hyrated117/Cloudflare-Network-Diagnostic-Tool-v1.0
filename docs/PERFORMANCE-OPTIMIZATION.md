# Performance Notes

Where the time goes in the two MCP servers, what bounds each tool, and how to make a run
faster. Objectives and the measurement approach live in
[PERFORMANCE-GUIDE.md](../PERFORMANCE-GUIDE.md); this page is about the implementation.

## Where the time goes

| Tool | Dominant cost | Bound in code |
|---|---|---|
| `dns_check` | resolver round trip(s) — Node issues A and AAAA concurrently, Python uses one `getaddrinfo` | resolver defaults |
| `doh_test` | TLS handshake plus response body | 5 s (`AbortSignal.timeout` / `urlopen(timeout=5)`) |
| `trace_route` | hop discovery; `traceroute` then `tracepath`, or `tracert` alone on Windows | 20 s per attempt |
| `health_score` | TCP connect to `1.1.1.1:443` | 3 s |
| `export_results` | string building | none required |

`trace_route` dominates a run. It spawns a child process (Node uses `spawnSync`, so
the event loop is blocked for the whole call) and waits for hop discovery to finish or
for the 20 s timeout. On Windows the single `tracert` candidate is bounded by its own
`-h 15 -w 300` flags, so the run ends by hop count or by the timeout, whichever comes
first.

## Sequential dispatch

Both servers read stdin line by line and handle one request at a time; there is no
worker pool or request queue. A long `trace_route` therefore holds up every other call on
that connection. If you need parallel probes, run several server processes, one client
session each, rather than multiplexing through one connection.

## Payload and memory

- There is no caching layer: every call repeats its network work.
- DoH bodies: both servers stop reading at 64 KiB and return a `status: "error"` result
  for a larger body, so neither buffers it. Node keeps only the first 4096 characters when
  the response is not JSON.
- JSON and CSV exports are assembled as a single string in memory. Results are small, so
  there is no streaming path — and no cap on `export_results` output either.

## Making a run faster

- Skip `trace_route` unless you need hop-level data; it is the only slow tool.
- `dns_check` and `doh_test` answer different questions (system resolver versus a
  specific DoH endpoint) and are both fast — run both instead of retrying one.
- Keep one long-lived server process. Startup only loads the standard library, but a new
  process repeats the `initialize` handshake and the client's config load.
- Do not retry a Windows `"unavailable"` trace; it is deterministic.

## Measuring

- Time each `tools/call` on the client side; both servers stamp every result with a
  `timestamp`, so a simple before/after diff is enough to spot slow calls.
- `python3 server/smoke_test.py` exercises the protocol without touching the network, so
  it isolates startup and framing from network time.
- Compare Node and Python on the same destination before picking one: the differences are
  in argument handling and DoH limits, not in timeouts.
