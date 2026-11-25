# Privacy

## What the tools send over the network

The MCP servers are local processes. They transmit only what a tool call asks for:

| Tool | Network activity |
|---|---|
| `dns_check` | A/AAAA resolution for the supplied domain via the system resolver |
| `doh_test` | A single GET to the supplied HTTP(S) DNS-over-HTTPS URL |
| `trace_route` | The route probes performed by the system `traceroute`/`tracepath` |
| `health_score` | A TCP connection to `1.1.1.1:443` |
| `export_results` | none |

Anything the client passes in those arguments — domains, URLs, destinations — leaves
the machine as part of that request and is visible to the resolver, the DoH endpoint
or the network path. There is no other outbound traffic.

## What is stored

- **No telemetry, analytics or tracking.** Neither server phones home.
- **No diagnostic history.** Results are returned to the client and not persisted.
- **No IP addresses, personal data or result archives** are written by the servers.
- **No logs are written.** Neither server makes a logging call, so nothing about a
  request is recorded and stderr stays empty unless startup fails.

## Installer footprint

Installing writes only inside a user-scoped directory:

- macOS/Linux: `~/.local/cloudflare-mcp/` (server copy, `config/mcp-server.json`,
  `config/mcp-client.json`, plus an `install.log` written by the Python installer,
  the Node CLI and the unified shell installer)
- Windows: `%APPDATA%\Cloudflare-MCP\` (same layout)

No system directories are modified and no privileges are elevated. The generated
configs contain absolute paths and, for Python, `PYTHONUNBUFFERED=1` — no secrets,
tokens or identifiers.

## Third parties

There is no third-party data sharing, because nothing is collected. If you point
`doh_test` at a specific provider, that provider sees the request you chose to send;
its own privacy policy applies.

## Planned (not implemented)

Earlier documentation described optional cloud sync, encrypted cloud storage,
anonymised aggregate analytics, device metadata collection and a GDPR portal. None
of these features exist in this repository — there is no account system, no backend
and no data upload path.

## Reporting a concern

Use [GitHub private vulnerability reporting](https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/security/advisories/new)
as described in [SECURITY.md](../SECURITY.md).
