#!/usr/bin/env python3
"""Self-test for Tools/stamp-version.py.

The stamper is what makes a version bump one edit and one command instead of twelve, so
the parts a bump depends on are pinned here against a throwaway copy of the tree: a
clean tree changes nothing under `--dry-run`, a bump rewrites every site and reads back
consistent, a second run is a no-op, and a bad `VERSION` or a site with the wrong number
of literals fails before anything is written.

    python3 Tools/test_stamp_version.py

Stdlib only. It imports `version_sites`, which is stdlib too.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import version_sites as sites  # noqa: E402

SPEC = importlib.util.spec_from_file_location("stamp_version", TOOLS / "stamp-version.py")
stamp_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stamp_version)

COPIED = (*sites.STRING_SITES, *sites.JSON_SITES, "VERSION")
SITES = len(COPIED) - 1


class StampVersion(unittest.TestCase):
    def setUp(self):
        self.real_root = sites.REPO_ROOT
        self.real_version_file = sites.VERSION_FILE
        self.temp = pathlib.Path(tempfile.mkdtemp(prefix="stamp-version-"))
        self.root = self.temp / "repo"
        self.root.mkdir()
        for name in COPIED:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.real_root / name, target)
        sites.REPO_ROOT = self.root
        sites.VERSION_FILE = self.root / "VERSION"
        self.version = (self.root / "VERSION").read_text(encoding="utf-8").strip()

    def tearDown(self):
        sites.REPO_ROOT = self.real_root
        sites.VERSION_FILE = self.real_version_file
        shutil.rmtree(self.temp)

    def stamp(self, argv=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = stamp_version.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def snapshot(self):
        return {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in COPIED
        }

    def test_clean_tree_needs_no_write(self):
        before = self.snapshot()
        code, out, err = self.stamp(["--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertIn(f"0 of {SITES} files would change", out)
        self.assertEqual(self.snapshot(), before)

    def test_bump_rewrites_every_site_and_reads_back_consistent(self):
        (self.root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        code, out, err = self.stamp()
        self.assertEqual(code, 0, err)
        self.assertIn("ok stamped", out)
        found, problems = sites.collect()
        self.assertEqual(problems, [])
        self.assertEqual({value for values in found.values() for value in values}, {"9.9.9"})

    def test_lockfile_versions_are_stamped_at_both_paths(self):
        (self.root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        self.assertEqual(self.stamp()[0], 0)
        for name in ("server/package-lock.json", "installers/package-lock.json"):
            data = json.loads((self.root / name).read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "9.9.9", name)
            self.assertEqual(data["packages"][""]["version"], "9.9.9", name)

    def test_second_run_is_a_no_op(self):
        (self.root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        self.assertEqual(self.stamp()[0], 0)
        before = self.snapshot()
        code, out, err = self.stamp(["--dry-run"])
        self.assertEqual(code, 0, err)
        self.assertIn(f"0 of {SITES} files would change", out)
        self.assertEqual(self.snapshot(), before)

    def test_bad_version_writes_nothing(self):
        (self.root / "VERSION").write_text("1.0\n", encoding="utf-8")
        before = self.snapshot()
        code, _, err = self.stamp()
        self.assertEqual(code, 1)
        self.assertIn("nothing written", err)
        self.assertEqual(self.snapshot(), before)

    def test_wrong_literal_count_writes_nothing(self):
        (self.root / "server/index.js").write_text("// no version string here\n", encoding="utf-8")
        before = self.snapshot()
        code, _, err = self.stamp()
        self.assertEqual(code, 1)
        self.assertIn("nothing written", err)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_argument_is_rejected(self):
        code, _, err = self.stamp(["--write"])
        self.assertEqual(code, 2)
        self.assertIn("usage: stamp-version.py", err)

    def test_replace_version_keeps_the_surrounding_text(self):
        text = '{"version": "1.0.0", "nested": {"version": "1.0.0"}}'
        new_text, count = sites.replace_version(text, r'"version":\s*"([^"]+)"', "2.0.0")
        self.assertEqual(count, 2)
        self.assertEqual(new_text, '{"version": "2.0.0", "nested": {"version": "2.0.0"}}')


if __name__ == "__main__":
    unittest.main()
