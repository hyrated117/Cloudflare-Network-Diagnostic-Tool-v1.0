# Implementation Checklist

Pre-release verification for this repository. Items marked **(automated)** run in
`.github/workflows/ci.yml`; everything else needs a human on the target platform.
The repository ships two MCP stdio servers, their installers and documentation — see
[README.md](./README.md) and [docs/Architecture.md](./docs/Architecture.md).

## 1. Repository contents

- [x] Root files present: `.gitignore`, `README.md`, `LICENSE`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`
- [x] Servers in `server/` (`index.js`, `index.py`), installers in `installers/`, checks in `Tools/`
- [x] `.github/` contains workflows, issue templates and the PR template
- [x] No `src/`, `tests/` or `.env.example` placeholders — the layout above is the real one
- [ ] Documentation index and tool reference current ([docs/README.md](./docs/README.md))

## 2. Servers

- [x] Both servers expose the same five tools (`dns_check`, `doh_test`, `trace_route`, `health_score`, `export_results`)
- [ ] Node/Python differences documented and intentional (see [docs/Modules.md](./docs/Modules.md))
- [x] Protocol frames on stdout only; logging on stderr
- [x] DoH (5 s), trace (20 s) and TCP probe (3 s) timeouts in place; DNS uses resolver defaults
- [x] No runtime dependencies in `server/package.json`

## 3. Installers

- [x] Generated configs use absolute script paths
- [x] No npm/pip install step; the Node install writes a `{"type": "module"}` manifest
- [x] Installer configs launch the server **(automated, Linux)**
- [ ] Windows installers verified on a real Windows host **(automated in the Windows CI job)**
- [ ] Shell and PowerShell installers still agree on config shape

## 4. Documentation

- [x] No broken relative links **(automated: `Tools/check-links.py`)**
- [x] Docs describe only shipped behaviour; planned work is labelled as such
- [ ] README install and usage steps verified against a fresh clone
- [ ] `CHANGELOG.md` reflects only work that exists

## 5. CI

- [x] Linux job: syntax, smoke test, JSON, documentation links, installer configs **(automated)**
- [x] Packaging jobs: build the release archive, check its contents with `Tools/check-archive.py`, then install from the extracted tarball and handshake with the packaged server — `Tools/check-installers.py` on Linux, `Tools/check-installers.ps1 -InstallersRoot` on Windows **(automated)**
- [x] Windows job: PowerShell parser, installer configs **(automated)**
- [ ] CodeQL, dependency review and security scan green on the release commit

## 6. Release

- [ ] `CHANGELOG.md` has an entry for the version being released
- [ ] Version bumped in `server/package.json` and `installers/package.json`
- [ ] Tag `vX.Y.Z` created and pushed (no tag exists yet)
- [ ] Release workflow built `mcp-installer-pack.tar.gz` and `SHA256SUMS`
- [ ] Checksums verified after download

## 7. Security

- [x] No secrets, tokens or credentials in the tree
- [x] Installers write only to user-scoped directories and never elevate
- [ ] New or changed tools reviewed against the tool list in [SECURITY.md](./SECURITY.md)
