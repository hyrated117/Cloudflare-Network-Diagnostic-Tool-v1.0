#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-actionlint-image.py, offline and both ways.

The image check needs the network, so its one fragile half — trusting what a registry
sends — is pinned here instead: a pin is found only on a real `uses:` line and only with
a 64-hex digest, two different pins are refused while one pin repeated in two files is
not, the `linux/amd64` entry is taken from an index that also carries buildx
attestations under `unknown`, a layer whose bytes do not hash to its digest is refused,
and extraction keeps only the two programs, refusing a path that escapes the directory
and refusing two layers that disagree. `Validate` runs this as `Self-test the image
check`; the image itself is a 25 MiB download, so it stays out of CI.

    python3 Tools/test_check_actionlint_image.py

Stdlib only.
"""

import hashlib
import importlib.util
import io
import pathlib
import stat
import tarfile
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-actionlint-image.py"
SPEC = importlib.util.spec_from_file_location("check_actionlint_image", TOOL)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

DIGEST = "d" * 64


def layer(files, mode=0o755):
    """One gzipped layer tarball holding the given name → bytes entries."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = mode
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class Parsing(unittest.TestCase):
    def test_finds_the_pin_and_its_digest(self):
        found = check.docker_references(
            "      - uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n"
        )
        self.assertEqual(found, [("rhysd/actionlint", "sha256:" + DIGEST)])

    def test_commented_out_pin_is_ignored(self):
        found = check.docker_references(
            "#      - uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n"
            "      - uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n"
        )
        self.assertEqual(found, [("rhysd/actionlint", "sha256:" + DIGEST)])

    def test_tag_only_reference_is_refused(self):
        with self.assertRaisesRegex(LookupError, "is not docker://image@sha256"):
            check.docker_references("      - uses: docker://rhysd/actionlint:1.7.12\n")

    def test_short_digest_is_refused(self):
        with self.assertRaisesRegex(LookupError, "is not docker://image@sha256"):
            check.docker_references("      - uses: docker://rhysd/actionlint@sha256:abc\n")

    def test_action_pins_are_not_mistaken_for_images(self):
        self.assertEqual(
            check.docker_references("      - uses: actions/checkout@" + "a" * 40 + "\n"),
            [],
        )


class PinnedImage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)

    def test_one_pin_is_returned(self):
        (self.directory / "ci.yml").write_text(
            "- uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n", encoding="utf-8"
        )
        self.assertEqual(
            check.pinned_image(self.directory), ("rhysd/actionlint", "sha256:" + DIGEST)
        )

    def test_the_same_pin_in_two_files_is_one_pin(self):
        for name in ("ci.yml", "extra.yaml"):
            (self.directory / name).write_text(
                "- uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n",
                encoding="utf-8",
            )
        self.assertEqual(
            check.pinned_image(self.directory), ("rhysd/actionlint", "sha256:" + DIGEST)
        )

    def test_no_pin_fails(self):
        (self.directory / "ci.yml").write_text("- uses: actions/checkout@" + "a" * 40 + "\n")
        with self.assertRaisesRegex(LookupError, "no docker://"):
            check.pinned_image(self.directory)

    def test_two_different_pins_fail_and_name_both(self):
        (self.directory / "ci.yml").write_text(
            "- uses: docker://rhysd/actionlint@sha256:" + DIGEST + "\n"
            "- uses: docker://example/tool@sha256:" + "e" * 64 + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(LookupError, "more than one image"):
            check.pinned_image(self.directory)


class Platform(unittest.TestCase):
    def test_amd64_manifest_is_selected_and_attestations_skipped(self):
        index = {
            "manifests": [
                {"platform": {"os": "unknown", "architecture": "unknown"}, "digest": "sha256:aa"},
                {"platform": {"os": "linux", "architecture": "arm64"}, "digest": "sha256:bb"},
                {"platform": {"os": "linux", "architecture": "amd64"}, "digest": "sha256:cc"},
            ]
        }
        self.assertEqual(check.select_platform(index), {"platform": {"os": "linux", "architecture": "amd64"}, "digest": "sha256:cc"})

    def test_missing_platform_fails(self):
        with self.assertRaisesRegex(LookupError, "no linux/amd64 manifest"):
            check.select_platform({"manifests": [{"platform": {"os": "linux", "architecture": "arm64"}}]})


class Digests(unittest.TestCase):
    def test_matching_digest_is_returned(self):
        data = b"layer bytes"
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        self.assertIs(check.verify_digest(data, digest), data)

    def test_mismatched_digest_fails(self):
        with self.assertRaisesRegex(LookupError, "hashes to"):
            check.verify_digest(b"layer bytes", "sha256:" + "f" * 64)


class Extraction(unittest.TestCase):
    def test_both_programs_come_out_of_their_layers(self):
        layers = [
            layer({"usr/local/bin/actionlint": b"actionlint"}),
            layer({"usr/local/bin/shellcheck": b"shellcheck"}),
            layer({"etc/alpine-release": b"3.22"}),
        ]
        self.assertEqual(
            check.extract_programs(layers),
            {"actionlint": b"actionlint", "shellcheck": b"shellcheck"},
        )

    def test_other_files_are_ignored(self):
        found = check.extract_programs(
            [
                layer(
                    {
                        "usr/local/bin/actionlint.bak": b"backup",
                        "usr/local/bin/actionlint": b"actionlint",
                    }
                )
            ],
            programs=("actionlint",),
        )
        self.assertEqual(found, {"actionlint": b"actionlint"})

    def test_path_that_escapes_the_directory_is_refused(self):
        with self.assertRaisesRegex(LookupError, "refusing the layer's path"):
            check.extract_programs([layer({"../../bin/actionlint": b"x"})])

    def test_two_layers_that_disagree_are_refused(self):
        with self.assertRaisesRegex(LookupError, "two layers disagree"):
            check.extract_programs(
                [layer({"a/actionlint": b"one"}), layer({"b/actionlint": b"two"})]
            )

    def test_missing_program_fails(self):
        with self.assertRaisesRegex(LookupError, "contains no shellcheck"):
            check.extract_programs([layer({"usr/local/bin/actionlint": b"x"})])


class Versions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)

    def script(self, name, body):
        path = self.directory / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_actionlint_version_is_its_first_line(self):
        binary = self.script("actionlint", 'echo 1.7.12; echo "built with go1.26.1"')
        self.assertEqual(check.version_of(binary, {"PATH": "/usr/bin:/bin"}), "1.7.12")

    def test_shellcheck_version_is_the_version_line(self):
        binary = self.script("shellcheck", 'echo "ShellCheck - shell script analysis tool"; echo "version: 0.11.0"')
        self.assertEqual(check.shellcheck_version(binary, {"PATH": "/usr/bin:/bin"}), "0.11.0")

    def test_unknown_shellcheck_is_named(self):
        binary = self.script("shellcheck", "exit 0")
        self.assertEqual(check.shellcheck_version(binary, {"PATH": "/usr/bin:/bin"}), "unknown")


if __name__ == "__main__":
    unittest.main()
