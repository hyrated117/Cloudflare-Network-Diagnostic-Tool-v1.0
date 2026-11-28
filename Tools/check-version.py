#!/usr/bin/env python3
"""Check that VERSION, every version string and the newest CHANGELOG section agree.

`VERSION` at the repository root is the single source for the version. It cannot be
read at runtime: the installers are copied to a user's machine as loose files and the
servers are launched directly, so each of the ten sites listed in
`version_sites.py` carries a literal that `Tools/stamp-version.py` writes. This script
fails when any of those sites drifts from `VERSION`, when the sites disagree with each
other, when `CHANGELOG.md`'s newest dated release section names a different version, or
when `release/v<version>/release-notes.md` is missing or its title does not name that
version — that file is the release body `release.yml` publishes.
"""

import re
import sys

import version_sites as sites

CHANGELOG = sites.REPO_ROOT / "CHANGELOG.md"
RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def main(argv):
    if argv:
        print(f"usage: check-version.py takes no arguments (got: {' '.join(argv)})", file=sys.stderr)
        return 2

    version, problems = sites.read_version()
    found, site_problems = sites.collect()
    problems += site_problems

    for name, values in sorted(found.items()):
        print(f"  {name}: {', '.join(values)}")
        if version is not None:
            for value in values:
                if value != version:
                    problems.append(f"{name}: {value} but VERSION says {version}")

    versions = {value for values in found.values() for value in values}
    if len(versions) != 1:
        problems.append(
            "version strings disagree: "
            + ", ".join(f"{name}={'/'.join(values)}" for name, values in sorted(found.items()))
        )
    elif version is None:
        # VERSION is unusable (already reported); still let the changelog be compared.
        version = versions.pop()
        if not sites.SEMVER.match(version):
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
            newest = headings[0][0]
            if version is not None and newest != version:
                problems.append(
                    f"CHANGELOG.md's newest release is {newest}, but VERSION says {version}"
                )
            notes = sites.REPO_ROOT / "release" / f"v{newest}" / "release-notes.md"
            if not notes.is_file():
                problems.append(f"{notes.relative_to(sites.REPO_ROOT)} is missing (the release body for v{newest})")
            else:
                title = notes.read_text(encoding="utf-8").splitlines()[0]
                if f"v{newest}" not in title:
                    problems.append(f"{notes.relative_to(sites.REPO_ROOT)}: title does not name v{newest}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    total = sum(len(values) for values in found.values())
    print(f"ok {total} version strings, VERSION and CHANGELOG.md [{version}] agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
