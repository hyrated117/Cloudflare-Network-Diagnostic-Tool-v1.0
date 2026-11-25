# AppMaker Generator — Planned, Not Implemented

> **Status:** not implemented. There is no AppMaker code, template directory or
> generator CLI in this repository.

Earlier revisions of this file documented a SwiftUI project generator
(`ProjectGenerator`, `GenerationConfig`, `ModuleInjector`, `UUIDGenerator`,
`ZipCompressor`, `cloudflare-mcp appmaker generate …`). That API was never built:
`grep` for `appmaker`, `ProjectGenerator` or `GenerationConfig` finds only
documentation, and no `templates/` directory exists.

## What the repository actually provides

- Two MCP stdio servers: `server/index.js` and `server/index.py`
- Installers and a Node CLI (`node installers/cli.js install|start|status`) — no
  `cloudflare-mcp` executable is installed
- Diagnostic tools: `dns_check`, `doh_test`, `trace_route`, `health_score`,
  `export_results`

See [Modules](./Modules.md), [Architecture](./Architecture.md) and
[docs/ROADMAP.md](./ROADMAP.md) for the current state and future plans.

## What shipping it would require

A real generator would need, at minimum:

1. A template tree and a templating engine.
2. A project writer that creates and validates an Xcode project.
3. Module injection into generated source.
4. Tests that build a generated project in CI.

Until those exist, anything referencing AppMaker should be treated as aspirational.
