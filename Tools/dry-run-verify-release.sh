#!/usr/bin/env bash
# Replay verify-release.yml against a locally built archive, in one command.
#
# The workflow's steps after the download need nothing but the two assets, so this
# builds them exactly as the release job does and runs the workflow's own commands
# over the result. It cannot prove `gh release download` or the `release: published`
# trigger; it proves what happens after them, which is where a bad archive fails.
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
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "error: version must look like 1.2.3, got '${VERSION}'" >&2
    exit 2
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/verify-release.XXXXXX")"
if [ "$KEEP" -eq 1 ]; then
    echo "scratch: ${WORK}"
else
    # shellcheck disable=SC2064 # expand now, so the path survives a later `cd`
    trap "rm -rf '${WORK}'" EXIT
fi

echo "== step: build the archive the publisher would upload"
"${REPO_ROOT}/Tools/build-package.sh" "$VERSION" "$WORK"
ASSETS="${WORK}/v${VERSION}"

echo "== step: check the tag"
RELEASE_TAG="v${VERSION}"
if [[ ! "$RELEASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "FAIL: invalid release tag: ${RELEASE_TAG}" >&2
    exit 1
fi
echo "verifying ${RELEASE_TAG}"

# The workflow downloads the two assets into dist/v<version>; the build wrote them
# into the same layout, so the steps below are the workflow's commands unchanged.
echo "== step: check the published archive"
python3 "${REPO_ROOT}/Tools/check-archive.py" "${ASSETS}/mcp-installer-pack.tar.gz" \
    --expect-checksum --extract-to "${WORK}/pack"

echo "== step: install from the published archive and handshake"
python3 "${REPO_ROOT}/Tools/check-installers.py" --installers-root "${WORK}/pack"

echo "ok: verify-release.yml's steps pass for ${RELEASE_TAG}"
echo "not covered here: gh release download, and the release: published trigger"
