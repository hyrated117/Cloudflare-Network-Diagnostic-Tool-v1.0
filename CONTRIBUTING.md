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
python3 Tools/check-conformance.py                # Python and Node answer identically
python3 Tools/check-version.py                    # version sites, VERSION and changelog agree
python3 Tools/validate-json.py .                  # JSON syntax
python3 Tools/check-links.py                      # no broken relative doc links
python3 Tools/check-installers.py                 # shell and CLI installers write launchable configs
Tools/build-package.sh v0.0.0-ci                  # build the release archive
python3 Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack
python3 Tools/check-installers.py --installers-root dist/pack
```

The last three build the release tarball with `Tools/build-package.sh` — the same
script `release.yml` uses — check its contents, then install from the extracted copy
and handshake with the packaged server, so packaging breakage fails on a push rather
than at tag time.

A second job on Windows parses `installers/*.ps1` and runs
`Tools/check-installers.ps1`. It also runs a real `trace_route` through `tracert`
(`Tools/check-conformance.py --live-trace 127.0.0.1`), so the Windows tracer path is
exercised instead of only handshaked. It then downloads the archive the Linux
packaging job uploaded — the same bytes, not a second build — checks its SHA-256,
extracts it and runs the packaged PowerShell installers against it:

```powershell
python Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack --expect-checksum
./Tools/check-installers.ps1 -InstallersRoot dist/pack
```

`release.yml` calls this workflow as its `checks` job and gates the publishing job on
it, so a tag whose commit fails any of the above cannot release anything.

A `lint` job runs `actionlint` over the workflows — its image bundles `shellcheck`, so
the shell inside every `run:` block is checked, including the release steps — and
`shellcheck` 0.11.0 at its default severity over `installers/*.sh` and `Tools/*.sh`.
The job installs that version from its pinned, checksum-verified release tarball rather
than using whatever the runner image ships, so the findings only change when someone
bumps `SHELLCHECK_VERSION` and `SHELLCHECK_SHA256` together. The three scripts are
clean today, so a finding there is something you just introduced; suppress it with a
`# shellcheck disable=SCXXXX` comment and a reason only when the warning is genuinely
wrong.

## Version bumps

`VERSION` at the repository root holds the version. The installers are copied to a
user's machine as loose files and the servers are launched directly, so the twelve
literals in ten files cannot read it at runtime; `Tools/stamp-version.py` writes it
into all of them. To bump:

1. Edit `VERSION` (for example `1.0.2`).
2. Run `python3 Tools/stamp-version.py` and commit the result; `--dry-run` lists what
   would change instead of writing.
3. Name the version in `CHANGELOG.md` — a dated `## [1.0.2] - YYYY-MM-DD` section below
   `## [Unreleased]` — and add `release/v1.0.2/release-notes.md`, which becomes the
   release body.
4. Tag `v1.0.2` and push the tag. `release.yml` refuses a tag that disagrees with
   `VERSION`, and both must be exactly `MAJOR.MINOR.PATCH` with no suffix: a
   `v1.0.2-rc1` tag is rejected, so tag the final version directly. It runs on a
   pinned Python 3.12 rather than the runner image's `python3`, builds
   `dist/v<version>` from `VERSION` and runs `check-version.py` before packaging.

`python3 Tools/check-version.py` checks all of it locally: it fails when a site
drifts from `VERSION`, when the changelog's newest dated section names another
version, or when that version's release notes are missing or mis-titled.

## Conventions

- Keep the Node (`server/index.js`) and Python (`server/index.py`) servers
  behaviourally consistent; both are dependency-free and use the standard library.
- Protocol responses go to stdout as single-line JSON; nothing diagnostic may go
  to stdout. The servers make no logging calls — stderr carries only fatal startup
  errors.
- Every network or process operation needs a timeout, and every tool must return a
  `status` value instead of throwing.
- Update the documentation with the code. The docs describe only what exists;
  planned work belongs in [ROADMAP.md](./ROADMAP.md) or
  [docs/ROADMAP.md](./docs/ROADMAP.md).
- Do not add dependencies for the servers, and do not commit credentials or
  collected diagnostic data.
