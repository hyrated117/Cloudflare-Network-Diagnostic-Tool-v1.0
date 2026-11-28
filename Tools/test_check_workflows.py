#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-workflows.py.

Each rule is pinned against a failure GitHub reports as nothing: a trigger that skips a
stacked pull request, a job that inherits the six-hour default, a `uses:` that can move
under a commit that already passed, and a continuation character followed by
whitespace. Both halves are asserted for every rule - a break that must fail and a
sound workflow that must stay quiet - so a change that stops a rule firing, or makes it
fire on a workflow GitHub would run fine, fails this test.

    python3 Tools/test_check_workflows.py

Stdlib only, and the tool imports PyYAML inside main(), so this runs without it.
"""

import contextlib
import importlib.util
import io
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-workflows.py"
SPEC = importlib.util.spec_from_file_location("check_workflows", TOOL)
check_workflows = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_workflows)

SHA = "a" * 40
DIGEST = "b" * 64


def quiet(call, *args):
    """Run a rule without its `ok ...` line landing in the test output."""
    with contextlib.redirect_stdout(io.StringIO()):
        call(*args)


def document(run, shell=None, runs_on="ubuntu-latest"):
    step = {"name": "probe", "run": run}
    if shell:
        step["shell"] = shell
    return {"jobs": {"probe": {"runs-on": runs_on, "steps": [step]}}}


class ContinuationRule(unittest.TestCase):
    def setUp(self):
        check_workflows.problems.clear()

    def failures(self, run, shell=None, runs_on="ubuntu-latest"):
        quiet(check_workflows.check_continuations, "probe.yml", document(run, shell, runs_on))
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


class TriggerRule(unittest.TestCase):
    def setUp(self):
        check_workflows.problems.clear()

    def failures(self, data):
        quiet(check_workflows.check_triggers, "probe.yml", data)
        return check_workflows.problems

    def workflow(self, spec):
        return {"on": spec, "jobs": {"probe": {"runs-on": "ubuntu-latest"}}}

    def assert_sound(self, spec):
        self.assertEqual(self.failures(self.workflow(spec)), [])

    def assert_fails(self, spec, expected):
        problems = self.failures(self.workflow(spec))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(expected, problems[0])

    def test_empty_pull_request_passes(self):
        self.assert_sound({"pull_request": None})

    def test_empty_pull_request_mapping_passes(self):
        self.assert_sound({"pull_request": {}})

    def test_event_list_passes(self):
        self.assert_sound(["push", "pull_request"])

    def test_yaml_boolean_on_key_is_read(self):
        # PyYAML resolves the bare key `on` as the boolean True under YAML 1.1.
        data = {True: {"pull_request": None}, "jobs": {"probe": {"runs-on": "ubuntu-latest"}}}
        self.assertEqual(self.failures(data), [])

    def test_branches_filter_fails(self):
        self.assert_fails({"pull_request": {"branches": ["main"]}}, "branches")

    def test_branches_ignore_filter_fails(self):
        self.assert_fails({"pull_request": {"branches-ignore": ["main"]}}, "branches-ignore")

    def test_missing_pull_request_fails(self):
        self.assert_fails({"push": {"branches": ["main"]}}, "does not trigger on pull_request")

    def test_missing_on_block_fails(self):
        problems = self.failures({"jobs": {"probe": {"runs-on": "ubuntu-latest"}}})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no on: trigger block", problems[0])

    def test_on_must_be_a_mapping_or_event(self):
        self.assert_fails(42, "must be a mapping")

    def test_pull_request_config_must_be_empty_or_mapping(self):
        self.assert_fails({"pull_request": "main"}, "must be empty or a mapping")


class TimeoutRule(unittest.TestCase):
    def setUp(self):
        check_workflows.problems.clear()

    def failures(self, jobs):
        quiet(check_workflows.check_timeouts, "probe.yml", {"jobs": jobs})
        return check_workflows.problems

    def job(self, **fields):
        base = {"runs-on": "ubuntu-latest", "steps": [{"run": "echo ok"}]}
        base.update(fields)
        return base

    def test_positive_timeout_passes(self):
        self.assertEqual(self.failures({"probe": self.job(**{"timeout-minutes": 15})}), [])

    def test_missing_timeout_fails(self):
        problems = self.failures({"probe": self.job()})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no timeout-minutes", problems[0])

    def test_zero_timeout_fails(self):
        problems = self.failures({"probe": self.job(**{"timeout-minutes": 0})})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("positive whole number", problems[0])

    def test_negative_timeout_fails(self):
        problems = self.failures({"probe": self.job(**{"timeout-minutes": -5})})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("positive whole number", problems[0])

    def test_boolean_timeout_fails(self):
        problems = self.failures({"probe": self.job(**{"timeout-minutes": True})})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("positive whole number", problems[0])

    def test_string_timeout_fails(self):
        problems = self.failures({"probe": self.job(**{"timeout-minutes": "15"})})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("positive whole number", problems[0])

    def test_reusable_workflow_job_is_skipped(self):
        call = {"uses": f"org/repo/.github/workflows/ci.yml@{SHA}"}
        self.assertEqual(self.failures({"call": call}), [])

    def test_no_jobs_fails(self):
        problems = self.failures({})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no jobs mapping", problems[0])

    def test_job_must_be_a_mapping(self):
        problems = self.failures({"probe": "oops"})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("must be a mapping", problems[0])


class PinRule(unittest.TestCase):
    def setUp(self):
        check_workflows.problems.clear()

    def failures(self, data):
        quiet(check_workflows.check_pins, "probe.yml", data)
        return check_workflows.problems

    def steps(self, *uses):
        return {"jobs": {"probe": {"runs-on": "ubuntu-latest",
                                   "steps": [{"uses": value} for value in uses]}}}

    def test_commit_sha_passes(self):
        self.assertEqual(self.failures(self.steps(f"actions/checkout@{SHA}")), [])

    def test_image_digest_passes(self):
        self.assertEqual(self.failures(self.steps(f"docker://rhysd/actionlint@sha256:{DIGEST}")), [])

    def test_local_workflow_passes(self):
        self.assertEqual(self.failures(self.steps("./.github/workflows/ci.yml")), [])

    def test_tag_fails(self):
        problems = self.failures(self.steps("actions/checkout@v4"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("commit SHA", problems[0])

    def test_missing_ref_fails(self):
        problems = self.failures(self.steps("actions/checkout"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("commit SHA", problems[0])

    def test_short_sha_fails(self):
        problems = self.failures(self.steps(f"actions/checkout@{SHA[:39]}"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("commit SHA", problems[0])

    def test_image_tag_fails(self):
        problems = self.failures(self.steps("docker://rhysd/actionlint:latest"))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("image digest", problems[0])

    def test_job_level_uses_is_checked(self):
        data = {"jobs": {"call": {"uses": "org/repo/.github/workflows/ci.yml@v1"}}}
        problems = self.failures(data)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("job 'call'", problems[0])


if __name__ == "__main__":
    unittest.main()
