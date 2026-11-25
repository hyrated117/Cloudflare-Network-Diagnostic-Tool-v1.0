#!/usr/bin/env python3
"""Check that every version string and the newest CHANGELOG section agree.

The version is maintained by hand in ten files: both servers' `initialize`
response, both `package.json` files, the Node CLI, the Python installer, and the
four shell/PowerShell installers (the two single-runtime ones write it into two
configs each). Nothing derives one from another, so a bump can land in only some of
them. This script fails when they disagree, when `CHANGELOG.md`'s newest release
section names a different version, or when `release/v<version>/release-notes.md` is
missing, which is the file the release workflow uses as the release body.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# file -> (pattern, number of version strings it must contain)
STRING_SOURCES = {
    "server/index.js": (r"this\.version\s*=\s*'([^']+)'", 1),
    "server/index.py": (r"self\.version\s*=\s*\"([^\"]+)\"", 1),
    "installers/cli.js": (r"const VERSION\s*=\s*'([^']+)'", 1),
    "installers/install-mcp-server.py": (r"^VERSION\s*=\s*\"([^\"]+)\"", 1),
    "installers/install-mcp-unified.sh": (r"^VERSION=\"([^\"]+)\"", 1),
    "installers/install-mcp-unified.ps1": (r"^\$version\s*=\s*\"([^\"]+)\"", 1),
    "installers/install-mcp-server.sh": (r"\"version\":\s*\"([^\"]+)\"", 2),
    "installers/install-mcp-server.ps1": (r"version\s*=\s*\"([^\"]+)\"", 2),
}
JSON_SOURCES = ("server/package.json", "installers/package.json")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def collect():
    """Return {file: [version, ...]} and a list of structural problems."""
    found = {}
    problems = []
    for name, (pattern, expected) in STRING_SOURCES.items():
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        matches = re.findall(pattern, text, re.MULTILINE)
        if len(matches) != expected:
            problems.append(
                f"{name}: expected {expected} version string(s), found {len(matches)}"
            )
            continue
        found[name] = matches
    for name in JSON_SOURCES:
        try:
            data = json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"{name}: not valid JSON ({error})")
            continue
        version = data.get("version")
        if not isinstance(version, str):
            problems.append(f'{name}: no "version" string')
            continue
        found[name] = [version]
    return found, problems


def main():
    found, problems = collect()
    versions = {version for values in found.values() for version in values}
    for name, values in sorted(found.items()):
        print(f"  {name}: {', '.join(values)}")

    if len(versions) != 1:
        problems.append(
            "version strings disagree: "
            + ", ".join(f"{name}={'/'.join(values)}" for name, values in sorted(found.items()))
        )
        version = None
    else:
        version = versions.pop()
        if not SEMVER.match(version):
            problems.append(f'version "{version}" is not MAJOR.MINOR.PATCH')

    if not CHANGELOG.is_file():
        problems.append("CHANGELOG.md is missing")
    else:
        changelog = CHANGELOG.read_text(encoding="utf-8")
        headings = RELEASE_HEADING.findall(changelog)
        if "## [Unreleased]" not in changelog:
            problems.append('CHANGELOG.md has no "## [Unreleased]" section')
        if not headings:
            problems.append("CHANGELOG.md has no dated release section")
        else:
            newest, date = headings[0]
            if version is not None and newest != version:
                problems.append(
                    f"CHANGELOG.md's newest release is {newest}, but the version strings say {version}"
                )
            notes = REPO_ROOT / "release" / f"v{newest}" / "release-notes.md"
            if not notes.is_file():
                problems.append(f"{notes.relative_to(REPO_ROOT)} is missing (the release body for v{newest})")
            else:
                title = notes.read_text(encoding="utf-8").splitlines()[0]
                if f"v{newest}" not in title:
                    problems.append(f"{notes.relative_to(REPO_ROOT)}: title does not name v{newest}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"ok {sum(len(values) for values in found.values())} version strings and CHANGELOG.md [{version}] agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
