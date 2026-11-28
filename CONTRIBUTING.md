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
python3 Tools/test_parity.py                      # ...and on 300 seeded random requests
python3 Tools/check-version.py                    # version sites, VERSION and changelog agree
python3 Tools/validate-json.py .                  # JSON syntax
python3 Tools/check-runtimes.py                   # the validate matrix runs README's minimums
python3 Tools/test_check_runtimes.py              # each rule fails its break, passes a sound matrix
python3 Tools/check-dependabot.py                 # .github/dependabot.yml parses and Dependabot would accept it
python3 Tools/test_check_dependabot.py            # each rule fails a bad config, passes a sound one
python3 Tools/check-workflows.py                  # triggers, timeouts, pins, broken continuations
python3 Tools/test_check_workflows.py             # each rule fails its break and passes a sound workflow
python3 Tools/test_check_pins.py                  # every pin-audit rule, offline
python3 Tools/test_check_actionlint_image.py      # every image-check rule, offline
python3 Tools/test_windows_trace_route.py         # the Windows tracert branch, forced
python3 Tools/test_injection.py                   # no flag or shell injection via trace/dns
python3 Tools/test_check_stack.py                 # every stack-guard rule, on temp repos
python3 Tools/test_check_version.py               # every failure the version checker promises
python3 Tools/test_stamp_version.py               # a bad VERSION writes nothing; a bump reads back consistent
python3 Tools/check-links.py                      # no broken relative doc links
python3 Tools/check-installers.py                 # shell, Python and CLI installers write launchable configs
Tools/build-package.sh v0.0.0-ci                  # build the release archive
python3 Tools/check-archive.py dist/v0.0.0-ci/mcp-installer-pack.tar.gz --extract-to dist/pack
python3 Tools/test_check_archive.py               # each archive rule fails a bad pack, passes a good one
python3 Tools/check-installers.py --installers-root dist/pack
```

CI runs that list twice: on the release environment (Node 20, Python 3.12) and on the
floor `README.md` promises (Node 18, Python 3.8). A tool that quietly needs a newer
runtime, a stdlib function that only exists from 3.9 or a runtime-specific output now
fails `Validate` instead of the user. Both legs pin PyYAML `6.0.3`, the newest release
that installs on 3.8 — `6.0.4` requires 3.10.

`check-dependabot.py` is the one check that needs a package: `python3 -m pip install
pyyaml==6.0.3`. CI installs that pinned version before running it, and every other tool
here is stdlib-only. It checks the keys Dependabot needs and reports unrecognized ones
as warnings rather than failures (GitHub keeps adding keys), and it exists because
GitHub reads `dependabot.yml` only from the default branch and says nothing when the
file is malformed, so a typo would silently stop the action updates.

`Tools/check-workflows.py` uses the same pinned PyYAML and asserts four things that
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
nothing to pin. A `run:` block line that ends in a continuation character followed by
whitespace fails too — a backtick in pwsh, a backslash in bash — because the shell ends
the line there and runs the rest of the command as its own statement, which only a
runner would report, and only at run time; which character to look for comes from the
shell the block runs in. Only code counts, so quoted text, comments, here-documents and
here-strings are masked before a match is trusted. `Tools/test_check_workflows.py`
pins both halves of every rule — a filtered `pull_request`, a job without a timeout and
a tag-pinned `uses:` each fail while an unfiltered trigger, a positive timeout and a
SHA- or digest-pinned `uses:` pass, and a here-document body and a trailing comment
stay quiet while a real continuation break in either shell still fails — and the
`Validate` job runs it as `Self-test the workflow checks`; it is stdlib-only, so it runs
before PyYAML is installed.

`Tools/check-pins.py` is the one audit that needs the network, so it is not a
`Validate` step: it asks the GitHub API whether every `owner/repo[/subpath]@SHA  # vX.Y.Z`
resolves to that commit — subpaths such as `github/codeql-action/init` are not part of
the repository name, and an annotated release tag has to be dereferenced before it can
be compared — and asks Docker Hub whether the actionlint digest, which Dependabot cannot
update, is the image the tag serves. `Tools/test_check_pins.py` pins those rules offline
with fake registries and runs in `Validate` as `Self-test the pin check`; set
`GITHUB_TOKEN` to lift the unauthenticated API quota when you run the audit itself.

`Tools/check-actionlint-image.py` closes the other half of that gap: it pulls the image
`lint` runs by the digest pinned in `ci.yml`, verifies each layer's sha256, extracts the
`actionlint` and `shellcheck` files and runs them from the repository root, exactly as
the image's entrypoint does under `docker://`. That makes the Docker step checkable on a
machine without a daemon; `Tools/test_check_actionlint_image.py` pins its rules offline
and runs in `Validate` as `Self-test the image check`.

`Tools/test_windows_trace_route.py` covers the one branch that otherwise runs only on
Windows: it forces `trace_route` down the `tracert` path in both servers and puts a fake
`tracert` on `PATH`, so the exact flags (`-d -h 15 -w 300`), a successful trace, a failed
one and a missing binary are all asserted offline in `Validate`.

`Tools/test_parity.py` pushes the Python/Node comparison past the fixed conformance
cases: a seeded random corpus (plus a fixed edge list) of odd argument types, missing and
extra keys, nulls, malformed lines, credentials and non-HTTP schemes in a DoH URL, a NUL
byte in a destination and non-ASCII export payloads goes to both servers, and every
response must match. Timestamps are compared by shape (`YYYY-MM-DDTHH:MM:SS.mmmZ`)
rather than ignored: the two servers cannot share an instant, but they must share the
format. The paths that normally need a network are compared too: name
resolution is stubbed in both runtimes from one table (A, AAAA, both, neither, and
Unicode names) and DoH is served by a loopback fixture (200, 404, 503, a redirect, empty,
non-JSON, over the 64 KiB cap), with each outcome asserted rather than merely diffed.
The Unicode cases cover what the standard library lets the servers share — case and NFC
normalisation land on one punycode name, and a malformed label is refused by both — and
the two characters the standards cannot agree on: `faß.test` and `ς.test` encode
differently under Python's IDNA2003 and Node's UTS#46, so `IDN_DIVERGENT` pins each
server's exact answer, keeps them out of the strict diff, and fails if they ever stop
differing. Two structurally invalid ASCII names (`a..b`, an over-long label) are compared
too: the resolver is asked and rejects them, and both servers must report the same
`domain is not a valid hostname` result instead of CPython's `UnicodeError` or c-ares's
`EBADNAME`. It is deterministic and
offline — `trace_route` runs with an empty `PATH` and `health_score` is never generated —
and `Validate` runs it as `Diff the servers on randomized requests`.

`Tools/test_injection.py` covers the input side: a fake `traceroute` first on `PATH`
records its argv and resolver stubs record names, then flag-shaped and shell-shaped
destinations and domains are sent. Each value must be refused or arrive as one literal
argument, no payload may add an argument, and a marker file every payload aims a `touch`
at must never appear. `Validate` runs it as `Test hostile destinations and domains`.

`Tools/check-stack.py --fetch` is the pre-flight for the stacked pull requests: it
resolves each branch, refuses a pull request whose base is not the previous tip (its diff
would carry someone else's commits), allows the first base to have moved but reports how
far, and merges the five branches into a simulated `main` with `git merge-tree` to prove
none conflicts. It needs git 2.38 or newer and the branches' refs, so `Validate` runs only
its self-test (`Self-test the stack check`); run it with `--fetch` before opening or
retargeting a pull request. Once the pull requests are merged the guard reports "already
merged", and once their branches are deleted it reports that there is nothing to
rehearse; both exit 0, so it never fails as dead weight. That is the signal to retire it:
delete the guard, its self-test, the `Self-test the stack check` step and the entries
that list them.

`Tools/test_check_version.py` and `Tools/test_stamp_version.py` pin the version
tooling the same way, and the `Validate` job runs them as `Self-test the version
checks`. Both work on a temporary copy of the tree, so they never touch the checkout:
the checker must fail on a drifted site, on two sites that disagree, on a `VERSION`
that is missing or not MAJOR.MINOR.PATCH, on a newest changelog section that names
another version, and on release notes that are missing or do not name the version;
the stamper must write nothing for a bad `VERSION` or a site with the wrong number of
literals, then rewrite all twelve files for a real bump and read back consistent.

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

A job on `macos-latest` runs the checks that need no Linux tooling — the syntax checks,
the Python smoke test, conformance, the differential test and the injection test — so
the macOS support the README and installers promise is exercised instead of assumed. It
does not run a live traceroute, so the `tracepath`/BSD `traceroute` choice is still only
covered by the stubs on the other runners.

`release.yml` calls this workflow as its `checks` job and gates the publishing job on
it, so a tag whose commit fails any of the above cannot release anything.

`verify-release.yml` covers what the publishing job cannot: it runs on
`release: published` (or when dispatched for an existing tag), downloads
`mcp-installer-pack.tar.gz` and `SHA256SUMS` from the release, and runs
`Tools/check-release-assets.sh` on them — checksum, required files, a version matching
the tag, extraction and the installer handshake. A second job on a Windows runner
downloads the same two assets, checks the archive with `check-archive.py` and hands the
extracted pack to `Tools/check-installers.ps1`, so the PowerShell installers a Windows
user runs are handshaked against published bytes too. The publishing job proves the
local archive before upload; this proves the bytes GitHub serves, so a truncated,
replaced or wrongly versioned upload fails a check instead of a user. It checks out the
default branch, so a fixed verifier can be dispatched against an already published
release.

`Tools/dry-run-verify-release.sh` replays the steps after the download against a
locally built archive: it stages the committed tree the way a tag checkout would,
builds `v<VERSION>` from it into a scratch directory, runs the same
`Tools/check-release-assets.sh` the workflow runs, then removes the tree. Pass a
version to build a different one, and `--keep` to leave the built archive for
inspection. Because both call that one script, the harness cannot drift from the
workflow; what it cannot exercise is `gh release download`, the `release: published`
trigger and the Windows job's PowerShell handshake. Staging from `HEAD` also means
untracked files cannot leak into the archive, so commit an edit before dry-running it.

A `lint` job runs `actionlint` over the workflows — its image bundles `shellcheck`, so
the shell inside every `run:` block is checked, including the release steps — and
`shellcheck` 0.11.0 at its default severity over `installers/*.sh` and `Tools/*.sh`.
The job installs that version from its pinned, checksum-verified release tarball rather
than using whatever the runner image ships, so the findings only change when someone
bumps `SHELLCHECK_VERSION` and `SHELLCHECK_SHA256` together. The five scripts are
clean today, so a finding there is something you just introduced; suppress it with a
`# shellcheck disable=SCXXXX` comment and a reason only when the warning is genuinely
wrong.

Every job carries a `timeout-minutes`, so a hung download or trace fails it instead of
holding a runner until GitHub's six-hour default: 15 for `validate`, `package` and
`lint`, 20 for the macOS job and `release.yml`'s release job, and 30 for the Windows job,
which runs the live trace.

The actions in every workflow are pinned to commit SHAs, with the release they came
from in a comment. `.github/dependabot.yml` raises a weekly `github-actions` pull
request that moves the SHA and its comment together: take those, rather than editing
a pin by hand or pointing it back at a tag, so an already cut tag keeps running the
code it was tested with.

One pin is the exception: the `lint` job runs
`docker://rhysd/actionlint@sha256:…`. Dependabot's `github-actions` updater only
rewrites `owner/repo@ref` action references, and
[GitHub's supported-ecosystems page](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
says `docker://` container references are not supported, so nothing will open a pull
request for that digest and it would otherwise age silently. Bump it by hand:

1. Read the digest of the new multi-arch index, not of one architecture's image, with
   `docker buildx imagetools inspect rhysd/actionlint:<version>` (or
   `docker manifest inspect`), and copy the `sha256:` it reports for the index.
2. Replace the digest in `ci.yml` and the version in the comment above that step, so the
   two still say the same thing.
3. Run the `lint` job: it checks the shell actionlint bundles, so a digest that resolves
   to something other than the image the workflows were linted with shows up there.

## Version bumps

`VERSION` at the repository root holds the version. The installers are copied to a
user's machine as loose files and the servers are launched directly, so the twelve
literals in twelve files cannot read it at runtime; `Tools/stamp-version.py` writes it
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
