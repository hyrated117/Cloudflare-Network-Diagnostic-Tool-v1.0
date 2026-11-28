#!/usr/bin/env python3
"""Audit every pinned action and image in the workflows against its release comment.

Dependabot's `github-actions` updater moves a pinned SHA and the comment beside it
together, but it cannot notice that the comment was wrong in the first place: a pin
copied from another release, or a tag that points somewhere else than the SHA, passes
every offline check this repository runs. This script asks the registries:

- for `owner/repo[/subpath]@<40-hex>  # vX.Y.Z`, that `vX.Y.Z` in `owner/repo`
  resolves to that commit;
- for `docker://image[:tag]@sha256:<digest>`, that the registry serves that digest,
  and that the tag resolves to it when the reference carries one.

It needs network access, so it is not part of `Validate`. `Tools/test_check_pins.py`
pins its rules offline and `Validate` runs that as `Self-test the pin check`; run this
after a pin changes, or periodically, with `GITHUB_TOKEN` set if nine-odd lookups would
push past the unauthenticated GitHub API quota (60 requests an hour).

Two traps it handles, because each looks like a mismatch when it is not:

- a subpath is not a repository: `github/codeql-action/init` and `.../analyze` live in
  `github/codeql-action`, so only the first two path segments go into the API path;
- release tags are often annotated: the ref then points at a tag object whose `object`
  is the commit, so the ref has to be dereferenced once before the comparison.

Usage:
    python Tools/check-pins.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

ACTION = re.compile(r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?)"
                    r"@(?P<sha>[0-9a-f]{40})$")
IMAGE = re.compile(r"^docker://(?P<image>[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)"
                   r"(?::(?P<tag>[A-Za-z0-9_.-]+))?@sha256:(?P<digest>[0-9a-f]{64})$")
RELEASE = re.compile(r"^v\d+(?:\.\d+)*$")
IMAGE_TAG = re.compile(r"^v?\d+(?:\.\d+)*$")
USES = re.compile(r"^\s*-?\s*uses:\s*(?P<target>\S+)\s*(?:#\s*(?P<comment>.+?))?\s*$")
IMAGE_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)


class Pin(NamedTuple):
    target: str
    comment: str
    where: str


def pins_from_workflows(directory=WORKFLOWS):
    """Every `uses:` in the workflow files, in file and line order."""
    pins = []
    for path in sorted(Path(directory).glob("*.yml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("#"):
                continue  # a commented-out example is not a pin
            match = USES.match(line)
            if match:
                pins.append(
                    Pin(
                        target=match.group("target"),
                        comment=(match.group("comment") or "").strip(),
                        where=f"{path.name}:{number}",
                    )
                )
    return pins


def repo_of(action):
    """The repository of an action reference, dropping any subpath (`.../init`)."""
    return "/".join(action.split("/")[:2])


def commit_of_ref(ref, fetch_tag_object):
    """The commit SHA a tag ref points at, dereferencing one annotated tag."""
    obj = ref["object"]
    if obj["type"] == "commit":
        return obj["sha"]
    if obj["type"] != "tag":
        raise LookupError(f"the tag points at a {obj['type']}")
    tag = fetch_tag_object(obj["sha"])
    if tag["object"]["type"] != "commit":
        raise LookupError(f"the tag object points at a {tag['object']['type']}")
    return tag["object"]["sha"]


def check_pin(pin, resolve_tag, resolve_image):
    """Return (ok, message); ok is None for a local workflow, which has nothing to pin."""
    target, comment = pin.target, pin.comment

    if target.startswith("./"):
        return None, "local workflow, nothing to pin"

    image = IMAGE.match(target)
    if image:
        if comment and not IMAGE_TAG.match(comment):
            return False, f"comment {comment!r} is not a release tag such as v1.7.12"
        reference = image.group("tag") or f"sha256:{image.group('digest')}"
        try:
            served = resolve_image(image.group("image"), reference)
        except LookupError as error:
            return False, f"cannot reach {image.group('image')}:{reference}: {error}"
        pinned = f"sha256:{image.group('digest')}"
        if served != pinned:
            return False, f"registry serves {served or 'no digest'} for {reference}, not {pinned}"
        return True, f"image digest resolves ({reference})"

    action = ACTION.match(target)
    if not action:
        return False, "not owner/repo[/subpath]@<40-hex SHA> or a docker image digest"
    if not comment:
        return False, "no release comment; expected `# vX.Y.Z` after the pin"
    if not RELEASE.match(comment):
        return False, f"comment {comment!r} is not a release tag such as v4.4.0"
    try:
        resolved = resolve_tag(action.group("action"), comment)
    except LookupError as error:
        return False, f"cannot confirm {comment}: {error}"
    if resolved != action.group("sha"):
        return False, (
            f"pinned {action.group('sha')}, but {comment} in "
            f"{repo_of(action.group('action'))} is {resolved}"
        )
    return True, f"{comment} resolves to the pinned commit"


def github_json(path, token=None):
    headers = {"User-Agent": "check-pins", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request("https://api.github.com" + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise LookupError(f"api.github.com returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise LookupError(f"cannot reach api.github.com: {error.reason}") from error


def resolve_action_tag(action, tag, token=None):
    """The commit `tag` points at in the repository that holds `action`."""
    repo = repo_of(action)
    ref = github_json(f"/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag)}", token)
    return commit_of_ref(ref, lambda sha: github_json(f"/repos/{repo}/git/tags/{sha}", token))


def resolve_image_digest(image, reference):
    """The digest the Docker Hub registry serves for `image:reference`."""
    scope = urllib.parse.quote(f"repository:{image}:pull", safe=":/")
    auth = urllib.request.Request(
        "https://auth.docker.io/token?service=registry.docker.io&scope=" + scope,
        headers={"User-Agent": "check-pins"},
    )
    try:
        with urllib.request.urlopen(auth, timeout=20) as response:
            token = json.loads(response.read().decode("utf-8"))["token"]
        request = urllib.request.Request(
            f"https://registry-1.docker.io/v2/{image}/manifests/{reference}",
            method="HEAD",
            headers={
                "User-Agent": "check-pins",
                "Authorization": f"Bearer {token}",
                "Accept": ", ".join(IMAGE_TYPES),
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.headers.get("Docker-Content-Digest", "")
    except urllib.error.HTTPError as error:
        raise LookupError(f"registry returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise LookupError(f"cannot reach the registry: {error.reason}") from error


def main(argv):
    if argv:
        print(f"usage: check-pins.py takes no arguments (got: {' '.join(argv)})", file=sys.stderr)
        return 2

    pins = pins_from_workflows()
    if not pins:
        print("FAIL: no `uses:` entries found under .github/workflows", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN") or None
    image_cache = {}

    def cached(kind, key, resolve):
        """One registry call per unique pin, failures included."""
        if key not in image_cache:
            try:
                image_cache[key] = (True, resolve())
            except LookupError as error:
                image_cache[key] = (False, error)
        ok, value = image_cache[key]
        if not ok:
            raise value
        return value

    def cached_tag(action, tag):
        return cached("tag", (action, tag), lambda: resolve_action_tag(action, tag, token))

    def cached_image(image, reference):
        return cached("image", (image, reference), lambda: resolve_image_digest(image, reference))

    checked = skipped = failures = 0
    for pin in pins:
        ok, message = check_pin(pin, cached_tag, cached_image)
        if ok is None:
            skipped += 1
            continue
        checked += 1
        label = pin.target + (f" # {pin.comment}" if pin.comment else "")
        if ok:
            print(f"ok {label} ({pin.where}): {message}")
        else:
            print(f"FAIL: {label} ({pin.where}): {message}", file=sys.stderr)
            failures += 1

    print(f"{checked} pin(s) audited, {skipped} skipped, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
