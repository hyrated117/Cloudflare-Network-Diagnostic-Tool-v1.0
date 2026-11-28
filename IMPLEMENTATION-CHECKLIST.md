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
- [x] Documentation index and tool reference current: every page in
  [docs/README.md](./docs/README.md) exists and its tool list matches
  [docs/Modules.md](./docs/Modules.md)

## 2. Servers

- [x] Both servers expose the same five tools (`dns_check`, `doh_test`, `trace_route`, `health_score`, `export_results`)
- [x] Node/Python differences documented and intentional (the "Behavioural differences
  between the two servers" section of [docs/Modules.md](./docs/Modules.md))
- [x] Protocol frames on stdout only; no logging calls, stderr silent except startup errors
- [x] DoH (5 s), trace (20 s) and TCP probe (3 s) timeouts in place; DNS uses resolver defaults
- [x] No runtime dependencies in `server/package.json`

## 3. Installers

- [x] Generated configs use absolute script paths
- [x] No npm/pip install step; the Node install writes a `{"type": "module"}` manifest
- [x] Installer configs launch the server in the tree — the shell, unified-shell, Python
  and Node CLI installers **(automated: `Tools/check-installers.py`)**
- [x] PowerShell installers handshaked on a Windows runner **(automated:
  `Tools/check-installers.ps1` in the `windows` job)**
- [x] Shell and PowerShell installers agree on config shape: both checks read
  `config/mcp-server.json` and `config/mcp-client.json` and require an absolute,
  existing script

## 4. Documentation

- [x] No broken relative links **(automated: `Tools/check-links.py` in `Validate`)**
- [x] Docs describe only shipped behaviour; planned work is labelled as such
- [ ] README install and usage steps verified against a fresh clone
- [ ] `CHANGELOG.md` reflects only work that exists

## 5. CI

- [x] Linux `Validate` job: syntax (`node --check` on both entries, `compileall`, `bash -n`
  on every shell script), Python smoke test, Python/Node conformance, version
  consistency, JSON, the pinned PyYAML install with the Dependabot check, the workflow
  checks and their self-test, both version self-tests, documentation links, installer
  configs **(automated)**
- [x] `lint` job: actionlint pinned by image digest, with its bundled shellcheck over
  every `run:` block, then shellcheck 0.11.0 from its checksum-verified tarball over
  `installers/*.sh` and `Tools/*.sh` **(automated)**
- [x] Packaging job: build the release archive, check its contents with
  `Tools/check-archive.py`, then install from the extracted tarball and handshake with
  the packaged server — `Tools/check-installers.py` (four installers) on Linux and
  `Tools/check-installers.ps1 -InstallersRoot` on Windows **(automated)**
- [x] Windows job: PowerShell parser, a real `tracert` trace, installer configs **(automated)**
- [ ] CodeQL, dependency review and security scan green on the release commit

## 6. Release

- [ ] `VERSION` edited and `Tools/stamp-version.py` run — one edit and one command write
  all ten sites (twelve literals); `--dry-run` lists what would change
- [ ] `Tools/check-version.py` green **(automated: `Check version consistency`)**: it
  fails while any site drifts from `VERSION`, the newest dated `CHANGELOG.md` section
  names another version, or `release/v<version>/release-notes.md` is missing or its
  title does not name that version
- [ ] `CHANGELOG.md` has a dated section for the version being released
- [ ] `release/v<version>/release-notes.md` added with the version in its title — it
  becomes the release body, and `## Commits` is appended only when an earlier tag exists
- [ ] Tag `v<version>` created and pushed; the tag and `VERSION` must both be bare
  `MAJOR.MINOR.PATCH`, since `release.yml` rejects a suffix
- [ ] The release job built `mcp-installer-pack.tar.gz` and `SHA256SUMS` and published
  them, after running `check-version.py` and `check-archive.py --expect-checksum`
- [ ] `verify-release.yml` passed on the published release: checksum, required files, the
  tag's version, extraction and the installer handshake on Linux, plus the archive check
  and `.ps1` handshake on Windows

## 7. Security

- [x] No secrets, tokens or credentials in the tree
- [x] Installers write only to user-scoped directories and never elevate
- [ ] New or changed tools reviewed against the tool list in [SECURITY.md](./SECURITY.md)
