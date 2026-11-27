#!/usr/bin/env bash
# Apply the release contract to a release's published assets, laid out the way
# build-package.sh writes them: mcp-installer-pack.tar.gz and SHA256SUMS in one
# directory.
#
# This is the whole post-download half of verify-release.yml. verify-release.yml and
# Tools/dry-run-verify-release.sh both call it, so the checks have one copy and the
# harness cannot drift from the workflow. The extracted tree lands in `pack` beside
# the assets directory.
#
# Usage: Tools/check-release-assets.sh <version> <assets-dir>
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <version> <assets-dir>" >&2
    exit 2
fi

VERSION="${1#v}"
ASSETS="${2%/}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: version must look like 1.2.3, got '${VERSION}'" >&2
    exit 2
fi

ARCHIVE="${ASSETS}/mcp-installer-pack.tar.gz"
PACK="$(dirname "${ASSETS}")/pack"
if [ ! -f "$ARCHIVE" ]; then
    echo "error: no archive at ${ARCHIVE}" >&2
    exit 1
fi

# The checksum must cover this archive, the required files must be present, and the
# version stamped inside must match the release.
python3 "${REPO_ROOT}/Tools/check-archive.py" "$ARCHIVE" \
    --expect-checksum --extract-to "$PACK"

# An intact archive is not the same as an installable one: this runs the packaged
# installers against the extracted tree and requires the initialize handshake.
python3 "${REPO_ROOT}/Tools/check-installers.py" --installers-root "$PACK"
