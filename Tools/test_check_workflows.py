#!/usr/bin/env python3
"""Self-test for the continuation rule in Tools/check-workflows.py.

That rule must stay quiet about a continuation character that is literal text - in a
here-document body, a here-string, a quoted string or a comment - and must still fail a
real break. An earlier version of it reported a here-doc body and a trailing comment,
so both halves are pinned here: a change that widens the rule back over literals, or
narrows it until it misses a real break, fails this test.

    python3 Tools/test_check_workflows.py

Stdlib only, and the tool imports PyYAML inside main(), so this runs without it.
"""

import importlib.util
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-workflows.py"
SPEC = importlib.util.spec_from_file_location("check_workflows", TOOL)
check_workflows = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_workflows)


def workflow(run, shell=None, runs_on="ubuntu-latest"):
    step = {"name": "probe", "run": run}
    if shell:
        step["shell"] = shell
    return {"jobs": {"probe": {"runs-on": runs_on, "steps": [step]}}}


class ContinuationRule(unittest.TestCase):
    def setUp(self):
        check_workflows.problems.clear()

    def failures(self, run, shell=None, runs_on="ubuntu-latest"):
        check_workflows.check_continuations("probe.yml", workflow(run, shell, runs_on))
        return check_workflows.problems

    def assert_quiet(self, run, **kwargs):
        self.assertEqual(self.failures(run, **kwargs), [])

    def test_heredoc_body_is_literal(self):
        self.assert_quiet("cat > notes.txt <<'EOF'\nC:\\Program Files\\ \nEOF\necho done")

    def test_trailing_comment_is_literal(self):
        self.assert_quiet("echo hi  # C:\\Users\\ \necho done")

    def test_multiline_quoted_string_is_literal(self):
        self.assert_quiet('echo "line one\ntwo \\ \nthree"')

    def test_pwsh_here_string_is_literal(self):
        self.assert_quiet(
            "Set-Content -Path out.txt -Value @'\nkeep this ` \n'@",
            shell="pwsh",
            runs_on="windows-latest",
        )

    def test_bash_break_is_reported(self):
        problems = self.failures("echo one \\ \n  two")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 1", problems[0])
        self.assertIn("bash", problems[0])

    def test_pwsh_break_is_reported(self):
        problems = self.failures("Write-Host one ` \n  two", shell="pwsh", runs_on="windows-latest")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 1", problems[0])
        self.assertIn("pwsh", problems[0])

    def test_break_after_a_heredoc_is_reported(self):
        problems = self.failures("cat > f.txt <<EOF\nbody\nEOF\necho one \\ \n  two")
        self.assertEqual(len(problems), 1)
        self.assertIn("line 4", problems[0])

    def test_other_shell_has_no_continuation_to_lose(self):
        self.assert_quiet("echo one \\ \n  two", shell="python {0}")


if __name__ == "__main__":
    unittest.main()
