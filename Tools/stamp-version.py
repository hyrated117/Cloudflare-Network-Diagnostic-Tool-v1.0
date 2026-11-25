#!/usr/bin/env python3
"""Write the version from VERSION into every hand-maintained site.

The version lives in one place, `VERSION`, but it cannot be read at runtime: the
installers are copied to a user's machine as loose files and the servers are launched
directly, so all twelve sites listed in `version_sites.py` carry a literal. This
script stamps that literal into all of them, so a version bump is one edit plus one
command instead of twelve edits.

It rewrites only those twelve string sites. `CHANGELOG.md` and
`release/v<version>/release-notes.md` are prose and stay hand-written;
`Tools/check-version.py` fails until their newest section and title name the stamped
version, and fails if any site here drifts from `VERSION`.

Usage:
    python Tools/stamp-version.py --dry-run   # list what would change
    python Tools/stamp-version.py             # rewrite the sites
"""

import json
import sys

import version_sites as sites


def main(argv):
    unknown = sorted(set(argv) - {"--dry-run"})
    if unknown:
        print(f"usage: stamp-version.py [--dry-run] (unknown: {', '.join(unknown)})", file=sys.stderr)
        return 2
    dry_run = "--dry-run" in argv

    version, problems = sites.read_version()
    found, site_problems = sites.collect()
    problems += site_problems
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        print("FAIL: nothing written", file=sys.stderr)
        return 1

    lines = []
    writes = []
    for name, (pattern, expected) in sites.STRING_SITES.items():
        path = sites.REPO_ROOT / name
        text = path.read_text(encoding="utf-8")
        new_text, count = sites.replace_version(text, pattern, version)
        if count != expected:
            print(
                f"FAIL: {name}: expected {expected} version string(s), found {count}",
                file=sys.stderr,
            )
            print("FAIL: nothing written", file=sys.stderr)
            return 1
        if new_text == text:
            lines.append(f"  {name}: {version} (unchanged)")
        else:
            lines.append(f"  {name}: {'/'.join(found[name])} -> {version}")
            writes.append((path, new_text))

    for name in sites.JSON_SITES:
        path = sites.REPO_ROOT / name
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        data["version"] = version
        new_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if new_text == text:
            lines.append(f"  {name}: {version} (unchanged)")
        else:
            lines.append(f"  {name}: {found[name][0]} -> {version}")
            writes.append((path, new_text))

    print("\n".join(lines))
    total = sum(len(values) for values in found.values())
    if dry_run:
        print(
            f"dry run: VERSION is {version}; {len(writes)} of {len(found)} files would change, nothing written"
        )
        return 0

    for path, new_text in writes:
        path.write_text(new_text, encoding="utf-8")
    print(
        f"ok stamped {total} version strings in {len(found)} files with VERSION {version} "
        f"({len(writes)} changed)"
    )
    if writes:
        print(
            f"note: name {version} in CHANGELOG.md and release/v{version}/release-notes.md "
            "by hand; Tools/check-version.py checks both"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
