# Changelog
All notable changes to this project will be documented in this file.

The format is based on **Keep a Changelog**, and this project adheres to **Semantic Versioning 2.0.0**.

Earlier revisions of this file listed a `1.1.0` release and a `0.1.0` prototype that
described a SwiftUI application, an AppMaker generator, a `cndt` CLI and a
Cloudflare API client. None of that was implemented, released or tagged, so those
entries have been removed. The first version in this repository is `1.0.0`.

---

## [Unreleased]

### Added
- `Tools/check-runtimes.py`, run in `Validate` as `Check the runtime matrix covers the
  README minimums`, with `Tools/test_check_runtimes.py` as its self-test. It reads the
  minimums out of `README.md`'s `## Requirements` list and fails when no `validate` leg
  runs that exact Node or Python version, when a leg's version is not a quoted version
  string, or when `setup-node`/`setup-python` stop reading `${{ matrix.node }}` and
  `${{ matrix.python }}`. The matrix is the only thing that executes the floor, and a
  workflow naming any runtimes at all is valid YAML, so without this check lowering a leg
  or editing the README requirement left the promise untested with everything green
- A `Validate` matrix: the job now runs on the runtimes the project promises as well as
  the one it releases from — Node 18 with Python 3.8 next to Node 20 and Python 3.12. The floor was a
  README claim with nothing executing it. PyYAML is pinned to `6.0.3` because `6.0.4`
  requires Python 3.10 and cannot install on that leg
- `VERSION` at the repository root as the one place the version is written, plus
  `Tools/stamp-version.py`, which stamps it into all sixteen hand-maintained literals
  in twelve files, including both `package-lock.json` files npm would otherwise rewrite. `Tools/check-version.py` now fails when any site drifts from `VERSION`, so
  a bump is one edit and one command instead of sixteen edits
- `Tools/check-dependabot.py` plus a `Validate` step that parse
  `.github/dependabot.yml` and assert the parts that matter: `version: 2`, a
  `package-ecosystem`, exactly one of `directory` or `directories`, a known `schedule`
  interval, and a `github-actions` entry at `/` whenever the workflows use actions.
  Unrecognized keys are warnings, not failures, since GitHub adds keys this check will
  not know about. GitHub reads that file only from the default branch and reports
  nothing when it is wrong, so a typo would silently stop the updates. Every rule is
  pinned both ways by `Tools/test_check_dependabot.py`, which `Validate` runs as
  `Self-test the Dependabot check`: a bad `version`, a bad `directory`/`directories`
  pair, an unknown interval, a `cron` interval without a `cronjob` and a missing
  `github-actions` entry for `/` each fail, while a sound config and an unrecognized key
  (a warning, not a failure) pass
- `installers/package-lock.json` and `server/package-lock.json`. Neither package
  declares a dependency today, so each lockfile lists only the package itself; they
  are committed so the tree is pinned the moment a dependency is added, `npm ci` can
  enforce that a manifest edit carries its lockfile, and Dependabot has something to
  update
- A `lint` CI job that runs `actionlint` (pinned by the digest of the 1.7.12 image's
  multi-arch index, so the tag cannot be repointed under it) over the workflows —
  its image bundles `shellcheck`, so the shell inside every `run:` block is checked —
  and `shellcheck` 0.11.0 at its default severity over the installer and tool scripts,
  which are clean today so any finding fails the job. `shellcheck` is installed in the
  job from its pinned release tarball and checked against the asset's SHA-256, so the
  runner image cannot move it
- `Tools/check-workflows.py` plus a `Validate` step, asserting the four rules that
  fail silently on GitHub. It fails when `ci.yml`, `codeql.yml`,
  `dependency-review.yml` or `security-scan.yml` puts a `branches`/`branches-ignore`
  filter back on `pull_request` or drops the trigger (those branches are stacked, so
  the filter skips the pull requests under review while the file still parses and no
  run is created); when a job in any workflow has no `timeout-minutes`, or a value that
  is not a positive whole number, so the six-hour default cannot return unnoticed; and
  when a `uses:` is not pinned to a commit SHA or an image digest, so the pinning rule
  is enforced instead of maintained by hand; and when a `run:` block ends a line of
  code with a continuation character followed by whitespace — a backtick in pwsh, a
  backslash in bash — which ends the line instead of continuing it, so the rest of the
  command runs as its own statement: a break only the runner would report, at run time.
  Only code counts, so quoted text, comments, here-documents and here-strings are
  masked first and a literal character inside them is not reported. The rule and its
  masking are held in place by `Tools/test_check_workflows.py`, which the `Validate` job
  runs as `Self-test the workflow checks`: a here-document body and a trailing comment
  must stay quiet while a real break in either shell must still fail. The trigger,
  timeout and pin rules are pinned the same way — a filtered `pull_request`, a missing
  or non-numeric `timeout-minutes` and a tag-pinned `uses:` each fail while an
  unfiltered trigger, a positive timeout and a SHA- or digest-pinned `uses:` pass
- `Tools/test_check_version.py` and `Tools/test_stamp_version.py`, and a `Validate` step
  `Self-test the version checks` that runs both. The first pins every failure
  `check-version.py` promises — a drifted site, two sites that disagree, a `VERSION`
  that is missing or not MAJOR.MINOR.PATCH, a newest changelog section that names
  another version, and release notes that are missing or do not name the version — and
  the second pins the stamper: a clean tree changes nothing under `--dry-run`, a bump
  rewrites all twelve files and reads back consistent, a second run is a no-op, and a bad
  `VERSION` or a site with the wrong number of literals fails before anything is
  written. Both work on a temporary copy of the tree, so they never touch the checkout
- `verify-release.yml`, in two jobs — `Verify published assets` on Linux and `Verify
  published assets (Windows)` — on `release: published` or when dispatched for an
  existing tag. The Linux job downloads `mcp-installer-pack.tar.gz` and `SHA256SUMS`
  from the release and applies `Tools/check-release-assets.sh` to them — checksum,
  required files, an archive stamped with the tag's version, extraction and the
  installer handshake, the same script `Tools/dry-run-verify-release.sh` runs on a
  locally built pack. The Windows job downloads the same two assets, checks the archive
  with `check-archive.py` and hands the extracted pack to `Tools/check-installers.ps1`,
  so the PowerShell installers are handshaked against published bytes instead of only
  inside the packaging job. The publishing job only proves the local archive before
  upload; this proves the served bytes, so an upload that truncated, replaced or
  mismatched an asset fails a check instead of a user
- `Tools/check-pins.py`, which audits the one thing the offline checks cannot: it asks
  the GitHub API whether each `owner/repo[/subpath]@SHA  # vX.Y.Z` resolves to that
  commit — splitting a subpath such as `github/codeql-action/init` from the repository
  and dereferencing annotated release tags — and asks Docker Hub whether the actionlint
  digest is the image the tag serves, so a pin whose comment names the wrong release
  fails. `Tools/test_check_pins.py` pins its rules offline against fake registries and
  `Validate` runs it as `Self-test the pin check`; the audit itself needs the network and
  takes `GITHUB_TOKEN` when the unauthenticated quota is not enough
- `Tools/check-actionlint-image.py`, which closes the gap the lint job left on a machine
  without Docker: it reads the image digest `ci.yml` pins, fetches the OCI index and the
  `linux/amd64` manifest, verifies every layer's sha256, extracts the image's own
  `actionlint` and `shellcheck` binaries and runs them from the repository root, so the
  exact bytes CI lints with are exercised. `Tools/test_check_actionlint_image.py` pins
  its rules offline and `Validate` runs it as `Self-test the image check`
- `Tools/test_windows_trace_route.py`, which closes the last branch that ran only on
  Windows: it forces `trace_route` down the `tracert` path in both servers and puts a
  fake `tracert` on `PATH`, so `Validate` asserts the exact flags
  (`-d -h 15 -w 300 <destination>`), a successful trace, a failed one (`error` with the
  message) and a missing binary (`unavailable`) on every pull request
- `Tools/check-stack.py`, the pre-flight for the five stacked pull requests: it refuses a
  branch whose base is not the previous tip, allows `main` to have moved past PR 1's
  branch point but reports how far, and merges all five into a simulated `main` with
  `git merge-tree --write-tree`, so a conflict or a wrong base is found before the pull
  requests are opened instead of in review. It degrades cleanly once the stack is gone —
  every branch merged reports "already merged", deleted branches report "nothing to
  rehearse", both exit 0 — so it can be deleted with its self-test and `Validate` step
  after PR 5 merges. `Tools/test_check_stack.py` pins its rules against throwaway
  repositories and `Validate` runs it as `Self-test the stack check`
- `Tools/check-installers.py` also runs `installers/install-mcp-server.py`, so the
  Python server installer's config is handshaked like the shell, unified-shell and Node
  CLI ones instead of only being described in the docs
- `Tools/test_check_archive.py`, which builds its own packs, both ways for every rule
  the release gate asserts: a missing required file, build junk, a `VERSION` that is not
  MAJOR.MINOR.PATCH or matches neither server nor installer, a half-bumped stamp against
  `--expect-version` and a missing, wrong or unreadable `SHA256SUMS` each fail, while a
  sound pack passes and extracts. A `SHA256SUMS` with fewer than two fields, a pack with
  no `VERSION` and a missing versioned site now report a failure instead of raising, and
  `Validate` runs the test as `Self-test the archive check`
- `Tools/test_parity.py` and a `Validate` step that diff the two servers on a seeded
  random corpus plus a fixed edge list — odd argument types, missing and extra keys,
  nulls, malformed lines, credentials and non-HTTP schemes in a DoH URL, a NUL byte in a
  destination, non-ASCII exports — so drift the hand-written conformance cases never
  listed fails. Deterministic (`--seed`, `--count`) and offline: name resolution is
  stubbed in both runtimes from one table, DoH is served by a loopback fixture (200, 404,
  503, a redirect, empty, non-JSON, over the 64 KiB cap) with each outcome asserted,
  `trace_route` runs with an empty `PATH` and `health_score` is never generated. It found
  eleven server differences: ten are fixed below, and the eleventh — IDNA2003 in Python
  against UTS#46 in Node — is documented and pinned as deliberate
- `Tools/test_injection.py` and a `Validate` step that keep caller input out of the
  command line: a fake `traceroute` first on `PATH` logs its exact argv and resolver stubs
  log every name, then flag-shaped destinations (`-n`, `--help`, a trailing `-n 1`) must
  be refused while shell-shaped ones (`;`, `&&`, `|`, `$(...)`, backticks, `${IFS}`) must
  arrive as one literal argument. Every payload aims a `touch` at a marker file that must
  never appear, so a shell in either server fails the test
- `Tools/test_parity.py` sends Unicode domains: `münchen.test`, an upper-case and an
  NFD-composed form must all encode to `xn--mnchen-3ya.test`, a malformed name that needs
  conversion must be refused by both servers, and `faß.test`/`ς.test` — which Python's IDNA2003 and Node's
  UTS#46 encode differently — are pinned per server in `IDN_DIVERGENT`, kept out of the
  strict diff and failed if they ever stop differing, so the remaining gap is deliberate
  rather than silent
- a `macos` job in `ci.yml` runs the syntax checks, the Python smoke test, conformance,
  the differential test and the injection test on `macos-latest`. macOS is claimed
  support, but every other job runs on Linux or Windows, so the platform the README and
  installers promise was never executed; this job runs no live traceroute

### Changed
- `release.yml` calls the `ci.yml` workflow as a `checks` job and gates publishing on it,
  so a tag whose commit fails the smoke test, the Node/Python conformance comparison,
  lint or the packaging checks cannot create a release; the jobs are called, not copied
- `ci.yml` triggers on `main` pushes and on pull requests, so a branch push is checked
  once instead of once by `push` and again by `pull_request` for the same commit; a tag
  still runs each check once, through `release.yml`'s `checks` job. `workflow_dispatch`
  covers a branch that has no pull request yet, which the narrower `push` trigger would
  otherwise leave unchecked
- `codeql.yml`, `dependency-review.yml` and `security-scan.yml` run on every pull
  request instead of only those targeting `main`: branches here are stacked, so a pull
  request is opened against the branch below it, and the workflows used to skip it
  while it was in review
- `security-scan.yml` installs from the committed lockfile with `npm ci
  --ignore-scripts` before `npm audit`, instead of generating a throwaway lockfile per
  run, so the audit covers the tree the repository ships rather than one resolved at
  audit time, and a dependency edit without its lockfile fails the job
- `.github/dependabot.yml` also tracks `npm` for `/installers` and `/server`, weekly,
  beside the `github-actions` entry; it stays quiet until a dependency exists
- `ci.yml` cancels a superseded pull request run (a `concurrency` group per ref, with
  `cancel-in-progress` limited to pull requests so `release.yml`'s `checks` job and a
  `main` push are never interrupted), and every CI job now has a `timeout-minutes`
  instead of the six-hour default — 15 for `validate`, `package` and `lint`, and 30 for
  the Windows job, which runs the live trace; `release.yml`'s release job has one too
- `release.yml` refuses a tag that disagrees with `VERSION`, and both must be a bare
  `MAJOR.MINOR.PATCH` (a `-rc1` suffix is rejected), builds `dist/v<version>` from
  `VERSION`, runs `check-version.py` before packaging and `check-archive.py` on the
  built pack before uploading, so a release cannot publish a pack whose name and
  stamped sites disagree
- `release.yml` runs the release job on a pinned Python 3.12 (`actions/setup-python`)
  instead of the image's `python3`, so the version check, the archive builder and
  `check-archive.py` behave on tag day the way they do in CI
- Every action in every workflow is pinned to a commit SHA with its release in a
  comment — `actions/checkout` v4.4.0 (v7.0.1 in the CodeQL workflow),
  `actions/setup-node` v4.4.0, `actions/setup-python` v5.6.0,
  `actions/upload-artifact` v4.6.2, `actions/download-artifact` v4.3.0,
  `actions/dependency-review-action` v4.9.0, `github/codeql-action` v4.39.5 and
  `softprops/action-gh-release` v2.6.2 — and a new `.github/dependabot.yml` opens a
  weekly `github-actions` PR that moves the SHA and the comment together, so a
  re-tagged action cannot change what an already cut tag runs
- The release archive ships `VERSION`, and `Tools/check-archive.py` fails when it
  disagrees with the version in the packaged server and unified installer, so an
  archive cannot be published under a stale version

### Fixed
- `dns_check` now converts a Unicode domain on both servers instead of leaving it to the
  resolver. Node's `dns` module rejected the raw UTF-8 label (`münchen.test not found`)
  while Python's `getaddrinfo` encoded and resolved it, so one server returned addresses
  and the other an error for the same domain. Both lowercase and NFC-normalise first, so
  case and composition no longer matter, and both refuse a name that is not a valid
  hostname with the same `domain is not a valid hostname` result and the name as typed,
  while a plain ASCII name is still left to the resolver as before; `faß.test` and `ς.test`
  still encode differently by standard, and both are documented and pinned rather than
  quietly disagreeing. An invalid ASCII name no longer surfaces as a `-32602` protocol
  error from CPython's `UnicodeError` on one server and a c-ares `EBADNAME` tool error on
  the other: both report `domain is not a valid hostname`, and the parity corpus covers
  `a..b` and an over-long label
- `release.yml` no longer appends the repository's whole history to a first tag's
  release body: with no earlier tag the curated notes stand alone and a notice is
  logged, and otherwise only the commits since that tag are listed
- `Tools/check-links.py` checks the Markdown files git tracks, so ignored build output
  and untracked scratch trees no longer fail the link check or change its count
- The release documentation no longer claims that no tag exists: the v1.0.1 notes, the
  v1.0.0 notes header, the 1.0.0 entry below and the release checklist record that
  v1.0.0 was never tagged, so publishing v1.0.1 cannot make them false
- Differences between the two servers that the fixed conformance cases missed, found by
  `Tools/test_parity.py`: the Python `export_results` escaped non-ASCII characters in
  JSON output where Node wrote them raw; Python rejected `results: null` while Node
  treated it as `{}`; Node treated `arguments: null` as omitted where Python rejected it;
  a NUL byte in `destination` reached `subprocess` in Python and failed with "embedded
  null byte" instead of the validation message; a non-string or missing tool name was
  reported as `'None'` by Python and `'null'`/`'undefined'` by Node; and the two servers
  chose different messages for a DoH URL whose scheme was missing, non-HTTP or carried
  credentials
- Results that only differ against a live network, found once the parity test stubbed the
  resolver and served DoH locally: Python raised on a 4xx/5xx DoH response and lost its
  status and body instead of returning them as a tool result; Python kept an unbounded
  non-JSON body where Node caps it at 4096 characters; Node listed resolved addresses in
  resolution order where Python sorts them; and Node repeated a failed lookup's message
  once per address family where Python reports it once. The parity corpus now checks every
  `dns_check` list against a sorted, de-duplicated copy of itself, not only the pinned
  dual-stack case
- A `traceroute`/`tracepath` that exists but cannot execute (wrong format, permissions)
  no longer kills the Python server: it returns a failed trace, the way Node does, instead
  of raising out of the request loop

### Changed
- `initialize` negotiates the protocol version instead of answering `2024-11-05`
  regardless of what the client asked for. Both servers echo `2024-11-05` when it is
  requested and answer `2024-11-05` for any other value — a newer or older MCP version,
  or one that is not a string — so a client is never told a version the server does not
  speak. `Tools/test_parity.py` pins the supported, newer, older and malformed cases on
  both servers; with a single supported version the echoed and the fallback answers are
  the same string, so the unsupported rows are what catch a version being echoed that
  the server does not speak

### Fixed
- The Python server's `export_results` CSV depended on the runtime: `csv.writer` quotes a
  bare carriage return on 3.10+ and leaves it bare on 3.8, where Node always quotes it, so
  the same result object produced two different documents. Cells are now quoted by the
  Node server's rule on every version. Found by running the checks on 3.8
- `Tools/check-archive.py` used `str.removeprefix` (3.9+) and
  `Tools/check-actionlint-image.py` annotated with `dict[...]` and `str | None` (3.9+/3.10+),
  so the archive and image self-tests failed on the Python 3.8 floor. The first is sliced
  and the second takes its annotations from `__future__`
- The two servers stamped results differently — `…Z` in Node, `…+00:00` with
  variable-length microseconds in Python — so the parity and conformance comparisons had
  to drop `timestamp` before diffing. Both now emit `YYYY-MM-DDTHH:MM:SS.mmmZ`, and
  `Tools/check-conformance.py` / `Tools/test_parity.py` assert that shape instead of
  ignoring the field, so a server that changes format fails the comparison
- `doh_test` echoed different URLs: Node returned `url.toString()`, which adds the path
  slash and normalises the host, where Python returned the string supplied. Both echo the
  request verbatim now, and `Tools/test_parity.py` compares each echo with the URL it
  sent, including a fixture endpoint addressed without a path

## [1.0.1] - 2026-11-25

Patch release: the two servers now answer identically for the two remaining
differences that were bugs rather than design, and the version strings finally match
a released version. See [release/v1.0.1/release-notes.md](release/v1.0.1/release-notes.md).

### Added
- `Tools/check-links.py` plus a CI step that fails the build on broken relative
  links and unsupported schemes (such as `ca://`) in the documentation
- `Tools/check-conformance.py`, which sends the same requests to both servers and
  fails on any difference, plus a `--live-trace` mode the Windows CI job uses to run
  a real `trace_route` through the `tracert` path; its DoH cases are served by a
  loopback fixture at 64 KiB and 64 KiB + 1 byte, so the shared cap is asserted
  without contacting a DoH provider, and a CSV case covers CR, CRLF and quoting
- `Tools/check-version.py`, which fails when any hand-maintained version string, the
  changelog's newest release section and `release/v<version>/release-notes.md`
  disagree, so a bump cannot land in only some of them
- `Tools/check-archive.py`, the only place the archive's file list is written down:
it checks the contents, verifies `SHA256SUMS` and extracts, on either platform
- `--installers-root` / `-InstallersRoot` on the installer checks, so the packaged
copy of an extracted archive can be installed and handshaked; their session now also
asserts the protocol version, the five tool names and `ping`
- A CI packaging job, plus a Windows job that downloads the same archive the Linux
job built, so the Windows installers are exercised on every push against identical
bytes
- Windows CI job that parses `installers/*.ps1` and runs `Tools/check-installers.ps1`

### Changed
- Version strings now report `1.0.1` in both servers (`initialize`), both
  `package.json` files, `installers/cli.js`, `installers/install-mcp-server.py` and
  the client configs written by the shell and PowerShell installers, so an installed
  config and a running server agree with the release they came from
- `ci.yml` replaced the checkout-only workflow with syntax, smoke test, JSON,
  documentation-link and installer checks on Linux
- The release archive now ships `LICENSE` and `README.md` alongside `installers/`,
  `server/` and `docs/`
- `Tools/build-package.sh` builds the archive for both `release.yml` and CI, so the
  two cannot drift apart
- Documentation rewritten to match the shipped code: `README.md`,
  `docs/Architecture.md`, `docs/Modules.md`, `docs/Export.md`, `docs/Privacy.md`,
  `docs/AppMaker.md` (now a status page), `docs/TROUBLESHOOTING.md`,
  `docs/ROADMAP.md`, `ROADMAP.md`, `PERFORMANCE-GUIDE.md`, `SECURITY.md` and
  `CONTRIBUTING.md`

### Fixed
- `doh_test` applies the same 64 KiB response cap in both servers: a larger body now
  returns a normal result with `status: "error"`, the HTTP `statusCode` and
  `DoH response exceeded 64 KiB limit` instead of Python's `-32602` and Node reading
  the whole body; Node stops reading at the cap, so neither server buffers a larger
  response
- `export_results` CSV quotes a cell containing a carriage return in Node as well as
  Python, so both servers quote it the same way instead of Node writing a bare CR
  that split the row for any reader that treats CR as a line ending
- `trace_route` works on Windows: both servers run `tracert -d -h 15 -w 300` there
  instead of looking only for `traceroute`/`tracepath`, which Windows does not ship,
  so the tool no longer always returns `unavailable`; destinations starting with `-`
  are rejected in both servers
- Generated MCP configs now use the installed script's absolute path; clients no
  longer receive a relative `index.py` that resolves against their own working
  directory
- Unused `axios` dependency removed, so the unified installers write a
  `{"type": "module"}` manifest instead of running `npm install`
- `installers/package.json` no longer points `main`, `start` and `dev` at an
  `index.js` that does not exist; it points at `cli.js` and declares no
  dependencies (unused `express`, `dotenv` and `eslint` removed)
- CodeQL no longer analyses Swift, which the repository does not contain, so the
  analysis job runs on Linux only
- The bug report template asks for OS, runtime and MCP client instead of Windows and
  PowerShell only
- Deleted the shadowed lowercase `issue_template/bug_report.md` duplicate, which
  asked for a Swift version and a v1.1.0 release that never existed
- The release workflow uploaded from `dist/vvX.Y.Z` while the build wrote
  `dist/vX.Y.Z`; the upload paths now match the archive that is built
- `docs/PERFORMANCE-OPTIMIZATION.md` was a Swift/NSCache/Instruments guide; it now
  documents the servers' real timeouts, payload bounds and measurement method
- Broken relative links in `docs/README.md` and `release/v1.0.0/release-notes.md`,
  and leftover `ca://` links in `docs/Architecture.md` and `docs/ROADMAP.md`

### Removed
- `docs/Troubleshooting.md`, a mislabeled Swift performance guide whose name
  collided with `docs/TROUBLESHOOTING.md` on case-insensitive filesystems
- `server/mcp-server.json` and `server/mcp-client.json`, the static config templates
  that carried the relative path
- `installers/ish-gh-installer.sh`, an unrelated Alpine script that built the GitHub
  CLI from source and had no connection to this project
- `.devcontainer/`, a corrupted directory holding a stray feature file and no
  `devcontainer.json`
- `reference/`, five optimisation write-ups for the SwiftUI app that never existed
  (four Swift files and a `.cflog` logging design the servers do not use)
- `.setup-github-agent.ps1`, a scaffold that regenerated the Copilot instructions,
  issue templates, `CONTRIBUTING.md` and `ci.yml` with Windows-first content
- `Tools/icon-resizer.sh` (iOS/macOS icon sizes; the repository has no icons) and
  `Tools/cleanup-logs.sh` (a generic `*.log` vacuum; nothing here writes `*.log`)

---

## [1.0.0] - 2026-06-19

First version committed to this repository (v1.0.0 was never tagged).

### Added
- Node.js MCP stdio server (`server/index.js`), ES module, no runtime dependencies
- Python MCP stdio server (`server/index.py`), standard library only
- Five diagnostic tools on both servers: `dns_check`, `doh_test`, `trace_route`,
  `health_score`, `export_results`
- Installers for macOS/Linux (`install-mcp-server.sh`, `install-mcp-unified.sh`),
  Windows (`install-mcp-server.ps1`, `install-mcp-unified.ps1`), Python
  (`install-mcp-server.py`) and the `installers/cli.js` Node CLI
- Client configuration (`mcp-server.json`, `mcp-client.json`) written by the
  installers into user-scoped directories
- Protocol smoke test (`server/smoke_test.py`) and JSON validation utility
- Documentation set: architecture, tools, export, privacy, troubleshooting, security
  and release notes
