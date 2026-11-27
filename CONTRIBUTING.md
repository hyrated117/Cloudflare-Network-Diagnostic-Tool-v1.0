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
python3 Tools/check-dependabot.py                 # .github/dependabot.yml parses and Dependabot would accept it
python3 Tools/check-workflows.py                  # every pull request is scanned, every job has a timeout, every use is pinned
python3 Tools/check-links.py                      # no broken relative doc links
python3 Tools/check-installers.py                 # shell and CLI installers write launchable configs
Tools/build-package.sh v0.0.0-ci                  # build the release archive
python3 Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack
python3 Tools/check-installers.py --installers-root dist/pack
```

`check-dependabot.py` is the one check that needs a package: `python3 -m pip install
pyyaml==6.0.4`. CI installs that pinned version before running it, and every other tool
here is stdlib-only. It checks the keys Dependabot needs and reports unrecognized ones
as warnings rather than failures (GitHub keeps adding keys), and it exists because
GitHub reads `dependabot.yml` only from the default branch and says nothing when the
file is malformed, so a typo would silently stop the action updates.

`Tools/check-workflows.py` uses the same pinned PyYAML and asserts three things that
fail silently on GitHub. These branches are stacked, so a pull request targets the
branch below it, and a `branches:` filter on `pull_request` in `ci.yml`, `codeql.yml`,
`dependency-review.yml` or `security-scan.yml` skips the review while the file still
parses and GitHub simply never creates the run; the `push` trigger is left alone
because it scans a branch once, when it lands. A job in any workflow with no
`timeout-minutes` (or a value that is not a positive whole number) fails the check,
because it would inherit the six-hour default; a job that calls a reusable workflow is
skipped, since its timeout belongs to the callee. A `uses:` that is not
`owner/repo@<40-hex SHA>` or `docker://...@sha256:<64-hex digest>` fails too, so a
tag-pinned action cannot slip in; a local `./...` workflow is exempt because there is
nothing to pin.

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

`verify-release.yml` covers what the publishing job cannot: it runs on
`release: published` (or when dispatched for an existing tag), downloads
`mcp-installer-pack.tar.gz` and `SHA256SUMS` from the release, reruns
`check-archive.py --expect-checksum` on them, extracts the archive and handshakes with
the packaged installers. The publishing job proves the local archive before upload;
this proves the bytes GitHub serves, so a truncated or mismatched upload fails a check
instead of a user. It checks out the default branch, so a fixed verifier can be
dispatched against an already published release.

A `lint` job runs `actionlint` over the workflows — its image bundles `shellcheck`, so
the shell inside every `run:` block is checked, including the release steps — and
`shellcheck` 0.11.0 at its default severity over `installers/*.sh` and `Tools/*.sh`.
The job installs that version from its pinned, checksum-verified release tarball rather
than using whatever the runner image ships, so the findings only change when someone
bumps `SHELLCHECK_VERSION` and `SHELLCHECK_SHA256` together. The three scripts are
clean today, so a finding there is something you just introduced; suppress it with a
`# shellcheck disable=SCXXXX` comment and a reason only when the warning is genuinely
wrong.

Every job carries a `timeout-minutes`, so a hung download or trace fails it instead of
holding a runner until GitHub's six-hour default: 15 for `validate`, `package` and
`lint`, 30 for the Windows job, which runs the live trace, and 20 for `release.yml`'s
release job.

The actions in every workflow are pinned to commit SHAs, with the release they came
from in a comment. `.github/dependabot.yml` raises a weekly `github-actions` pull
request that moves the SHA and its comment together: take those, rather than editing
a pin by hand or pointing it back at a tag, so an already cut tag keeps running the
code it was tested with.

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
