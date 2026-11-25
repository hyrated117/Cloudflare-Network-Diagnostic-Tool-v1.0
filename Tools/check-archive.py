#!/usr/bin/env python3
"""Check that a release archive is shippable, and optionally extract it.

The archive contract lives here so every platform checks the same list. What the
extracted tree then installs is checked by Tools/check-installers.py (POSIX) or
Tools/check-installers.ps1 (Windows), which take the tree root as an argument.
"""

import argparse
import hashlib
import sys
import tarfile
from pathlib import Path

REQUIRED = (
    "LICENSE",
    "README.md",
    "docs/README.md",
    "server/index.py",
    "server/index.js",
    "installers/install-mcp-server.sh",
    "installers/install-mcp-unified.sh",
    "installers/install-mcp-server.ps1",
    "installers/install-mcp-unified.ps1",
)
JUNK = ("__pycache__/", "node_modules/", ".git/", ".DS_Store")


def checksum(archive, checksum_file, required):
    if not checksum_file.is_file():
        if required:
            print(f"FAIL: no SHA256SUMS next to {archive}", file=sys.stderr)
            return False
        return True
    expected = checksum_file.read_text(encoding="utf-8").split()[0].lower()
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
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

    if args.extract_to:
        extract(archive, Path(args.extract_to).resolve())

    print("release archive: shippable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
