#!/usr/bin/env python3
"""Check that a release archive is shippable, and optionally extract it.

The archive contract lives here so every platform checks the same list. What the
extracted tree then installs is checked by Tools/check-installers.py (POSIX) or
Tools/check-installers.ps1 (Windows), which take the tree root as an argument.

The archive also ships `VERSION`, and this check requires it to match the version
stamped into the server and the unified installer the pack carries, so a pack built
from a half-bumped tree cannot be published under either version.
"""

import argparse
import hashlib
import re
import sys
import tarfile
from pathlib import Path

REQUIRED = (
    "LICENSE",
    "README.md",
    "VERSION",
    "docs/README.md",
    "server/index.py",
    "server/index.js",
    "installers/install-mcp-server.sh",
    "installers/install-mcp-unified.sh",
    "installers/install-mcp-server.ps1",
    "installers/install-mcp-unified.ps1",
)
JUNK = ("__pycache__/", "node_modules/", ".git/", ".DS_Store")
# The two entry points a user actually launches, not every stamped site: the whole set
# is checked in the repository by Tools/check-version.py before anything is packaged.
VERSION_SITES = {
    "server/index.js": r"this\.version\s*=\s*'([^']+)'",
    "installers/install-mcp-unified.sh": r"^VERSION=\"([^\"]+)\"",
}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def checksum(archive, checksum_file, required):
    if not checksum_file.is_file():
        if required:
            print(f"FAIL: no SHA256SUMS next to {archive}", file=sys.stderr)
            return False
        return True
    fields = checksum_file.read_text(encoding="utf-8").split()
    expected, name = fields[0].lower(), fields[-1].lstrip("*")
    if name != archive.name:
        print(f"FAIL: SHA256SUMS covers {name}, not {archive.name}", file=sys.stderr)
        return False
    actual = digest(archive)
    if actual != expected:
        print(f"FAIL: checksum mismatch: archive is {actual}, SHA256SUMS says {expected}", file=sys.stderr)
        return False
    print("checksum: matches SHA256SUMS")
    return True


def contents(archive):
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    ok = True
    for required in REQUIRED:
        if required not in names:
            print(f"FAIL: archive is missing {required}", file=sys.stderr)
            ok = False
    junk = [name for name in names if any(marker in name for marker in JUNK)]
    if junk:
        print(f"FAIL: archive carries generated files: {junk[:3]}", file=sys.stderr)
        ok = False
    if ok:
        print(f"archive: {len(names)} entries, required files present, no build junk")
    return ok


def version(archive):
    """Require the pack's VERSION to match the server and installer it ships."""
    with tarfile.open(archive) as tar:
        raw = tar.extractfile("VERSION").read().decode("utf-8")
        words = raw.split()
        if len(words) != 1 or not SEMVER.match(words[0]):
            print(f"FAIL: VERSION in the archive is not MAJOR.MINOR.PATCH: {raw.strip()!r}", file=sys.stderr)
            return False
        expected = words[0]
        ok = True
        for name, pattern in VERSION_SITES.items():
            found = re.findall(pattern, tar.extractfile(name).read().decode("utf-8"), re.MULTILINE)
            if len(found) != 1:
                print(f"FAIL: {name} in the archive has {len(found)} version string(s), expected 1", file=sys.stderr)
                ok = False
            for value in found:
                if value != expected:
                    print(f"FAIL: VERSION in the archive says {expected}, but {name} says {value}", file=sys.stderr)
                    ok = False
    if ok:
        print(f"version: VERSION {expected} matches the packaged server and installer")
    return ok


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        try:
            tar.extractall(destination, filter="data")
        except TypeError:  # Python < 3.12
            tar.extractall(destination)
    print(f"extracted to {destination}")


def main():
    parser = argparse.ArgumentParser(description="Check a release archive's contents.")
    parser.add_argument("archive", help="path to mcp-installer-pack.tar.gz")
    parser.add_argument("--extract-to", metavar="DIR", help="extract the archive here")
    parser.add_argument(
        "--expect-checksum",
        action="store_true",
        help="require a SHA256SUMS file next to the archive and verify it",
    )
    args = parser.parse_args()

    archive = Path(args.archive).resolve()
    if not archive.is_file():
        print(f"FAIL: archive not found: {archive}", file=sys.stderr)
        return 1

    ok = checksum(archive, archive.parent / "SHA256SUMS", args.expect_checksum)
    ok = contents(archive) and ok
    if not ok:
        return 1

    if not version(archive):
        return 1

    if args.extract_to:
        extract(archive, Path(args.extract_to).resolve())

    print("release archive: shippable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
