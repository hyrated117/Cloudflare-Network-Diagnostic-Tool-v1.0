#!/usr/bin/env python3
"""Fail when a workflow would silently skip a pull request or run unbounded.

Two invariants, both about a failure GitHub reports as nothing at all.

1. These branches are stacked, so a pull request is normally opened against the branch
   below it rather than against main. A `branches:` filter on `pull_request` therefore
   skips exactly the pull requests that are being reviewed: the workflow still parses,
   GitHub just never creates the run, and nothing reports the gap. Every workflow here
   that runs on pull requests - ci.yml, codeql.yml, dependency-review.yml and
   security-scan.yml - must trigger on all of them.

   The push trigger is deliberately not checked. It stays filtered so a branch is
   scanned once, when it lands, and its filter differs between the pre-release branches.

2. A job without `timeout-minutes` inherits GitHub's six-hour default, so a hung
   download, trace or upload holds a runner until then. CONTRIBUTING.md and CHANGELOG.md
   both state that every job has one, so every workflow file is checked for it. A job
   that calls a reusable workflow (`uses:`) is skipped: its timeout is the callee's to
   set, and the callee's own jobs are checked when that file is read.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"
PR_WORKFLOWS = ("ci.yml", "codeql.yml", "dependency-review.yml", "security-scan.yml")
BRANCH_FILTERS = ("branches", "branches-ignore")
MISSING = object()

problems = []


def fail(message):
    problems.append(message)


def event_map(spec):
    """Normalize an `on:` value to {event: configuration}, or None if unusable."""
    if spec is None:
        return {}
    if isinstance(spec, str):
        return {spec: None}
    if isinstance(spec, list):
        return {str(event): None for event in spec}
    if isinstance(spec, dict):
        return spec
    return None


def check_triggers(label, data):
    # PyYAML resolves the bare key `on` as the boolean True under YAML 1.1.
    spec = data.get("on", data.get(True, MISSING))
    if spec is MISSING:
        return fail(f"{label} has no on: trigger block")
    events = event_map(spec)
    if events is None:
        return fail(f"{label}: on: must be a mapping, a list or an event name")

    config = events.get("pull_request", MISSING)
    if config is MISSING:
        return fail(
            f"{label} does not trigger on pull_request at all, so no run is created "
            "for a pull request"
        )
    if config is None:
        print(f"ok {label}: pull_request runs for every branch")
        return None
    if not isinstance(config, dict):
        return fail(f"{label}: pull_request must be empty or a mapping, got {config!r}")

    filters = [key for key in BRANCH_FILTERS if key in config]
    if filters:
        return fail(
            f"{label} filters pull_request by {', '.join(filters)} "
            f"({config[filters[0]]!r}); a stacked pull request targets the branch "
            "below it, so that filter skips it while the file still parses"
        )
    # Other pull_request keys (types:, paths:) are not branch filters and are allowed.
    print(f"ok {label}: pull_request runs for every branch ({', '.join(sorted(config))} set)")


def check_timeouts(label, data):
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return fail(f"{label} has no jobs mapping, so its jobs cannot be checked")

    checked = 0
    for name, job in jobs.items():
        if not isinstance(job, dict):
            fail(f"{label}: job {name!r} must be a mapping")
            continue
        if "uses" in job:
            # Reusable workflow call: the callee's jobs carry their own timeouts.
            continue
        checked += 1
        value = job.get("timeout-minutes")
        if value is None:
            fail(
                f"{label}: job {name!r} has no timeout-minutes, so it inherits GitHub's "
                "six-hour default; a hung download, trace or upload would hold a runner "
                "until then"
            )
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            fail(
                f"{label}: job {name!r} has timeout-minutes {value!r}; "
                "expected a positive whole number of minutes"
            )
    if checked:
        print(f"ok {label}: {checked} job(s) set timeout-minutes")
    return None


def main():
    try:
        import yaml
    except ModuleNotFoundError:
        return (
            "check-workflow-triggers.py needs PyYAML: python3 -m pip install "
            "pyyaml==6.0.4 (CI installs it before running this check)"
        )

    paths = sorted(WORKFLOW_DIR.glob("*.yml")) if WORKFLOW_DIR.is_dir() else []
    if not paths:
        fail(".github/workflows has no .yml files")
    loaded = {}
    for path in paths:
        label = path.relative_to(ROOT).as_posix()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
            fail(f"{label} is not valid YAML{where}: {error}")
            continue
        if not isinstance(data, dict):
            fail(f"{label} must be a mapping at the top level")
            continue
        loaded[label] = data
        check_timeouts(label, data)

    for name in PR_WORKFLOWS:
        label = f".github/workflows/{name}"
        if label not in loaded:
            # Unparsable files already reported; only a genuinely absent file lands here.
            if label not in {p.relative_to(ROOT).as_posix() for p in paths}:
                fail(f"{label} is missing")
            continue
        check_triggers(label, loaded[label])

    if problems:
        for message in problems:
            print(f"FAIL: {message}", file=sys.stderr)
        return (
            f"{len(problems)} problem(s) in the workflows' pull_request triggers "
            "or job timeouts"
        )

    print(f"ok {len(PR_WORKFLOWS)} pull-request workflows: trigger not filtered by branch")
    print(f"ok {len(loaded)} workflows: every job that can set a timeout has one")
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(1)
    sys.exit(result)
