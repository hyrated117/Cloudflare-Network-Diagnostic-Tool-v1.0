# Contributing

Thank you for your interest in contributing.

## Getting started

1. Fork the repository and create a focused branch.
2. Make your changes and add tests where appropriate.
3. Run the checks below.
4. Open a pull request with a clear summary and testing details.

## Checks

CI runs these on Linux for every push and pull request:

```bash
node --check server/index.js                      # JavaScript syntax
node --check installers/cli.js
python3 -m compileall -q server installers Tools  # Python syntax
python3 server/smoke_test.py                      # JSON-RPC smoke test, no network
python3 Tools/validate-json.py .                  # JSON syntax
python3 Tools/check-links.py                      # no broken relative doc links
python3 Tools/check-installers.py                 # installers write launchable configs
Tools/build-package.sh v0.0.0-ci                  # build the release archive
python3 Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack
python3 Tools/check-installers.py --installers-root dist/pack
```

The last three build the release tarball with `Tools/build-package.sh` — the same
script `release.yml` uses — check its contents, then install from the extracted copy
and handshake with the packaged server, so packaging breakage fails on a push rather
than at tag time.

A second job on Windows parses `installers/*.ps1` and runs
`Tools/check-installers.ps1`. It then downloads the archive the Linux packaging job
uploaded — the same bytes, not a second build — checks its SHA-256, extracts it and
runs the packaged PowerShell installers against it:

```powershell
python Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack --expect-checksum
./Tools/check-installers.ps1 -InstallersRoot dist/pack
```

## Conventions

- Keep the Node (`server/index.js`) and Python (`server/index.py`) servers
  behaviourally consistent; both are dependency-free and use the standard library.
- Protocol responses go to stdout as single-line JSON; logs go to stderr.
- Every network or process operation needs a timeout, and every tool must return a
  `status` value instead of throwing.
- Update the documentation with the code. The docs describe only what exists;
  planned work belongs in [ROADMAP.md](./ROADMAP.md) or
  [docs/ROADMAP.md](./docs/ROADMAP.md).
- Do not add dependencies for the servers, and do not commit credentials or
  collected diagnostic data.
