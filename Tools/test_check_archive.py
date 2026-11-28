#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-archive.py.

The archive check is the release gate: nothing is published unless it reports
`release archive: shippable`. Each rule it asserts is pinned here both ways, against small archives built in a
temporary directory: a pack missing a required file, carrying
build junk, stamped with a half-bumped version, or with a wrong or absent checksum must
fail, and a sound pack must pass. The gate's exit status is exercised through the CLI
too, so the order in which the rules run stays part of what is tested.

    python3 Tools/test_check_archive.py

Stdlib only.
"""

import contextlib
import hashlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-archive.py"
SPEC = importlib.util.spec_from_file_location("check_archive", TOOL)
check_archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_archive)

VERSION = "1.2.3"
PACK = "mcp-installer-pack.tar.gz"
SERVER_JS = "const info = {};\nthis.version = '1.2.3';\n"
UNIFIED_SH = '#!/usr/bin/env bash\nVERSION="1.2.3"\n'


def pack_files(version=VERSION, server=SERVER_JS, unified=UNIFIED_SH):
    """The files a sound pack carries, with any of the stamped ones replaceable."""
    return {
        "LICENSE": "MIT\n",
        "README.md": "# Pack\n",
        "VERSION": version + "\n",
        "docs/README.md": "# Docs\n",
        "server/index.py": "print('server')\n",
        "server/index.js": server,
        "installers/install-mcp-server.sh": "#!/bin/sh\n",
        "installers/install-mcp-unified.sh": unified,
        "installers/install-mcp-server.ps1": "Write-Output 'server'\n",
        "installers/install-mcp-unified.ps1": "Write-Output 'unified'\n",
    }


class ArchiveCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)

    def build(self, files, name=PACK):
        path = self.root / name
        with tarfile.open(path, "w:gz") as tar:
            for member, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return path

    def capture(self, call, *args):
        """Run a rule with its FAIL lines captured, and return (result, out, err)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = call(*args)
        return result, out.getvalue(), err.getvalue()

    def assert_rule(self, call, args, expected, message=None):
        result, out, err = self.capture(call, *args)
        self.assertIs(result, expected, err)
        if message is not None:
            self.assertIn(message, err if expected is False else out)
        return out, err

    def sums(self, archive, digest=None, name=None):
        digest = digest or hashlib.sha256(archive.read_bytes()).hexdigest()
        sums_path = self.root / "SHA256SUMS"
        sums_path.write_text(f"{digest}  {name or archive.name}\n", encoding="utf-8")
        return sums_path

    def run_tool(self, *arguments):
        completed = subprocess.run(
            [sys.executable, str(TOOL), *map(str, arguments)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return completed


class ChecksumRule(ArchiveCase):
    def test_missing_sums_is_allowed_when_optional(self):
        archive = self.build(pack_files())
        self.assert_rule(
            check_archive.checksum, (archive, self.root / "SHA256SUMS", False), True
        )

    def test_missing_sums_fails_when_required(self):
        archive = self.build(pack_files())
        self.assert_rule(
            check_archive.checksum,
            (archive, self.root / "SHA256SUMS", True),
            False,
            "no SHA256SUMS",
        )

    def test_matching_sums_passes(self):
        archive = self.build(pack_files())
        out, _ = self.assert_rule(
            check_archive.checksum, (archive, self.sums(archive), False), True
        )
        self.assertIn("checksum: matches SHA256SUMS", out)

    def test_binary_mode_star_prefix_passes(self):
        archive = self.build(pack_files())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        sums = self.sums(archive)
        sums.write_text(f"{digest} *{archive.name}\n", encoding="utf-8")
        self.assert_rule(check_archive.checksum, (archive, sums, True), True)

    def test_sums_for_another_file_fails(self):
        archive = self.build(pack_files())
        self.assert_rule(
            check_archive.checksum,
            (archive, self.sums(archive, name="other.tar.gz"), True),
            False,
            "SHA256SUMS covers other.tar.gz",
        )

    def test_wrong_digest_fails(self):
        archive = self.build(pack_files())
        self.assert_rule(
            check_archive.checksum,
            (archive, self.sums(archive, digest="0" * 64), True),
            False,
            "checksum mismatch",
        )

    def test_malformed_sums_fails(self):
        archive = self.build(pack_files())
        sums = self.root / "SHA256SUMS"
        sums.write_text("abc\n", encoding="utf-8")
        self.assert_rule(
            check_archive.checksum, (archive, sums, True), False, "malformed"
        )

    def test_empty_sums_fails(self):
        archive = self.build(pack_files())
        sums = self.root / "SHA256SUMS"
        sums.write_text("", encoding="utf-8")
        self.assert_rule(
            check_archive.checksum, (archive, sums, True), False, "malformed"
        )


class ContentsRule(ArchiveCase):
    def test_complete_archive_passes(self):
        archive = self.build(pack_files())
        out, _ = self.assert_rule(check_archive.contents, (archive,), True)
        self.assertIn("required files present, no build junk", out)

    def test_missing_required_file_fails(self):
        files = pack_files()
        files.pop("docs/README.md")
        archive = self.build(files)
        self.assert_rule(
            check_archive.contents, (archive,), False, "archive is missing docs/README.md"
        )

    def test_every_required_file_is_required(self):
        for required in check_archive.REQUIRED:
            with self.subTest(required=required):
                files = pack_files()
                files.pop(required)
                archive = self.build(files)
                _, err = self.assert_rule(check_archive.contents, (archive,), False)
                self.assertIn(f"archive is missing {required}", err)

    def test_every_junk_marker_fails(self):
        for marker in check_archive.JUNK:
            with self.subTest(marker=marker):
                files = pack_files()
                files[f"installers/{marker}rubbish"] = "x"
                archive = self.build(files)
                _, err = self.assert_rule(check_archive.contents, (archive,), False)
                self.assertIn("archive carries generated files", err)

    def test_junk_names_are_shown(self):
        files = pack_files()
        files["server/__pycache__/index.cpython-312.pyc"] = "x"
        archive = self.build(files)
        _, err = self.assert_rule(check_archive.contents, (archive,), False)
        self.assertIn("__pycache__", err)

    def test_missing_file_and_junk_are_both_reported(self):
        files = pack_files()
        files.pop("VERSION")
        files["installers/node_modules/x/y.js"] = "x"
        archive = self.build(files)
        _, err = self.assert_rule(check_archive.contents, (archive,), False)
        self.assertIn("archive is missing VERSION", err)
        self.assertIn("archive carries generated files", err)


class VersionRule(ArchiveCase):
    def test_matching_version_passes(self):
        archive = self.build(pack_files())
        out, _ = self.assert_rule(check_archive.version, (archive,), True)
        self.assertIn("version: VERSION 1.2.3", out)

    def test_release_prefix_matches(self):
        archive = self.build(pack_files())
        self.assert_rule(check_archive.version, (archive, "v1.2.3"), True)

    def test_release_without_prefix_matches(self):
        archive = self.build(pack_files())
        self.assert_rule(check_archive.version, (archive, "1.2.3"), True)

    def test_release_mismatch_fails(self):
        archive = self.build(pack_files())
        self.assert_rule(
            check_archive.version, (archive, "v2.0.0"), False, "but the release is 2.0.0"
        )

    def test_non_semver_version_fails(self):
        for bad in ("1.2", "v1.2.3", "1.2.3.4", "1.2.3 1.2.4", ""):
            with self.subTest(version=bad):
                archive = self.build(pack_files(version=bad))
                self.assert_rule(
                    check_archive.version,
                    (archive,),
                    False,
                    "not MAJOR.MINOR.PATCH",
                )

    def test_missing_version_file_fails(self):
        files = pack_files()
        files.pop("VERSION")
        archive = self.build(files)
        self.assert_rule(check_archive.version, (archive,), False, "VERSION is not in the archive")

    def test_server_version_drift_fails(self):
        archive = self.build(pack_files(server="this.version = '9.9.9';\n"))
        self.assert_rule(
            check_archive.version,
            (archive,),
            False,
            "but server/index.js says 9.9.9",
        )

    def test_installer_version_drift_fails(self):
        archive = self.build(pack_files(unified='VERSION="9.9.9"\n'))
        self.assert_rule(
            check_archive.version,
            (archive,),
            False,
            "but installers/install-mcp-unified.sh says 9.9.9",
        )

    def test_missing_version_string_fails(self):
        archive = self.build(pack_files(server="// no version here\n"))
        self.assert_rule(
            check_archive.version, (archive,), False, "has 0 version string(s), expected 1"
        )

    def test_duplicate_version_string_fails(self):
        archive = self.build(
            pack_files(server="this.version = '1.2.3';\nthis.version = '1.2.3';\n")
        )
        self.assert_rule(
            check_archive.version, (archive,), False, "has 2 version string(s), expected 1"
        )

    def test_missing_versioned_site_fails(self):
        files = pack_files()
        files.pop("server/index.js")
        archive = self.build(files)
        self.assert_rule(
            check_archive.version, (archive,), False, "server/index.js is not in the archive"
        )


class Extraction(ArchiveCase):
    def test_extract_writes_the_tree(self):
        archive = self.build(pack_files())
        destination = self.root / "tree"
        out, _ = self.assert_rule(check_archive.extract, (archive, destination), None)
        self.assertIn(f"extracted to {destination}", out)
        self.assertEqual((destination / "VERSION").read_text(encoding="utf-8").strip(), VERSION)
        self.assertTrue((destination / "server" / "index.js").is_file())


class Gate(ArchiveCase):
    """The CLI's exit status, so the order the rules run in stays tested too."""

    def test_missing_archive_fails(self):
        completed = self.run_tool(self.root / "absent.tar.gz")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("archive not found", completed.stderr)

    def test_sound_archive_passes(self):
        archive = self.build(pack_files())
        completed = self.run_tool(archive)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("release archive: shippable", completed.stdout)

    def test_checksum_required_but_absent_fails(self):
        archive = self.build(pack_files())
        completed = self.run_tool(archive, "--expect-checksum")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("no SHA256SUMS", completed.stderr)

    def test_expected_checksum_passes(self):
        archive = self.build(pack_files())
        self.sums(archive)
        completed = self.run_tool(archive, "--expect-checksum")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("checksum: matches SHA256SUMS", completed.stdout)

    def test_junk_archive_fails_before_the_version_check(self):
        files = pack_files()
        files[".git/config"] = "x"
        archive = self.build(files)
        completed = self.run_tool(archive, "--expect-version", "v9.9.9")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("generated files", completed.stderr)
        self.assertNotIn("but the release is", completed.stderr)

    def test_wrong_release_fails(self):
        archive = self.build(pack_files())
        completed = self.run_tool(archive, "--expect-version", "v2.0.0")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("but the release is 2.0.0", completed.stderr)

    def test_extract_to_writes_the_pack(self):
        archive = self.build(pack_files())
        destination = self.root / "out"
        completed = self.run_tool(archive, "--extract-to", destination)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue((destination / "VERSION").is_file())


if __name__ == "__main__":
    unittest.main()
