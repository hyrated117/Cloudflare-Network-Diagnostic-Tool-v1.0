#!/usr/bin/env bash
# Replay verify-release.yml against a locally built archive, in one command.
#
# The verifier applies Tools/check-release-assets.sh to the two assets a release
# publishes. This builds them the way the release job does and runs that same script
# over them, so the harness cannot drift from the workflow: there is one copy of the
# checks. What it cannot exercise is the download and the trigger; everything after
# them is the workflow's own command.
#
# Usage: Tools/dry-run-verify-release.sh [version] [--keep]
#   [version]  version to build, defaulting to the repository's VERSION file
#   --keep     leave the scratch tree in place and print its path
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    echo "usage: $0 [version] [--keep]" >&2
    exit 2
}

KEEP=0
VERSION=""
for arg in "$@"; do
    case "$arg" in
        --keep) KEEP=1 ;;
        -*) echo "unknown option: $arg" >&2; usage ;;
        *)
            if [ -n "$VERSION" ]; then
                echo "unexpected argument: $arg" >&2
                usage
            fi
            VERSION="$arg"
            ;;
    esac
done

VERSION="${VERSION:-$(cat "${REPO_ROOT}/VERSION")}"
VERSION="${VERSION#v}"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/verify-release.XXXXXX")"
if [ "$KEEP" -eq 1 ]; then
    echo "scratch: ${WORK}"
else
    # shellcheck disable=SC2064 # expand now, so the path survives a later `cd`
    trap "rm -rf '${WORK}'" EXIT
fi

# A release is built from a tag checkout, never from a working tree, so stage the
# committed tree first: an untracked file (a stray __pycache__, a scratch directory)
# then cannot end up in the archive and fail a check that the release would pass.
# The consequence is that an uncommitted edit is not what gets built; commit it first.
echo "== stage the committed tree"
mkdir -p "${WORK}/src"
git -C "$REPO_ROOT" archive --format=tar HEAD | tar -x -C "${WORK}/src"

echo "== build the assets the publisher would upload"
"${WORK}/src/Tools/build-package.sh" "$VERSION" "${WORK}/assets"

echo "== apply the verifier's checks"
"${REPO_ROOT}/Tools/check-release-assets.sh" "$VERSION" "${WORK}/assets/v${VERSION}"

echo "ok: verify-release.yml's steps pass for v${VERSION}"
echo "not covered here: gh release download, and the release: published trigger"
