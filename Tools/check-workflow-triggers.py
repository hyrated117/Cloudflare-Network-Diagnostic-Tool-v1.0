#!/usr/bin/env python3
"""Fail when a pull-request workflow filters pull_request by branch.

These branches are stacked, so a pull request is normally opened against the branch
below it rather than against main. A `branches:` filter on `pull_request` therefore
skips exactly the pull requests that are being reviewed: the workflow still parses,
GitHub just never creates the run, and nothing reports the gap. Every workflow here
that runs on pull requests - ci.yml, codeql.yml, dependency-review.yml and
security-scan.yml - must trigger on all of them.

The push trigger is deliberately not checked. It stays filtered so a branch is scanned
once, when it lands, and its filter differs between the pre-release branches.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ("ci.yml", "codeql.yml", "dependency-review.yml", "security-scan.yml")
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


def check_workflow(path, yaml):
    label = path.relative_to(ROOT).as_posix()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        return fail(f"{label} is not valid YAML{where}: {error}")
    if not isinstance(data, dict):
        return fail(f"{label} must be a mapping at the top level")

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


def main():
    try:
        import yaml
    except ModuleNotFoundError:
        return (
            "check-workflow-triggers.py needs PyYAML: python3 -m pip install "
            "pyyaml==6.0.4 (CI installs it before running this check)"
        )

    for name in WORKFLOWS:
        path = ROOT / ".github" / "workflows" / name
        if not path.is_file():
            fail(f".github/workflows/{name} is missing")
            continue
        check_workflow(path, yaml)

    if problems:
        for message in problems:
            print(f"FAIL: {message}", file=sys.stderr)
        return f"{len(problems)} problem(s) in the pull-request workflows' triggers"

    print(f"ok {len(WORKFLOWS)} workflows: pull_request is not filtered by branch")
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(1)
    sys.exit(result)
