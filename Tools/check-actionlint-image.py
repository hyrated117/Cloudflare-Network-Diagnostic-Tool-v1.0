#!/usr/bin/env python3
"""Run the actionlint image the `lint` job uses, without a Docker daemon.

`lint` runs `docker://rhysd/actionlint@sha256:b1934ee5…`, so the check that matters is
that the bytes behind that digest pass on this tree — not that some locally installed
actionlint does. Docker Hub lets an owner repoint a tag, but not a digest, and the image
also bundles shellcheck, which actionlint runs over every `run:` block when it finds it
on `PATH`. This script reproduces the step from the registry alone:

1. read the `docker://…@sha256:<digest>` pin out of `.github/workflows`;
2. fetch the OCI index at that digest, then the `linux/amd64` manifest, skipping the
   buildx attestation entries whose platform is `unknown`;
3. download each layer and verify its sha256 before reading it, then extract the
   `actionlint` and `shellcheck` files into a temporary directory;
4. run `actionlint` with no arguments from the repository root, as the image's
   `ENTRYPOINT` does under `docker://`, and fail if anything is reported.

It needs network access and a 25 MiB download, so it is not part of `Validate`;
`Tools/test_check_actionlint_image.py` pins its rules offline and `Validate` runs that
as `Self-test the image check`. Run this alongside `Tools/check-pins.py` when a pin
changes or periodically.

Usage:
    python3 Tools/check-actionlint-image.py
"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
REGISTRY = "https://registry-1.docker.io"
AUTH = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:{image}:pull"
PLATFORM = {"os": "linux", "architecture": "amd64"}
PROGRAMS = ("actionlint", "shellcheck")
USER_AGENT = "check-actionlint-image"
ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def docker_references(text: str, where: str = "") -> list[tuple[str, str]]:
    """Every `uses: docker://image@sha256:<digest>` in one workflow, comments excluded."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("#"):
            continue
        marker = "uses: docker://"
        if marker not in line:
            continue
        value = line.split(marker, 1)[1].split()[0]
        image, _, digest = value.partition("@sha256:")
        if not image or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise LookupError(
                f"{where}:{number}: '{value}' is not docker://image@sha256:<64 hex>"
            )
        found.append((image, f"sha256:{digest}"))
    return found


def pinned_image(workflows: Path) -> tuple[str, str]:
    """The single image digest the workflows pin, with every file that pins it."""
    found: dict[tuple[str, str], list[str]] = {}
    for path in sorted(workflows.glob("*.y*ml")):
        for reference in docker_references(path.read_text(encoding="utf-8"), path.name):
            found.setdefault(reference, []).append(path.name)
    if not found:
        raise LookupError(f"no docker://…@sha256:<digest> pin in {workflows}")
    if len(found) > 1:
        listed = "; ".join(
            f"{image}@{digest[:19]}… in {', '.join(sorted(set(files)))}"
            for (image, digest), files in found.items()
        )
        raise LookupError(f"more than one image is pinned: {listed}")
    (image, digest), files = next(iter(found.items()))
    return image, digest


def verify_digest(data: bytes, digest: str) -> bytes:
    actual = "sha256:" + hashlib.sha256(data).hexdigest()
    if actual != digest:
        raise LookupError(f"blob {digest} hashes to {actual}")
    return data


def select_platform(index: dict, platform: dict = PLATFORM) -> dict:
    """The index entry for one platform, ignoring the attestations under `unknown`."""
    for entry in index.get("manifests", []):
        found = entry.get("platform") or {}
        if found.get("os") == platform["os"] and found.get("architecture") == platform[
            "architecture"
        ]:
            return entry
    raise LookupError(f"no {platform['os']}/{platform['architecture']} manifest in the index")


def extract_programs(layers: Iterable[bytes], programs: Iterable[str] = PROGRAMS) -> dict:
    """The named programs from a stack of layer tarballs, keyed by basename."""
    wanted = tuple(programs)
    found: dict[str, bytes] = {}
    for data in layers:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                if not member.isfile() or Path(member.name).name not in wanted:
                    continue
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise LookupError(f"refusing the layer's path '{member.name}'")
                handle = archive.extractfile(member)
                assert handle is not None
                payload = handle.read()
                name = Path(member.name).name
                if name in found and found[name] != payload:
                    raise LookupError(f"two layers disagree about {name}")
                found[name] = payload
    missing = [name for name in wanted if name not in found]
    if missing:
        raise LookupError("the image contains no " + ", ".join(missing))
    return found


def token_for(image: str) -> str:
    request = urllib.request.Request(AUTH.format(image=image), headers={"User-Agent": USER_AGENT})
    return json.load(urllib.request.urlopen(request, timeout=60))["token"]


def fetch(url: str, token: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"}
    if accept:
        headers["Accept"] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120).read()


def version_of(binary: Path, env: dict) -> str:
    result = subprocess.run([str(binary), "-version"], capture_output=True, text=True, env=env)
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"


def shellcheck_version(binary: Path, env: dict) -> str:
    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, env=env)
    for line in result.stdout.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("usage: python3 Tools/check-actionlint-image.py", file=sys.stderr)
        return 2
    try:
        image, digest = pinned_image(WORKFLOWS)
        token = token_for(image)
        index = json.loads(fetch(f"{REGISTRY}/v2/{image}/manifests/{digest}", token, ACCEPT))
        if "manifests" in index:
            index = json.loads(
                fetch(
                    f"{REGISTRY}/v2/{image}/manifests/{select_platform(index)['digest']}",
                    token,
                    ACCEPT,
                )
            )
        layers = [
            verify_digest(fetch(f"{REGISTRY}/v2/{image}/blobs/{layer['digest']}", token), layer["digest"])
            for layer in index.get("layers", [])
        ]
        programs = extract_programs(layers)
    except (LookupError, OSError, ValueError, KeyError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as directory:
        bindir = Path(directory)
        for name, payload in programs.items():
            path = bindir / name
            path.write_bytes(payload)
            path.chmod(0o755)
        env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
        actionlint = version_of(bindir / "actionlint", env)
        shellcheck = shellcheck_version(bindir / "shellcheck", env)
        workflows = sorted(WORKFLOWS.glob("*.y*ml"))
        result = subprocess.run(
            [str(bindir / "actionlint")], cwd=ROOT, capture_output=True, text=True, env=env
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            print(
                f"FAIL: actionlint {actionlint} from {image}@{digest} reports problems",
                file=sys.stderr,
            )
            print(output, file=sys.stderr)
            return 1
        total = sum(len(layer) for layer in layers)
        print(
            f"ok {image}@{digest} (actionlint {actionlint}, shellcheck {shellcheck}, "
            f"{len(layers)} layers, {total // 1024} KiB): {len(workflows)} workflow(s), "
            "nothing reported"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
