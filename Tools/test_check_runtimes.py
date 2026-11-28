#!/usr/bin/env python3
"""Self-test for the rules in Tools/check-runtimes.py.

The matrix and the README's stated minimums have to stay in step, and neither breaks
loudly on its own: a workflow naming any runtimes is valid YAML, and a README edit is
just prose. Every rule is pinned here both ways — a matrix that drops the minimum, a
setup step that hardcodes a version, an unquoted `3.10` or a README that stops stating
a minimum must each fail, and a matrix that covers both minimums must stay quiet.

    python3 Tools/test_check_runtimes.py

Stdlib only; the tool imports PyYAML inside main(), so this runs without it.
"""

import contextlib
import importlib.util
import io
import pathlib
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "check-runtimes.py"
SPEC = importlib.util.spec_from_file_location("check_runtimes", TOOL)
check_runtimes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_runtimes)

PROMISED = {"node": "18", "python": "3.8"}


def leg(node, python, name="leg"):
    return {"name": name, "node": node, "python": python}


def job(*legs, node=check_runtimes.MATRIX_NODE, python=check_runtimes.MATRIX_PYTHON, drop=None):
    steps = [
        {"uses": "actions/setup-node@0d9bb1b1a5b0e5e0a0d0c0b0a090807060504030", "with": {"node-version": node}},
        {"uses": "actions/setup-python@0d9bb1b1a5b0e5e0a0d0c0b0a090807060504030", "with": {"python-version": python}},
    ]
    if drop:
        steps = [step for step in steps if not step["uses"].startswith(drop)]
    return {"strategy": {"matrix": {"include": list(legs)}}, "steps": steps}


class Base(unittest.TestCase):
    def setUp(self):
        check_runtimes.problems.clear()

    def failures(self, promised, value):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            check_runtimes.check(promised, value)
        return check_runtimes.problems

    def assert_sound(self, promised, value):
        self.assertEqual(self.failures(promised, value), [])

    def assert_fails(self, promised, value, expected):
        problems = self.failures(promised, value)
        self.assertTrue(problems, "expected a failure")
        self.assertTrue(
            any(expected in problem for problem in problems),
            f"{expected!r} not in {problems}",
        )


class Minimums(Base):
    def test_readme_requirement_bullet(self):
        text = "# Tool\n\n## Requirements\n\n- Node.js 18+ **or** Python 3.8+ (either one)\n"
        self.assertEqual(check_runtimes.minimums(text), {"node": "18", "python": "3.8"})

    def test_patch_version_and_spacing(self):
        text = "## Requirements\n\n- Node.js 20.11+ or Python 3.12.1+\n"
        self.assertEqual(check_runtimes.minimums(text), {"node": "20.11", "python": "3.12.1"})

    def test_missing_python_minimum(self):
        text = "## Requirements\n\n- Node.js 18+\n"
        self.assertEqual(check_runtimes.minimums(text), {"node": "18", "python": None})

    def test_minimum_outside_the_requirements_section_is_ignored(self):
        text = "## Requirements\n\n- Node.js 18+\n\n## Checks\n\nPython 3.8+ is enough.\n"
        self.assertEqual(check_runtimes.minimums(text), {"node": "18", "python": None})

    def test_readme_without_the_section(self):
        self.assertEqual(check_runtimes.minimums("# Tool\n"), {"node": None, "python": None})


class Legs(Base):
    def test_include_matrix(self):
        self.assertEqual(check_runtimes.legs(job(leg("18", "3.8"))), [leg("18", "3.8")])

    def test_matrix_without_include(self):
        self.assertEqual(check_runtimes.legs({"strategy": {"matrix": {"node": ["18"]}}}), [])

    def test_job_without_strategy(self):
        self.assertEqual(check_runtimes.legs({}), [])


class Coverage(Base):
    def test_one_leg_covering_both_minimums(self):
        self.assert_sound(PROMISED, job(leg("18", "3.8")))

    def test_both_minimums_covered_on_separate_legs(self):
        self.assert_sound(PROMISED, job(leg("20", "3.12"), leg("18", "3.8")))

    def test_missing_node_minimum(self):
        self.assert_fails(PROMISED, job(leg("20", "3.12")), "no validate leg runs Node 18")

    def test_missing_python_minimum(self):
        self.assert_fails(PROMISED, job(leg("18", "3.12")), "no validate leg runs Python 3.8")

    def test_no_legs_at_all(self):
        self.assert_fails(PROMISED, job(), "no strategy.matrix.include legs")

    def test_readme_without_a_minimum(self):
        self.assert_fails({"node": None, "python": "3.8"}, job(leg("18", "3.8")), "README.md no longer states a Node minimum")


class LegShape(Base):
    def test_leg_without_python(self):
        self.assert_fails(PROMISED, job({"name": "leg", "node": "18"}), "python must be a quoted version string")

    def test_unquoted_float_version(self):
        self.assert_fails(PROMISED, job(leg("18", 3.8)), "python must be a quoted version string")

    def test_version_that_is_not_a_version(self):
        self.assert_fails(PROMISED, job(leg("18.x", "3.8")), "node is not a version")

    def test_leg_that_is_not_a_mapping(self):
        self.assert_fails(PROMISED, job("18/3.8"), "must be a mapping with node and python")


class SetupWiring(Base):
    def test_hardcoded_node_version(self):
        self.assert_fails(PROMISED, job(leg("18", "3.8"), node="20"), "so the matrix versions are not the ones installed")

    def test_hardcoded_python_version(self):
        self.assert_fails(PROMISED, job(leg("18", "3.8"), python="3.12"), "so the matrix versions are not the ones installed")

    def test_missing_setup_python_step(self):
        self.assert_fails(PROMISED, job(leg("18", "3.8"), drop="actions/setup-python"), "no step using actions/setup-python")


if __name__ == "__main__":
    unittest.main(verbosity=2)
