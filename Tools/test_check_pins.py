#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-pins.py, offline and both ways.

Every rule the audit applies is pinned here against fake registries, so a later change
that stops a wrong pin failing, or starts failing a sound one, fails this test instead
of only showing up on the next real audit: a matching tag passes while a pin whose tag
resolves elsewhere fails, an annotated tag is dereferenced before the comparison, a pin
without a release comment fails while a local workflow is skipped, and an image digest
passes only when the registry serves it. `Validate` runs this as `Self-test the pin
check`; the live audit needs network access and is not part of CI.

    python3 Tools/test_check_pins.py

Stdlib only.
"""

import importlib.util
import pathlib
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-pins.py"
SPEC = importlib.util.spec_from_file_location("check_pins", TOOL)
check_pins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_pins)

PINNED = "a" * 40
OTHER = "b" * 40
DIGEST = "c" * 64


def pin(target, comment="", where="probe.yml:1"):
    return check_pins.Pin(target=target, comment=comment, where=where)


def tags(mapping):
    def resolve(action, tag):
        key = (action, tag)
        if key not in mapping:
            raise LookupError(f"no tag {tag} in {check_pins.repo_of(action)}")
        return mapping[key]

    return resolve


def images(mapping):
    def resolve(image, reference):
        key = (image, reference)
        if key not in mapping:
            raise LookupError("registry returned HTTP 404")
        return mapping[key]

    return resolve


class Parsing(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)
        (self.directory / "probe.yml").write_text(
            "\n".join(
                [
                    "jobs:",
                    "  probe:",
                    "    steps:",
                    f"      - uses: actions/checkout@{PINNED} # v4.4.0",
                    "      #   uses: actions/setup-example@v1",
                    f"      - uses: docker://rhysd/actionlint@sha256:{DIGEST}",
                    "      - uses: ./.github/workflows/ci.yml",
                    "      - uses: actions/setup-node@"
                    f"{OTHER}   #   v4.4.0  ",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_finds_every_pin_and_skips_commented_out_uses(self):
        pins = check_pins.pins_from_workflows(self.directory)
        self.assertEqual(
            [p.target for p in pins],
            [
                f"actions/checkout@{PINNED}",
                f"docker://rhysd/actionlint@sha256:{DIGEST}",
                "./.github/workflows/ci.yml",
                f"actions/setup-node@{OTHER}",
            ],
        )

    def test_comments_and_locations_are_recorded(self):
        pins = check_pins.pins_from_workflows(self.directory)
        self.assertEqual(pins[0].comment, "v4.4.0")
        self.assertEqual(pins[0].where, "probe.yml:4")
        self.assertEqual(pins[1].comment, "")
        self.assertEqual(pins[3].comment, "v4.4.0")

    def test_subpath_is_not_part_of_the_repository(self):
        self.assertEqual(check_pins.repo_of("github/codeql-action/init"), "github/codeql-action")
        self.assertEqual(check_pins.repo_of("github/codeql-action/analyze"), "github/codeql-action")
        self.assertEqual(check_pins.repo_of("actions/checkout"), "actions/checkout")


class TagResolution(unittest.TestCase):
    def test_lightweight_tag_is_its_own_commit(self):
        ref = {"object": {"type": "commit", "sha": PINNED}}
        self.assertEqual(check_pins.commit_of_ref(ref, lambda sha: {}), PINNED)

    def test_annotated_tag_is_dereferenced(self):
        seen = []

        def fetch(sha):
            seen.append(sha)
            return {"object": {"type": "commit", "sha": PINNED}}

        ref = {"object": {"type": "tag", "sha": "d" * 40}}
        self.assertEqual(check_pins.commit_of_ref(ref, fetch), PINNED)
        self.assertEqual(seen, ["d" * 40])

    def test_tag_object_that_points_at_a_blob_fails(self):
        ref = {"object": {"type": "tag", "sha": "d" * 40}}
        with self.assertRaisesRegex(LookupError, "tag object points at a blob"):
            check_pins.commit_of_ref(ref, lambda sha: {"object": {"type": "blob", "sha": PINNED}})

    def test_ref_that_is_not_a_tag_or_commit_fails(self):
        ref = {"object": {"type": "tree", "sha": PINNED}}
        with self.assertRaisesRegex(LookupError, "points at a tree"):
            check_pins.commit_of_ref(ref, lambda sha: {})


class LookupShape(unittest.TestCase):
    """The API paths the live resolvers build, without a network call."""

    def test_tag_lookup_drops_the_subpath_and_the_pin(self):
        calls = []

        def fake(path, token=None):
            calls.append(path)
            return {"object": {"type": "commit", "sha": PINNED}}

        original = check_pins.github_json
        check_pins.github_json = fake
        try:
            resolved = check_pins.resolve_action_tag(f"github/codeql-action/init@{PINNED}", "v4.39.5")
        finally:
            check_pins.github_json = original
        self.assertEqual(resolved, PINNED)
        self.assertEqual(calls, ["/repos/github/codeql-action/git/ref/tags/v4.39.5"])

    def test_annotated_tag_lookup_dereferences_its_object(self):
        calls = []

        def fake(path, token=None):
            calls.append(path)
            if path.endswith("/git/ref/tags/v4.39.5"):
                return {"object": {"type": "tag", "sha": "d" * 40}}
            return {"object": {"type": "commit", "sha": PINNED}}

        original = check_pins.github_json
        check_pins.github_json = fake
        try:
            resolved = check_pins.resolve_action_tag(f"github/codeql-action/analyze@{PINNED}", "v4.39.5")
        finally:
            check_pins.github_json = original
        self.assertEqual(resolved, PINNED)
        self.assertEqual(
            calls,
            [
                "/repos/github/codeql-action/git/ref/tags/v4.39.5",
                f"/repos/github/codeql-action/git/tags/{'d' * 40}",
            ],
        )


class ActionPins(unittest.TestCase):
    def test_matching_release_passes(self):
        ok, message = check_pins.check_pin(
            pin(f"actions/checkout@{PINNED}", "v4.4.0"),
            tags({("actions/checkout", "v4.4.0"): PINNED}),
            images({}),
        )
        self.assertIs(ok, True)
        self.assertIn("resolves to the pinned commit", message)

    def test_mismatched_release_fails_with_both_shas(self):
        ok, message = check_pins.check_pin(
            pin(f"actions/checkout@{PINNED}", "v4.4.0"),
            tags({("actions/checkout", "v4.4.0"): OTHER}),
            images({}),
        )
        self.assertIs(ok, False)
        self.assertIn(PINNED, message)
        self.assertIn(OTHER, message)
        self.assertIn("v4.4.0", message)

    def test_subpath_action_is_audited_against_its_repository(self):
        ok, message = check_pins.check_pin(
            pin(f"github/codeql-action/init@{PINNED}", "v4.39.5"),
            tags({("github/codeql-action/init", "v4.39.5"): PINNED}),
            images({}),
        )
        self.assertIs(ok, True)
        self.assertIn("v4.39.5", message)

    def test_missing_release_comment_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"actions/checkout@{PINNED}"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("no release comment", message)

    def test_comment_that_is_not_a_release_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"actions/checkout@{PINNED}", "main"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("not a release tag", message)

    def test_unknown_tag_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"actions/checkout@{PINNED}", "v9.9.9"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("cannot confirm v9.9.9", message)

    def test_reference_that_is_not_pinned_fails(self):
        ok, message = check_pins.check_pin(
            pin("actions/checkout@v4", "v4.4.0"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("not owner/repo", message)

    def test_local_workflow_is_skipped(self):
        ok, message = check_pins.check_pin(
            pin("./.github/workflows/ci.yml"), tags({}), images({})
        )
        self.assertIsNone(ok)
        self.assertIn("nothing to pin", message)


class ImagePins(unittest.TestCase):
    def test_digest_that_the_registry_serves_passes(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint@sha256:{DIGEST}"),
            tags({}),
            images({("rhysd/actionlint", f"sha256:{DIGEST}"): f"sha256:{DIGEST}"}),
        )
        self.assertIs(ok, True)
        self.assertIn("digest resolves", message)

    def test_digest_the_registry_cannot_serve_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint@sha256:{DIGEST}"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("cannot reach rhysd/actionlint", message)

    def test_tag_resolves_to_the_pinned_digest(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint:1.7.12@sha256:{DIGEST}", "1.7.12"),
            tags({}),
            images({("rhysd/actionlint", "1.7.12"): f"sha256:{DIGEST}"}),
        )
        self.assertIs(ok, True)
        self.assertIn("(1.7.12)", message)

    def test_tag_that_resolves_elsewhere_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint:1.7.12@sha256:{DIGEST}", "1.7.12"),
            tags({}),
            images({("rhysd/actionlint", "1.7.12"): "sha256:" + "e" * 64}),
        )
        self.assertIs(ok, False)
        self.assertIn("not sha256:", message)

    def test_image_comment_must_be_a_version(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint@sha256:{DIGEST}", "latest"), tags({}), images({})
        )
        self.assertIs(ok, False)
        self.assertIn("not a release tag", message)

    def test_registry_returning_another_digest_fails(self):
        ok, message = check_pins.check_pin(
            pin(f"docker://rhysd/actionlint@sha256:{DIGEST}"),
            tags({}),
            images({("rhysd/actionlint", f"sha256:{DIGEST}"): "sha256:" + "e" * 64}),
        )
        self.assertIs(ok, False)
        self.assertIn("not sha256:", message)


if __name__ == "__main__":
    unittest.main()
