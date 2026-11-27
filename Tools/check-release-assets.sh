#!/usr/bin/env bash
# Apply the release contract to a release's published assets, laid out the way
# build-package.sh writes them: mcp-installer-pack.tar.gz and SHA256SUMS in one
# directory, built from the version being released.
#
# This is the whole post-download half of verify-release.yml's Linux job. That job and
# Tools/dry-run-verify-release.sh both call it, so the checks have one copy and the
# harness cannot drift from the workflow. The workflow's Windows job runs the archive
# check with check-archive.py directly, then check-installers.ps1 on the extracted
# pack, so the PowerShell installers are handshaked without a POSIX installer run.
#
# Usage: Tools/check-release-assets.sh <version> <assets-dir>
#   <version>     the release being verified, with or without a leading v
#   <assets-dir>  directory holding mcp-installer-pack.tar.gz and SHA256SUMS
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <version> <assets-dir>" >&2
    exit 2
fi

VERSION="${1#v}"
ASSETS="$2"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: version must look like 1.2.3, got '$1'" >&2
    exit 2
fi
if [ ! -d "$ASSETS" ]; then
    echo "error: no assets directory at '${ASSETS}'" >&2
    exit 1
fi

ARCHIVE="${ASSETS}/mcp-installer-pack.tar.gz"
if [ ! -f "$ARCHIVE" ]; then
    echo "error: no mcp-installer-pack.tar.gz in '${ASSETS}'" >&2
    exit 1
fi

# The extracted tree only feeds the installer check, so it goes in a directory this
# script owns and removes. Extracting elsewhere would write into the caller's tree,
# and a pack left over from an earlier run would be checked alongside this one.
PACK="$(mktemp -d "${TMPDIR:-/tmp}/release-pack.XXXXXX")"
trap 'rm -rf "$PACK"' EXIT

# The checksum must cover this archive, the archive must be stamped with the version
# being released, the required files must be present, and the extracted copy must
# install.
python3 "${REPO_ROOT}/Tools/check-archive.py" "$ARCHIVE" \
    --expect-checksum --expect-version "$VERSION" --extract-to "$PACK"

# An intact archive is not the same as an installable one: this runs the packaged
# installers against the extracted tree and requires the initialize handshake.
python3 "${REPO_ROOT}/Tools/check-installers.py" --installers-root "$PACK"
