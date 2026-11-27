# Stacked PRs — paste-ready descriptions

All five branches are pushed, and each row describes the tip it names. PR 1 carries one
commit that makes CodeQL and the npm audit run on every pull request: the five branches
are stacked, so the old `branches: [ main ]` filter skipped four of these pull requests
while they were in review. Each branch above it then merges the updated branch below, so
the same change is in every tip and in every pull request's merge ref without appearing
again in the diff of PRs 2–5. Those merges are why the later rows count one merge commit
more than before. PR 5's own commits are the release and lint work: the PR bodies in
this file, the `CONTRIBUTING.md` tag-suffix fix, the release job's Python pin, the action
SHA pins with Dependabot, the `ci.yml` pins and the three security workflows, the CI
trigger/concurrency/timeout fix, the Dependabot check, the workflow-trigger check, the
committed npm lockfiles, three more ignore entries and the docs that describe the
broadened triggers. PR 5's row
names the merge below the commit that writes this file, and its counts are taken at the
branch tip one commit later, so they describe what the pull request shows.

| PR | Head branch | Tip | Base branch | Commits | Files | Lines |
| -- | ----------- | --- | ----------- | ------- | ----- | ----- |
| 1 | `pr/installer-ci` | `5be12ea` | `main` | 2 | 12 | +341 −149 |
| 2 | `fix/windows-trace-route-v2` | `df345b3` | `pr/installer-ci` | 8 (7 own + 1 merge) | 4 | +357 −25 |
| 3 | `ci/packaging` | `d2f9a4b` | `fix/windows-trace-route-v2` | 10 (3 own + 7 merges) | 20 | +455 −1890 |
| 4 | `docs/rewrite` | `113e3d5` | `ci/packaging` | 11 (7 own + 4 merges) | 23 | +1265 −1647 |
| 5 | `fix/doh-cap-csv-cr` | `6792f34` | `docs/rewrite` | 40 (39 own + 1 merge) | 41 | +1870 −120 |

Open them in order with **Create a merge commit** (no squash, no rebase), and after
each one lands retarget the next PR's base to `main` (GitHub does this itself when
the merge target is the branch you merged into). Measured at the tip: merging the
five in order reproduces the branch tree exactly, while squashing them onto `main`
in order conflicts at PR 2 in `.github/workflows/ci.yml` (PR 1 alone applies
cleanly).

PR 5 is the only branch that contains any of the version/release tooling, so `VERSION`
does not exist until PR 5 lands.

Every claim below was checked against the branch's own diff, not against the
earlier description. Where a later PR supersedes something in an earlier one, the
earlier body says so rather than describing the final state.

---

## PR 1

**Title**

```
Fix the MCP installer configs, and validate and scan every pull request
```

**Head:** `pr/installer-ci` → **Base:** `main`

https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/pull/new/pr/installer-ci

**Body**

<!-- BODY 1 START -->
## Summary

The installers copied static `server/mcp-server.json` / `server/mcp-client.json`
templates into place, and those templates named a relative `index.py`. MCP clients
resolve a relative `args[0]` against their own working directory, not against the
config file, so the installed server never launched. The unified installers also
ran `npm install` for a server that is an ES module with no runtime dependencies.
The configs are now generated with the installed script's absolute path, and a
checker runs the installers and handshakes with the server they produce. The
security workflows change too: CodeQL and the npm audit now run on every pull
request, not only the ones opened against `main`, because the five branches here
are stacked and each pull request targets the branch below it.

## Changes

- `installers/install-mcp-server.sh`, `installers/install-mcp-unified.sh`: write
  `mcp-server.json` and `mcp-client.json` from `command -v python3` and the
  installed script's absolute path instead of copying the templates.
  `install-mcp-unified.sh` also drops the `npm install` step and writes a
  `{"type": "module"}` manifest for the copied Node server.
- `installers/install-mcp-unified.ps1`: the same, and it no longer requires
  `npm`/`npm.cmd` to be installed.
- Delete `server/mcp-client.json` and `server/mcp-server.json` (the relative-path
  templates), and drop the unused `axios` dependency from `server/package.json`
  and `installers/package.json`.
- `Tools/check-installers.py`: runs each installer with `HOME` pointed at a
  temporary directory, then for both written configs asserts `command` is
  executable, `args[0]` is absolute and exists, launches `<command> <args[0]>`,
  and requires an `initialize` response. It also runs `installers/cli.js install`
  when Node is available.
- `Tools/check-installers.ps1`: the same for `install-mcp-unified.ps1` and
  `install-mcp-server.ps1`, installed into a temporary `-InstallDir`, including
  the `initialize` handshake.
- `.github/workflows/ci.yml`: the `Validate` job runs the Python checker (alongside
  `node --check`, `compileall`, `bash -n`, the smoke test and JSON validation) and
  gets Node 20 and Python 3.12 explicitly. A new `windows` job parses every
  `installers/*.ps1` with the PowerShell parser and runs the `.ps1` checker.
- `.github/workflows/codeql.yml`, `.github/workflows/security-scan.yml`: `pull_request`
  now runs for every pull request instead of only those targeting `main` (the security
  scan also listed `master` and `develop`). The branches here are stacked, so a pull
  request is normally opened against the branch below it, and the old filter skipped
  both workflows for it. The `push` filters are unchanged, so a branch is still scanned
  once when it lands.

## Notes

- No change for anyone who already installed by hand: a fresh run writes the
  corrected config, an existing one is left alone.
- The handshake here is `initialize` only. PR 3 turns it into a full session
  (protocol version, `tools/list`, `ping`) and adds `--installers-root` /
  `-InstallersRoot` so an extracted release archive can be checked instead.
<!-- BODY 1 END -->

---

## PR 2

**Title**

```
Run tracert on Windows and check that both servers agree
```

**Head:** `fix/windows-trace-route-v2` → **Base:** `pr/installer-ci`

https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/pull/new/fix/windows-trace-route-v2

**Body**

<!-- BODY 2 START -->
## Summary

`trace_route` looked only for `traceroute` and `tracepath`, neither of which
Windows ships, so it returned `status: "unavailable"` there. While adding
`tracert`, the two servers turned out to have drifted in argument validation and
in the CSV export, with nothing checking that they agree. This fixes the Windows
path, brings the servers back in line, and adds a conformance check that fails on
any remaining difference.

## Changes

- Both servers: a platform-specific candidate list. On Windows that is
  `tracert -d -h 15 -w 300`; elsewhere `traceroute`, then `tracepath`. A
  destination starting with `-` is rejected so it cannot be read as an option,
  and the "no trace tool" message now names all three.
- `server/index.py`: an unparsable DoH URL (`urlsplit` raising) is reported as the
  same validation error as the other malformed URLs; trace output is decoded with
  `errors="replace"`; the CSV writer uses `\n` and exports strings verbatim and
  every other value as compact JSON.
- `server/index.js`: the same CSV dialect (strings verbatim, other values as
  compact JSON, quoting only when needed), `tools/call` rejects arguments the
  input schema does not declare, and `params: undefined` is treated as `{}`.
  Tool descriptions are declared in the input schemas.
- `Tools/check-conformance.py`: feeds the same 24 requests plus a malformed line
  to both servers and fails on any difference other than timestamps (the JSON
  payload inside a `content` text entry is compared instead of its whitespace).
  `PATH` is emptied so `trace_route` reports no tool rather than probing the
  network. `health_score`'s probe to `1.1.1.1:443` is stubbed in both runtimes
  (`sitecustomize` for Python, `--require` for Node), the two calls must return
  95/`healthy` then 64/`degraded`, and the stub's stderr markers are counted so a
  changed probe target fails instead of silently using the network.
- `Tools/check-conformance.py --live-trace DEST`: one real trace per server, which
  must report `status: "ok"` with no non-zero return code, non-empty output, and
  output mentioning the destination. It does not match the trace's wording.
- `.github/workflows/ci.yml`: `Compare the Python and Node servers` in `Validate`,
  and `python Tools/check-conformance.py --live-trace 127.0.0.1` in `windows`.

## Notes

- The check is a comparison: a difference fails, so it cannot catch something both
  servers get wrong. The only absolute expectations are the two `health_score`
  outcomes and the probe-stub marker count.
- `windows-latest` is the only place `tracert` is actually run; that is what the
  new live-trace step is for.
- The branch merges the updated branch below it, which broadens the `pull_request`
  filters in `codeql.yml` and `security-scan.yml`. That change is already in the base,
  so it adds no files or lines to this diff; it is what makes CodeQL and the npm audit
  run while this pull request is open.
<!-- BODY 2 END -->

---

## PR 3

**Title**

```
Add packaging and release checks, and drop the app-era files
```

**Head:** `ci/packaging` → **Base:** `fix/windows-trace-route-v2`

https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/pull/new/ci/packaging

**Body**

<!-- BODY 3 START -->
## Summary

`release.yml` built the release tarball with an inline `tar` command that no CI job
ever ran, so packaging could only break at tag time, and the repository still
carried Swift/Python reference dumps, `.setup-github-agent.ps1` and helper scripts
that nothing referenced. This moves the archive build into one script, adds a CI
job that builds, checks, extracts and installs from it on Linux and Windows, and
deletes the dead weight.

## Changes

- `Tools/build-package.sh`: the single archive builder, used by `ci.yml` and
  `release.yml`. Takes `<version> [output-root]`, refuses to build when an entry is
  missing, packs `installers/ server/ docs/ LICENSE README.md` into
  `dist/v<version>/mcp-installer-pack.tar.gz`, and writes `SHA256SUMS` with
  `sha256sum` or `shasum`.
- `Tools/check-archive.py`: the one place the archive's file list is written down.
  It asserts a required-entry list, rejects build junk (`__pycache__/`,
  `node_modules/`, `.git/`, `.DS_Store`), and optionally extracts
  (`--extract-to`) and verifies the sibling `SHA256SUMS` (`--expect-checksum`).
- `Tools/check-installers.py` / `.ps1`: `--installers-root` / `-InstallersRoot` to
  check a tree other than the working copy, and the handshake grows into a session
  that asserts protocol `2024-11-05`, all five tool names from `tools/list`, and
  `ping`.
- `.github/workflows/ci.yml`: a new `package` job builds `v0.0.0-ci`, checks and
  extracts it, installs the servers from the extracted copy, and uploads the
  archive. The `windows` job now needs it, downloads the same artifact rather than
  rebuilding, checks the checksum, and runs the packaged PowerShell installers.
- `.github/workflows/release.yml`: build via `Tools/build-package.sh` instead of
  duplicating the `tar` invocation, and publish the curated
  `release/v<tag>/release-notes.md` as the release body ahead of the generated
  commit list.
- Add `.gitignore` (`__pycache__/`, `*.pyc`, `dist/`); `codeql.yml` drops the Swift
  language so the analysis runs on Linux only; `installers/package.json` points
  `main` at `cli.js`, declares `private`, and drops the `express`, `dotenv` and
  `eslint` dependencies plus the scripts that pointed at a nonexistent `index.js`.
- Delete `reference/` (four Swift optimisation write-ups and one Python logging
  design), `.setup-github-agent.ps1`, `Tools/cleanup-logs.sh`,
  `Tools/icon-resizer.sh`, `installers/ish-gh-installer.sh`, and the corrupted
  `.devcontainer/` directory (a single stray quoted-path file, no
  `devcontainer.json`).

## Notes

- The Windows job tests the Linux-built archive on purpose: one build, two
  platforms, so a platform difference in the archive shows up as a failure.
- The release body still appends `## Commits` for every release at this point;
  PR 5 makes that conditional on an earlier tag.
- The branch merges the updated branch below it, which broadens the `pull_request`
  filters in `codeql.yml` and `security-scan.yml`. That change is already in the base,
  so it adds no files or lines to this diff; it is what makes CodeQL and the npm audit
  run while this pull request is open.
<!-- BODY 3 END -->

---

## PR 4

**Title**

```
Rewrite the docs around the servers that actually ship
```

**Head:** `docs/rewrite` → **Base:** `ci/packaging`

https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/pull/new/docs/rewrite

**Body**

<!-- BODY 4 START -->
## Summary

The documentation still described a macOS app that is not in this repository:
Swift modules, an export pipeline, a logging layer, an app-side performance tuning
guide. It also claimed things the two MCP servers do not do (write log files, offer
a GUI, ship an install wizard). This rewrites the docs around the servers and
installers that are in the tree, labels unbuilt work as planned, and adds a link
check so the next rewrite cannot rot.

## Changes

- `README.md`, `docs/README.md`, `docs/Architecture.md`, `docs/Modules.md`,
  `docs/TROUBLESHOOTING.md`, `docs/Privacy.md`, `docs/Export.md`,
  `docs/AppMaker.md` (now a status page), `docs/PERFORMANCE-OPTIMIZATION.md`,
  `docs/ROADMAP.md`, `ROADMAP.md`, `PERFORMANCE-GUIDE.md`, `SECURITY.md`,
  `IMPLEMENTATION-CHECKLIST.md`, `.github/copilot-instructions.md`: describe the
  five MCP tools, the two server implementations, the installers and the CI jobs
  that exist.
- `CHANGELOG.md`: drops the `1.1.0` and `0.1.0` entries for the SwiftUI app,
  AppMaker generator, `cndt` CLI and Cloudflare API client that were never built,
  and records the install, Windows `trace_route`, conformance and packaging
  changes from PRs 1–3 under `## [Unreleased]`.
- `release/v1.0.0/release-notes.md`: corrected against the tree, including the
  broken relative links.
- `.github/ISSUE_TEMPLATE/bug_report.md`: asks for OS, runtime and MCP client
  instead of Windows and PowerShell only.
- Delete `docs/Troubleshooting.md` — a copy of the Swift performance guide saved
  under the wrong name, whose filename collided with `docs/TROUBLESHOOTING.md` on
  case-insensitive filesystems — and `.github/issue_template/bug_report.md`, an
  older Windows/PowerShell-only form sitting in `issue_template/` (lowercase,
  singular), which GitHub does not read.
- `Tools/check-links.py`: walks the repository's `*.md` files, ignores fenced code
  blocks, does not fetch `http://`, `https://` or `mailto:` targets, skips pure
  `#anchor` links, and fails when a relative target does not exist or uses an
  unsupported scheme. New `Check documentation links` step in the `Validate` job.

## Notes

- Anchors are not validated: only the file part of a relative link is resolved.
- The checker walks the working tree at this point; PR 5 restricts it to
  git-tracked files (with the walk kept as a fallback outside a checkout).
- No server changes. The workflow changes are the added link step and the broadened
  `pull_request` filters in `codeql.yml` and `security-scan.yml`, which arrive with the
  merge of the updated branch below and are already in the base, so they add nothing to
  this diff.
<!-- BODY 4 END -->

---

## PR 5

**Title**

```
Release 1.0.1: version stamping, release guards, and lint
```

**Head:** `fix/doh-cap-csv-cr` → **Base:** `docs/rewrite`

https://github.com/hyrated117/Cloudflare-Network-Diagnostic-Tool-v1.0/pull/new/fix/doh-cap-csv-cr

**Body**

<!-- BODY 5 START -->
## Summary

Two server gaps first — the Node server buffered a DoH response with no limit, and
its CSV export did not quote a carriage return — then the release plumbing they
exposed: the version was written by hand in a dozen places, a tag could publish a
commit that failed CI, and no job linted the workflows or the shell scripts.
`VERSION` is now the single source, `Tools/check-version.py` proves every stamped
site agrees with it, and `release.yml` calls `ci.yml` before it publishes.

## Fixes

- `server/index.js`: read the DoH body as a stream and stop at 64 KiB instead of
  `await response.text()`, so a remote endpoint cannot make the process buffer an
  unbounded body. Over the cap is a tool result with `status: "error"`, like a
  timeout.
- `server/index.py`: it already read at most 64 KiB + 1, but raised `ValueError`,
  which surfaced as a `-32602` protocol error. It now returns the same error tool
  result as Node.
- `server/index.js`: the CSV export quotes fields containing `\r` as well as `"`
  and `\n`; a trailing carriage return used to escape the quoting and split the
  row.
- `Tools/check-conformance.py`: a CSV case with `\r`, `\r\n`, a comma and an
  embedded quote, plus a loopback HTTP fixture that serves a body of exactly
  64 KiB and one of 64 KiB + 1. The at-cap body must be accepted and parsed, the
  over-cap body must come back as an error tool result marked `isError`, and the
  docstring no longer claims some requests reach the network.

## Version single-sourcing

- `VERSION` — the one place the release number is written.
- `Tools/version_sites.py` — the list of the eight files that carry a version
  literal (with the pattern that matches each) and the two `package.json` files:
  twelve literals in ten files.
- `Tools/stamp-version.py` — rewrite every site from `VERSION`; `--dry-run` lists
  what would change.
- `Tools/check-version.py` — the authoritative check. It fails when a site drifts
  from `VERSION`, when the sites disagree with each other, when `CHANGELOG.md` has
  no `## [Unreleased]` or its newest dated section names a different version, or
  when `release/v<newest>/release-notes.md` is missing or its title does not name
  that version. New `Check version consistency` step in the `Validate` job.
- `release/v1.0.1/release-notes.md` — the curated 1.0.1 notes. The two servers,
  the installers, `installers/cli.js` and both `package.json` files are stamped
  `1.0.1`.

## Release workflow guards

- Tag and `VERSION` must agree (`vMAJOR.MINOR.PATCH`, no suffix), and
  `check-version.py` must pass, before anything is built.
- `Tools/check-archive.py --expect-checksum` runs on the built archive before the
  upload step.
- The release job runs on a pinned Python 3.12 (`actions/setup-python`) instead of
  the runner image's `python3`, the way `ci.yml` pins Node and Python and the lint job
  pins actionlint and shellcheck, so tag day does not depend on the image.
- Every action in every workflow is pinned to a commit SHA with its release in a
  comment (`actions/checkout` v4.4.0, and v7.0.1 in the CodeQL workflow,
  `actions/setup-node` v4.4.0, `actions/setup-python` v5.6.0,
  `actions/upload-artifact` v4.6.2, `actions/download-artifact` v4.3.0,
  `actions/dependency-review-action` v4.9.0, `github/codeql-action` v4.39.5,
  `softprops/action-gh-release` v2.6.2), so a re-tagged or moved action cannot change
  what runs. A new `.github/dependabot.yml` opens a weekly `github-actions` PR that
  moves the SHA and the comment together.
- The release body is the curated notes. `## Commits` is appended only when an
  earlier tag exists, so 1.0.1 does not list the entire history; with no earlier
  tag the body is just the notes and the step logs a `::notice::` saying so.
- `release.yml` now gates publishing on CI: `ci.yml` gains `workflow_call:`, and
  `release.yml` runs it as a `checks` job with `release: needs: checks`. Validate,
  package, lint and the Windows job all have to pass before a tag can publish.
  `ci.yml` triggers on `main` pushes and pull requests rather than every branch push,
  so a branch commit is checked once instead of once by `push` and again by
  `pull_request`, and a tag still runs each check once through the `checks` job.
  `workflow_dispatch` keeps a branch without a pull request checkable by hand.
- `ci.yml` cancels a superseded pull request run via a `concurrency` group per ref
  (`cancel-in-progress` only for pull requests, so a release's `checks` job and a
  `main` push always finish), and every job has a `timeout-minutes` — 15, 30 for the
  Windows job with the live trace — so a hung download or trace fails the job instead
  of holding a runner for six hours. The release job has one too.
- `Tools/check-links.py` now checks git-tracked files only (falling back to a
  directory walk when git is unavailable), so ignored build output and untracked
  scratch files cannot fail a release.

## Dependency lockfiles

- `installers/package-lock.json` and `server/package-lock.json` are committed. Neither
  package declares a dependency today — `README.md` already says no `npm install` is
  needed — so each lockfile lists only the package itself. They are here so the tree is
  pinned the moment a dependency is added, not to change what installs now.
- `security-scan.yml` runs `npm ci --ignore-scripts` before `npm audit`, so the audit
  covers the committed tree instead of a lockfile generated per run, and a dependency
  edit that forgets its lockfile fails the job rather than being audited anyway.
- `.github/dependabot.yml` gains a weekly `npm` entry for `/installers` and `/server`
  beside the `github-actions` entry; it stays quiet until a dependency exists.

## Dependabot check

- `Tools/check-dependabot.py` parses `.github/dependabot.yml` and asserts only what
  Dependabot needs: `version: 2`, a `package-ecosystem`, exactly one of `directory` or
  `directories`, a known `schedule` interval (plus `cronjob` when it is `cron`), and a
  `github-actions` entry at `/` while the workflows use actions. Unrecognized keys are
  warnings, not failures, so a new GitHub key cannot fail a sound config. The
  `Validate` job installs PyYAML 6.0.4 for it, pinned like everything else; the other
  tools stay stdlib-only. GitHub reads the   file only from the default branch and
  reports nothing when it is malformed, so without this a typo would silently stop the
  action updates.

## Workflow trigger check

- `Tools/check-workflow-triggers.py` fails when `ci.yml`, `codeql.yml`,
  `dependency-review.yml` or `security-scan.yml` puts a `branches` or
  `branches-ignore` filter back on `pull_request`, or drops the `pull_request`
  trigger. The regression is otherwise silent: the file still parses and GitHub simply
  never creates the run, and a stacked pull request is exactly the one a
  `branches: [ main ]` filter skips. It was checked both ways: green on this tree and
  red with `branches: [ "main" ]` restored in a probe copy. The `Validate` job runs it
  with the pinned PyYAML.
- `dependency-review.yml` had the same `main` filter as the two security workflows, so
  it now runs on every pull request as well; on this branch it is what gives a pull
  request that adds a dependency a review where it is opened.

## Ignored files

- `.gitignore` also covers `node_modules/`, `.venv/` and `.DS_Store`, so a local
  `npm install` or virtualenv and macOS metadata cannot end up in a commit.

## Lint

- New `Lint workflows and shell` job in `ci.yml`: actionlint pinned to the
  `docker://rhysd/actionlint:1.7.12` image (it bundles shellcheck, so the shell
  inside every `run:` block is checked too), then shellcheck 0.11.0 installed from
  its pinned release tarball with a SHA-256 check, run at default severity over
  `installers/*.sh` and `Tools/*.sh` — three scripts today.

## Docs

- `CONTRIBUTING.md`: the checks list including the release gate, the lint job and
  how to suppress a shellcheck finding (a `# shellcheck disable=SCXXXX` comment
  plus a reason), and the version bump flow. Its tag step no longer implies a
  `-rc1` tag is accepted: the workflow and `VERSION` both require a bare
  `MAJOR.MINOR.PATCH`. It also records that the release actions are SHA-pinned and
  that Dependabot's weekly PR is how a pin moves.
- `CHANGELOG.md`, `release/v1.0.1/release-notes.md`,
  `IMPLEMENTATION-CHECKLIST.md`, `release/v1.0.0/release-notes.md` and
  `.github/copilot-instructions.md` reflect the above, and the time-bound "no tag
  exists yet" wording is replaced with what actually happened.

## Notes

- `v1.0.0` was never tagged in this repository; the 1.0.0 notes are kept as
  history. 1.0.1 would be the first tag this workflow can publish.
- The upload step (`softprops/action-gh-release`) has not been executed — no tag
  was pushed. Everything up to it was run in a dry run.
- The `codeql.yml` / `security-scan.yml` trigger broadening lands in PR 1, and this
  branch merges the updated branch below, so every pull request in the stack gets
  CodeQL and the npm audit while it is open without the change appearing twice.
- `PR-DESCRIPTIONS.md` at the repository root carries the bodies for these five
  PRs, so they survive outside the PR descriptions themselves.
<!-- BODY 5 END -->

---

## What was checked

Each body's claims were re-verified against the branch's own diff before this file
was written. Corrections made in this pass:

- PR 1: `--installers-root` does not exist yet (added in PR 3) and is now described
  as such; the checker asserts an `initialize` handshake, not just JSON parsing;
  the `package.json` change removed `axios`, not "install entries"; the
  directory-creation claim was already true before this PR and is gone.
- PR 2: `--live-trace` does not match "hop structure" — it asserts status, return
  code, non-empty output and that the destination appears in it. The argument
  injection guard and the cross-server parity fixes were missing and are added.
- PR 3: `check-archive.py` asserts a required list and rejects junk markers; it does
  not "refuse unexpected paths". The `check-installers` session upgrade, the
  `.gitignore`, the CodeQL/Swift removal and the `installers/package.json` cleanup
  were missing.
- PR 4: neither deleted file was a duplicate. `docs/Troubleshooting.md` was a copy
  of the Swift performance guide under the wrong name, and the two bug-report
  templates differ. `check-links.py` does not validate anchors and walked the
  working tree here; the `git ls-files` change belongs to PR 5.
- PR 5: the Python server already capped DoH at 64 KiB — this PR changes its
  over-cap behaviour from a protocol error to a tool result; the CI step is named
  `Check version consistency`; the loopback DoH fixture and the CR CSV case are now
  described. The `CONTRIBUTING.md` sentence that implied pre-release tags work is
  corrected on this branch, since `release.yml` rejects any suffix.

Re-checked at the tips named above: PRs 1–4 keep every commit they were reviewed at, and
each adds only the trigger change (PR 1, as a commit) or the merge of the updated branch
below (PRs 2–4), so no other reviewed content moved. Each body's claims were spot-checked
again — the Windows `tracert -d -h 15 -w 300` candidate list and the leading-`-`
rejection in both servers, the 24-request conformance set with its probe stubs and
`--live-trace`, `--installers-root` / `-InstallersRoot` and the `2024-11-05` session, the
CodeQL matrix without Swift, the deleted `reference/` files and bug-report template, and
`check-links.py` walking the working tree there. PR 5 was read at `6792f34`: 12 version
strings in 10 files, `VERSION` and `CHANGELOG.md` at 1.0.1, 76 links in 23 Markdown
files, the Dependabot check at 2 entries, the 65536-byte DoH cap in both servers, and
`timeout-minutes` of 15/15/30/15 plus the release job's 20.

Previously established by running the jobs, not re-run in this pass:

- Dry run of every job in `ci.yml` and `release.yml`, one clean checkout per job,
  with a throwaway local `v1.0.1` tag, first at `fd72604`, re-run at `da8707a` after
  the release workflow changed and again at `e560454`: `validate`, `package` and
  `lint` all passed,
  actionlint reported no findings, and the `release` job passed after the gate — tag
  and `VERSION` agree on 1.0.1, `check-version.py` green, release body 5747 bytes
  from the curated notes with no `## Commits` section, `release archive: shippable`.
- The notes step with an earlier tag present: exactly one commit bullet under
  `## Commits`.
- The lint job's meaningfulness: a probe copy with an SC2086 finding fails at
  default severity while `bash -n` and `--severity=error` both pass it. All three
  shell scripts are clean at default severity.
- Merging the stack 1→5 with merge commits reproduces the tip tree exactly, and one
  squash of the whole stack onto `main` lands on that same tree; squashing the five
  branches onto `main` one at a time conflicts at PR 2 (`.github/workflows/ci.yml`).

Not checked (and cannot be from here): GitHub Actions on the remote — there is no
`gh` auth in this environment. The Windows `tracert` path is only proven by the
`windows-latest` job, `pwsh` is unavailable locally, and the release upload action
has never run because no tag was pushed.

All five tips carry the broadened triggers, and that is what a `pull_request` run needs:
GitHub uses the workflow file from the PR's merge commit (`refs/pull/N/merge`), the base
branch merged with the head, so the `on:` block in force is the one those two trees
carry. PR 1 adds the change as a commit, and each later branch merges the updated branch
below it, so every later merge ref has it too. Because it is in each PR's merge base, the
three-dot diff of PRs 2–5 does not repeat it. `ci.yml` itself already triggers on every
push and pull request in all five branches, so the rest of CI was never filtered.
`dependency-review.yml` is the exception: it is broadened in this PR, so this pull
request runs the dependency review while PRs 2–4, whose trees predate the change, still
skip it.
