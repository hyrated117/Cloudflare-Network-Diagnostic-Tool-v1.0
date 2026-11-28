#!/usr/bin/env python3
"""The one list of hand-maintained version sites, shared by the checker and stamper.

The version itself lives in `VERSION` at the repository root. It cannot be read at
runtime: the installers are copied to a user's machine as loose files and the servers
are launched directly, so every site below carries a literal string. `Tools/stamp-version.py`
writes `VERSION` into all of them and `Tools/check-version.py` fails when one drifts.

Each pattern must capture the version string as group 1, so the stamper can replace
exactly that substring and keep the surrounding quoting and syntax untouched.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# file -> (pattern, number of version strings it must contain)
STRING_SITES = {
    "server/index.js": (r"this\.version\s*=\s*'([^']+)'", 1),
    "server/index.py": (r"self\.version\s*=\s*\"([^\"]+)\"", 1),
    "installers/cli.js": (r"const VERSION\s*=\s*'([^']+)'", 1),
    "installers/install-mcp-server.py": (r"^VERSION\s*=\s*\"([^\"]+)\"", 1),
    "installers/install-mcp-unified.sh": (r"^VERSION=\"([^\"]+)\"", 1),
    "installers/install-mcp-unified.ps1": (r"^\$version\s*=\s*\"([^\"]+)\"", 1),
    "installers/install-mcp-server.sh": (r"\"version\":\s*\"([^\"]+)\"", 2),
    "installers/install-mcp-server.ps1": (r"version\s*=\s*\"([^\"]+)\"", 2),
}
# file -> the JSON paths that carry its version, in the order they are reported. A
# package.json holds it at "version"; an npm lockfile repeats it for the package itself
# under packages[""], so both are stamped or the lockfile drifts from the manifest.
JSON_SITES = {
    "server/package.json": (("version",),),
    "installers/package.json": (("version",),),
    "server/package-lock.json": (("version",), ("packages", "", "version")),
    "installers/package-lock.json": (("version",), ("packages", "", "version")),
}


def read_version():
    """Return (version, problems) for the VERSION file."""
    if not VERSION_FILE.is_file():
        return None, ["VERSION is missing; it holds the one version every site is stamped from"]
    words = VERSION_FILE.read_text(encoding="utf-8").split()
    if len(words) != 1:
        return None, ["VERSION must contain exactly one version string"]
    version = words[0]
    if not SEMVER.match(version):
        return None, [f'VERSION "{version}" is not MAJOR.MINOR.PATCH']
    return version, []


def json_version(data, path):
    """Return the string at `path` in `data`, or None when it is absent or not a string."""
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, str) else None


def set_json_version(data, path, version):
    """Write `version` at `path` in `data`; the caller has already checked it exists."""
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = version


def path_label(path):
    """How a JSON path is named in a problem, e.g. packages.`version` under an empty key."""
    return ".".join(part for part in path if part) or "<root>"


def collect():
    """Return ({file: [version, ...]}, problems) read from the twelve sites."""
    found = {}
    problems = []
    for name, (pattern, expected) in STRING_SITES.items():
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        matches = re.findall(pattern, text, re.MULTILINE)
        if len(matches) != expected:
            problems.append(
                f"{name}: expected {expected} version string(s), found {len(matches)}"
            )
            continue
        found[name] = matches
    for name, paths in JSON_SITES.items():
        try:
            data = json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"{name}: not valid JSON ({error})")
            continue
        values = []
        for path in paths:
            value = json_version(data, path)
            if value is None:
                problems.append(f'{name}: no "version" string at {path_label(path)}')
                break
            values.append(value)
        else:
            found[name] = values
    return found, problems


def replace_version(text, pattern, version):
    """Replace group 1 of every match with version; return (new text, match count)."""
    count = 0

    def substitute(match):
        nonlocal count
        count += 1
        start, end = match.span(1)
        offset = match.start(0)
        return match.group(0)[: start - offset] + version + match.group(0)[end - offset :]

    return re.sub(pattern, substitute, text, flags=re.MULTILINE), count
