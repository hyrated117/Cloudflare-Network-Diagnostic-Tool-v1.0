#!/usr/bin/env python3
"""Check .github/dependabot.yml so a typo cannot silently stop the action updates.

GitHub reads this file only from the default branch and says nothing when it is
malformed or a key is misspelled: the updates simply never arrive. No workflow reads
it either, so without this check a broken file is invisible until someone notices the
Dependabot pull requests stopped.

The repository's own tools are stdlib-only; this one needs PyYAML, because writing a
YAML parser to validate a YAML file would be a worse failure mode than installing the
parser. CI installs it before running this. Every rule below is pinned both ways by
`Tools/test_check_dependabot.py`, which runs the checks against mappings rather than
files, so it needs no PyYAML itself.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".github" / "dependabot.yml"
WORKFLOWS = ROOT / ".github" / "workflows"

# The keys this check knows about. Anything else is a warning rather than a failure:
# GitHub keeps adding keys, and a stale list here should not fail a sound config.
TOP_LEVEL = {
    "version",
    "updates",
    "registries",
    "enable-beta-ecosystems",
    "multi-ecosystem-groups",
}
ENTRY = {
    "package-ecosystem",
    "directory",
    "directories",
    "schedule",
    "allow",
    "assignees",
    "cooldown",
    "commit-message",
    "groups",
    "ignore",
    "insecure-external-code-execution",
    "labels",
    "milestone",
    "multi-ecosystem-group",
    "open-pull-requests-limit",
    "pull-request-branch-name",
    "rebase-strategy",
    "registries",
    "reviewers",
    "target-branch",
    "vendor",
    "versioning-strategy",
}
SCHEDULE = {"interval", "day", "time", "timezone", "cronjob"}
INTERVALS = {"daily", "weekly", "monthly", "quarterly", "semiannually", "yearly", "cron"}

problems = []


def fail(message):
    problems.append(message)


def unrecognized(label, keys, known):
    unknown = sorted(set(keys) - known)
    if unknown:
        print(
            f"warning: {label}: unrecognized key(s) {', '.join(unknown)}; "
            "add them to this check if they are real Dependabot keys",
            file=sys.stderr,
        )


def check_entry(index, entry):
    label = f"updates[{index}]"
    if not isinstance(entry, dict):
        return fail(f"{label}: must be a mapping, got {type(entry).__name__}")
    unrecognized(label, entry, ENTRY)

    ecosystem = entry.get("package-ecosystem")
    if not isinstance(ecosystem, str) or not ecosystem.strip():
        fail(f"{label}: package-ecosystem must be a name such as 'github-actions'")

    paths = [key for key in ("directory", "directories") if key in entry]
    if len(paths) != 1:
        fail(f"{label}: set exactly one of directory or directories")
    elif paths[0] == "directory" and not isinstance(entry["directory"], str):
        fail(f"{label}: directory must be a string")
    elif paths[0] == "directories" and not (
        isinstance(entry["directories"], list)
        and entry["directories"]
        and all(isinstance(item, str) for item in entry["directories"])
    ):
        fail(f"{label}: directories must be a non-empty list of strings")

    schedule = entry.get("schedule")
    if not isinstance(schedule, dict):
        return fail(f"{label}: needs a schedule mapping with an interval")
    unrecognized(f"{label}.schedule", schedule, SCHEDULE)
    interval = schedule.get("interval")
    if interval not in INTERVALS:
        fail(
            f"{label}.schedule: interval must be one of {', '.join(sorted(INTERVALS))}, "
            f"got {interval!r}"
        )
    if interval == "cron" and not isinstance(schedule.get("cronjob"), str):
        fail(f"{label}.schedule: interval cron needs a cronjob string")


def pinned_workflows():
    """Names of the workflow files that use an action, so a pin updater must cover them."""
    return sorted(
        path.name
        for path in WORKFLOWS.glob("*.yml")
        if any(
            line.strip().startswith("uses: ")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    )


def check_config(config, pinned):
    """Assert the top-level keys, every update entry, and the pin coverage of `pinned`.

    Returns the `updates` list so the caller can report what it found.
    """
    if config.get("version") != 2:
        fail(f"version must be 2, got {config.get('version')!r}")

    updates = config.get("updates")
    if not isinstance(updates, list) or not updates:
        fail("updates must be a non-empty list")
        updates = []
    for index, entry in enumerate(updates):
        check_entry(index, entry)

    # The workflows pin every action to a commit SHA, so the file has to keep the
    # github-actions entry that moves those pins; otherwise they never get updated.
    covered = any(
        isinstance(entry, dict)
        and entry.get("package-ecosystem") == "github-actions"
        and entry.get("directory") == "/"
        for entry in updates
    )
    if pinned and not covered:
        fail(
            "the workflows use actions in "
            + ", ".join(pinned)
            + ", but no github-actions entry with directory '/' exists, "
            "so those actions would never be updated"
        )
    return updates


def main():
    try:
        import yaml
    except ModuleNotFoundError:
        return (
            "check-dependabot.py needs PyYAML: python3 -m pip install pyyaml==6.0.4 "
            "(CI installs it before running this check)"
        )

    if not CONFIG.is_file():
        return f"{CONFIG.relative_to(ROOT)} is missing; Dependabot is not configured at all"
    try:
        config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        return f"{CONFIG.relative_to(ROOT)} is not valid YAML{where}: {error}"
    if not isinstance(config, dict):
        return f"{CONFIG.relative_to(ROOT)} must be a mapping at the top level"
    unrecognized(CONFIG.relative_to(ROOT), config, TOP_LEVEL)

    updates = check_config(config, pinned_workflows())

    if problems:
        for message in problems:
            print(f"FAIL: {message}", file=sys.stderr)
        return f"{len(problems)} problem(s) in {CONFIG.relative_to(ROOT)}"

    summary = ", ".join(
        f"{entry['package-ecosystem']} in {entry.get('directory', entry.get('directories'))}"
        for entry in updates
        if isinstance(entry, dict)
    )
    print(f"{CONFIG.relative_to(ROOT)}: {len(updates)} update entry(ies): {summary}")
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(1)
    sys.exit(result)
