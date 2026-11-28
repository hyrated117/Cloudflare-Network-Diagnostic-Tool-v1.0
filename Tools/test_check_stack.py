#!/usr/bin/env python3
"""Self-test for Tools/check-stack.py, against throwaway repositories.

The guard is the only check that reads a chain of branches, so its rules are pinned here
where the branches are cheap: a clean two-commit stack rehearses with no problems and
ends on the last head's tree; a branch based on the wrong tip is refused because its
diff would carry another pull request's commits; a base that moved with unrelated work
is allowed but reported; a base that moved with conflicting work fails on the conflict;
a missing branch is an error rather than a traceback; and the run leaves every ref where
it found it. `Validate` runs this as `Self-test the stack check`; the guard itself needs
the real stack's refs, so it is a pre-flight rather than a CI step.

    python3 Tools/test_check_stack.py

Stdlib plus git, which `Validate` already uses for `bash -n`.
"""

import contextlib
import importlib.util
import io
import pathlib
import subprocess
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-stack.py"
SPEC = importlib.util.spec_from_file_location("check_stack", TOOL)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def sh(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def new_repo(path):
    repo = pathlib.Path(path) / "repo"
    repo.mkdir()
    sh(repo, "init", "-q", "-b", "main")
    sh(repo, "config", "user.name", "test")
    sh(repo, "config", "user.email", "test@example.invalid")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    sh(repo, "add", "base.txt")
    sh(repo, "commit", "-q", "-m", "base")
    return repo


def write_commit(repo, name, content, message=None):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    sh(repo, "add", name)
    sh(repo, "commit", "-q", "-m", message or f"add {name}")


def branch(repo, name):
    sh(repo, "checkout", "-q", "-b", name)


def checkout(repo, name):
    sh(repo, "checkout", "-q", name)


def capture_run(repo, branches):
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = check.run(branches, "origin", repo)
    return code, output.getvalue()


class Rehearsal(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)

    def test_a_clean_stack_rehearses_and_ends_on_the_last_tree(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        branch(repo, "b2")
        write_commit(repo, "b2.txt", "two\n")
        problems, results, final_tree, last_tree = check.rehearsal(
            repo, ["main", "b1", "b2"]
        )
        self.assertEqual(problems, [])
        self.assertEqual([step["clean"] for step in results], [True, True])
        self.assertEqual([step["ancestor"] for step in results], [True, True])
        self.assertEqual(final_tree, last_tree)

    def test_a_branch_based_on_the_wrong_tip_is_refused(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        checkout(repo, "main")
        branch(repo, "b2")
        write_commit(repo, "b2.txt", "two\n")
        problems, results, _, _ = check.rehearsal(
            repo, ["main", "b1", "b2"]
        )
        self.assertTrue(
            any("not based on b1" in problem for problem in problems), problems
        )
        self.assertFalse(results[1]["ancestor"])
        self.assertTrue(
            results[1]["clean"], "the branches still merge; only the base is wrong"
        )

    def test_a_moved_first_base_is_allowed_when_the_merge_is_clean(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        checkout(repo, "main")
        write_commit(repo, "unrelated.txt", "other\n")
        problems, results, final_tree, last_tree = check.rehearsal(repo, ["main", "b1"])
        self.assertEqual(problems, [])
        self.assertFalse(results[0]["ancestor"])
        self.assertTrue(results[0]["clean"])
        self.assertIn("not on this branch", results[0]["note"])
        self.assertEqual((results[0]["ahead"], results[0]["behind"]), (1, 1))
        self.assertNotEqual(
            final_tree, last_tree, "main's unrelated file is in the merged tree"
        )

    def test_a_moved_first_base_with_a_conflict_fails(self):
        repo = new_repo(self.directory)
        write_commit(repo, "line.txt", "one\n")
        branch(repo, "b1")
        write_commit(repo, "line.txt", "two\n")
        checkout(repo, "main")
        write_commit(repo, "line.txt", "three\n")
        problems, results, _, _ = check.rehearsal(repo, ["main", "b1"])
        self.assertTrue(any("conflicts" in problem for problem in problems), problems)
        self.assertFalse(results[0]["clean"])
        self.assertTrue(results[0]["conflicts"])

    def test_a_missing_branch_is_an_error_not_a_traceback(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        with self.assertRaisesRegex(check.StackError, "no-such-branch"):
            check.rehearsal(repo, ["main", "b1", "no-such-branch"])

    def test_no_branches_left_is_reported_as_retired(self):
        repo = new_repo(self.directory)
        with self.assertRaisesRegex(check.NoStack, "none of the stack branches exist"):
            check.rehearsal(repo, ["main", "b1", "b2"])
        code, output = capture_run(repo, ["main", "b1", "b2"])
        self.assertEqual(code, 0, output)
        self.assertIn("nothing to rehearse", output)
        self.assertIn("can be retired", output)

    def test_merged_branches_are_reported_as_retired(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        checkout(repo, "main")
        sh(repo, "merge", "-q", "--no-ff", "-m", "merge b1", "b1")
        with self.assertRaisesRegex(check.NoStack, "already merged"):
            check.rehearsal(repo, ["main", "b1"])
        code, output = capture_run(repo, ["main", "b1"])
        self.assertEqual(code, 0, output)
        self.assertIn("already merged", output)

    def test_a_partially_missing_stack_is_still_an_error(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        with self.assertRaisesRegex(check.StackError, r"branch\(s\) missing: b2"):
            check.rehearsal(repo, ["main", "b1", "b2"])

    def test_the_diff_summary_counts_the_branch_alone(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\ntwo\n")
        problems, results, _, _ = check.rehearsal(repo, ["main", "b1"])
        self.assertEqual(problems, [])
        self.assertEqual(results[0]["commits"], 1)
        self.assertEqual(results[0]["files"], 1)
        self.assertEqual((results[0]["added"], results[0]["removed"]), (2, 0))


class Run(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = pathlib.Path(self.temporary.name)

    def test_run_passes_a_clean_stack(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        code, output = capture_run(repo, ["main", "b1"])
        self.assertEqual(code, 0, output)
        self.assertIn("1 merge(s) into main are conflict-free", output)
        self.assertIn("matches b1's tree", output)

    def test_run_fails_and_names_the_problem(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        checkout(repo, "main")
        branch(repo, "b2")
        write_commit(repo, "b2.txt", "two\n")
        code, output = capture_run(repo, ["main", "b1", "b2"])
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL", output)
        self.assertIn("not based on b1", output)

    def test_rehearsal_leaves_every_ref_where_it_was(self):
        repo = new_repo(self.directory)
        branch(repo, "b1")
        write_commit(repo, "b1.txt", "one\n")
        before = sh(repo, "for-each-ref", "--format=%(refname) %(objectname)")
        check.rehearsal(repo, ["main", "b1"])
        after = sh(repo, "for-each-ref", "--format=%(refname) %(objectname)")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
