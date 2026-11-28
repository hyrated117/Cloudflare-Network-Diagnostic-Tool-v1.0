#!/usr/bin/env python3
"""Check that CI still runs on the Node and Python versions README.md promises.

`README.md` states "Node.js 18+ **or** Python 3.8+", and a matrix leg executes those
versions. Nothing made the two agree: lowering a leg, deleting it, or editing the
requirement would leave the promise untested while every workflow stayed green, because
a matrix naming any versions at all is valid YAML. This check ties the two together.

It asserts four things:

1. the README's `## Requirements` list still names a Node.js and a Python minimum;
2. the `validate` job has a matrix whose legs each set `node` and `python`;
3. at least one leg runs the exact Node minimum and at least one the exact Python
   minimum — the same leg may cover both;
4. the setup steps read those values from the matrix, because a leg that names 18 and a
   step that hardcodes 20 tests neither.

Every rule is pinned both ways by `Tools/test_check_runtimes.py`, which feeds mappings
rather than files, so it needs no PyYAML; this tool imports PyYAML inside `main()`, the
way `check-dependabot.py` does.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# `${{ matrix.node }}` and `${{ matrix.python }}`, spelled exactly as the workflows need.
MATRIX_NODE = "${{ matrix.node }}"
MATRIX_PYTHON = "${{ matrix.python }}"
SETUP = {"node": ("actions/setup-node", "node-version"), "python": ("actions/setup-python", "python-version")}

problems = []


def fail(message):
    problems.append(message)


def requirements_section(text):
    """The lines under `## Requirements`, up to the next heading."""
    lines = text.splitlines()
    section = []
    inside = False
    for line in lines:
        if re.match(r"^##\s+Requirements\s*$", line):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            section.append(line)
    return "\n".join(section)


def minimums(text):
    """The Node and Python minimums the README promises, or None where it names none."""
    section = requirements_section(text)
    node = re.search(r"Node(?:\.js)?\s+(\d+(?:\.\d+)*)\s*\+", section)
    python = re.search(r"Python\s+(\d+(?:\.\d+)*)\s*\+", section)
    return {
        "node": node.group(1) if node else None,
        "python": python.group(1) if python else None,
    }


def validate_job(workflow):
    """The `validate` job, or {} when the workflow does not define one."""
    job = ((workflow or {}).get("jobs") or {}).get("validate")
    return job if isinstance(job, dict) else {}


def legs(job):
    """The matrix legs as a list of mappings; [] when there is no `include` matrix."""
    matrix = (job.get("strategy") or {}).get("matrix")
    include = matrix.get("include") if isinstance(matrix, dict) else None
    return include if isinstance(include, list) else []


def setup_step(job, kind):
    """The step that installs one runtime, matched by the action it uses."""
    action = SETUP[kind][0]
    for step in job.get("steps") or []:
        if isinstance(step, dict) and str(step.get("uses", "")).startswith(action + "@"):
            return step
    return None


def check(minimums_by_runtime, job):
    """Every rule above, against parsed values. Returns nothing; appends to `problems`."""
    for kind in ("node", "python"):
        if minimums_by_runtime[kind] is None:
            fail(f"README.md no longer states a {kind.capitalize()} minimum in ## Requirements")

    found = legs(job)
    if not found:
        fail("the validate job has no strategy.matrix.include legs, so no runtime is chosen")
        return

    for index, leg in enumerate(found):
        if not isinstance(leg, dict):
            fail(f"matrix leg {index}: must be a mapping with node and python")
            continue
        label = f"matrix leg {index} ({leg.get('name', 'unnamed')})"
        for kind in ("node", "python"):
            value = leg.get(kind)
            if not isinstance(value, str) or not value.strip():
                # An unquoted 3.10 is a float and reads back as 3.1, which would silently
                # test the wrong interpreter, so the type is part of the rule.
                fail(f"{label}: {kind} must be a quoted version string, got {value!r}")
            elif not re.fullmatch(r"\d+(\.\d+)*", value):
                fail(f"{label}: {kind} is not a version: {value!r}")

    for kind in ("node", "python"):
        wanted = minimums_by_runtime[kind]
        if wanted is None:
            continue
        available = sorted(str(leg.get(kind)) for leg in found if isinstance(leg, dict))
        if wanted not in available:
            fail(
                f"no validate leg runs {kind.capitalize()} {wanted}, the minimum README.md "
                f"promises; the matrix has {', '.join(available) or 'none'}"
            )

    for kind, (_, key) in SETUP.items():
        step = setup_step(job, kind)
        wanted = MATRIX_NODE if kind == "node" else MATRIX_PYTHON
        if step is None:
            fail(f"the validate job has no step using {SETUP[kind][0]}, so a leg installs nothing")
            continue
        value = (step.get("with") or {}).get(key)
        if value != wanted:
            fail(
                f"the {SETUP[kind][0]} step sets {key} to {value!r}, not {wanted!r}, "
                "so the matrix versions are not the ones installed"
            )


def main():
    try:
        import yaml
    except ModuleNotFoundError:
        return (
            "check-runtimes.py needs PyYAML: python3 -m pip install pyyaml==6.0.3 "
            "(CI installs it before running this check)"
        )

    if not README.is_file():
        return "README.md is missing, so the promised minimums cannot be read"
    if not WORKFLOW.is_file():
        return f"{WORKFLOW.relative_to(ROOT)} is missing, so no matrix can run"

    promised = minimums(README.read_text(encoding="utf-8"))
    try:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        return f"{WORKFLOW.relative_to(ROOT)} is not valid YAML{where}: {error}"

    job = validate_job(workflow)
    check(promised, job)

    if problems:
        for message in problems:
            print(f"FAIL: {message}", file=sys.stderr)
        return f"{len(problems)} problem(s) in the validate matrix"

    covered = ", ".join(
        f"{leg.get('node')}/{leg.get('python')}" for leg in legs(job) if isinstance(leg, dict)
    )
    print(
        f"ok the validate matrix runs Node {promised['node']} and Python {promised['python']} "
        f"as promised: {covered}"
    )
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(1)
    sys.exit(result)
