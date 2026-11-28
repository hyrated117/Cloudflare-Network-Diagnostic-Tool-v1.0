#!/usr/bin/env python3
"""Self-test for Tools/check-version.py.

The checker is what keeps a version bump to one edit: it fails when `VERSION` is not
MAJOR.MINOR.PATCH, when any of the ten sites drifts from it, and when the newest
CHANGELOG section or its release notes disagree. Each of those failures is pinned here
against a throwaway copy of the tree, so a later simplification that turns a failure
into a warning, or compares the wrong CHANGELOG section, fails this test.

    python3 Tools/test_check_version.py

Stdlib only. It imports `version_sites`, which is stdlib too.
"""

import contextlib
import importlib.util
import io
import pathlib
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import version_sites as sites  # noqa: E402

SPEC = importlib.util.spec_from_file_location("check_version", TOOLS / "check-version.py")
check_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_version)

COPIED = (*sites.STRING_SITES, *sites.JSON_SITES, "VERSION", "CHANGELOG.md")


class CheckVersion(unittest.TestCase):
    def setUp(self):
        self.real_root = sites.REPO_ROOT
        self.real_version_file = sites.VERSION_FILE
        self.real_changelog = check_version.CHANGELOG
        self.temp = pathlib.Path(tempfile.mkdtemp(prefix="check-version-"))
        self.root = self.temp / "repo"
        self.root.mkdir()
        for name in COPIED:
            self.copy(name)
        shutil.copytree(self.real_root / "release", self.root / "release")
        sites.REPO_ROOT = self.root
        sites.VERSION_FILE = self.root / "VERSION"
        check_version.CHANGELOG = self.root / "CHANGELOG.md"
        self.version = (self.root / "VERSION").read_text(encoding="utf-8").strip()

    def tearDown(self):
        sites.REPO_ROOT = self.real_root
        sites.VERSION_FILE = self.real_version_file
        check_version.CHANGELOG = self.real_changelog
        shutil.rmtree(self.temp)

    def copy(self, name):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.real_root / name, target)

    def edit(self, name, old, new):
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def check(self, argv=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_version.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_consistent_tree_passes(self):
        code, out, err = self.check()
        self.assertEqual(code, 0, err)
        self.assertIn(f"CHANGELOG.md [{self.version}] agree", out)

    def test_one_drifted_site_fails(self):
        self.edit("server/index.js", self.version, "9.9.9")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn(f"server/index.js: 9.9.9 but VERSION says {self.version}", err)

    def test_two_sites_that_disagree_fail(self):
        self.edit("server/index.js", self.version, "9.9.9")
        self.edit("installers/cli.js", self.version, "9.9.8")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("version strings disagree", err)

    def test_non_semver_version_fails(self):
        (self.root / "VERSION").write_text("1.0\n", encoding="utf-8")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("MAJOR.MINOR.PATCH", err)

    def test_missing_version_file_fails(self):
        (self.root / "VERSION").unlink()
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("VERSION is missing", err)

    def test_newest_changelog_section_must_match(self):
        path = self.root / "CHANGELOG.md"
        text = path.read_text(encoding="utf-8")
        path.write_text("## [9.9.9] - 2026-01-01\n\n" + text, encoding="utf-8")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("CHANGELOG.md's newest release is 9.9.9", err)

    def test_newest_release_notes_must_exist(self):
        (self.root / "release" / f"v{self.version}" / "release-notes.md").unlink()
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("is missing (the release body", err)

    def test_release_notes_title_must_name_the_version(self):
        path = self.root / "release" / f"v{self.version}" / "release-notes.md"
        path.write_text("# Release notes\n", encoding="utf-8")
        code, _, err = self.check()
        self.assertEqual(code, 1)
        self.assertIn("title does not name", err)

    def test_an_older_changelog_section_is_ignored(self):
        path = self.root / "CHANGELOG.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\n## [0.9.0] - 2025-01-01\n", encoding="utf-8")
        code, _, err = self.check()
        self.assertEqual(code, 0, err)

    def test_arguments_are_rejected(self):
        code, _, err = self.check(["--strict"])
        self.assertEqual(code, 2)
        self.assertIn("takes no arguments", err)


if __name__ == "__main__":
    unittest.main()
