#!/usr/bin/env bash
# Build the release archive. Used by release.yml and by the packaging CI job so the
# two cannot drift apart.
#
# Usage: Tools/build-package.sh <version> [output-root]
#   <version>      v1.2.3 or 1.2.3; outputs to <output-root>/v<version>/
#   [output-root]  defaults to <repo>/dist
set -euo pipefail

if [ "$#" -lt 1 ] || [ -z "${1:-}" ]; then
    echo "usage: $0 <version> [output-root]" >&2
    exit 2
fi

VERSION="${1#v}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="${2:-${REPO_ROOT}/dist}"
DEST="${OUTPUT_ROOT}/v${VERSION}"
ARCHIVE="${DEST}/mcp-installer-pack.tar.gz"
CONTENTS=(installers server docs LICENSE README.md)

for entry in "${CONTENTS[@]}"; do
    if [ ! -e "${REPO_ROOT}/${entry}" ]; then
        echo "error: archive entry missing from the repository: ${entry}" >&2
        exit 1
    fi
done

mkdir -p "${DEST}"
tar -czf "${ARCHIVE}" -C "${REPO_ROOT}" "${CONTENTS[@]}"
tar -tzf "${ARCHIVE}" >/dev/null
# Git Bash and macOS spell the checksum tool differently.
if command -v sha256sum >/dev/null 2>&1; then
    ( cd "${DEST}" && sha256sum mcp-installer-pack.tar.gz > SHA256SUMS )
elif command -v shasum >/dev/null 2>&1; then
    ( cd "${DEST}" && shasum -a 256 mcp-installer-pack.tar.gz > SHA256SUMS )
else
    echo "error: need sha256sum or shasum to write SHA256SUMS" >&2
    exit 1
fi

echo "${ARCHIVE}"
