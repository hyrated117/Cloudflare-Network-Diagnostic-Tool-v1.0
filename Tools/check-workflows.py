#!/usr/bin/env python3
"""Fail when a workflow could silently skip a pull request, run unbounded, run
unpinned code, or drop half of a command without saying so.

All four checks are about failures GitHub reports as nothing at all.

Triggers: these branches are stacked, so a pull request is opened against the branch
below it rather than against main. A `branches:` filter on `pull_request` therefore
skips exactly the pull requests under review: the file still parses, GitHub just never
creates the run. The four pull-request workflows must trigger on all of them. The push
trigger is not checked - it stays filtered so a branch is scanned once, when it lands.

Timeouts: a job without `timeout-minutes` inherits GitHub's six-hour default, so a hung
download, trace or upload holds a runner until then. Every job that can set one must. A
job that calls a reusable workflow is skipped: its timeout belongs to the callee.

Pins: an action referenced by tag, branch or nothing can change under a commit that
already passed. Every `uses:` must name a commit SHA, a docker image digest, or a local
workflow under ./ that cannot be pinned at all.

Continuations: a pwsh line break is a backtick and a POSIX one is a backslash, and
either must be the last character on the line. Whitespace after it ends the line
instead, so the continuation is lost and the rest of the command runs as its own
statement - `--flag` then reads as a unary operator or an unknown command. The shell
reports it only at run time, so no local check reached it. Which character is checked
follows the shell the block runs in: the step's `shell:`, then the job's and the
workflow's `defaults.run.shell`, then the runner (pwsh on Windows, bash elsewhere).
Only code counts: a character inside a quoted string, a comment, a here-document or a
here-string is literal text, so the line is masked before the match is trusted.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"
PR_WORKFLOWS = ("ci.yml", "codeql.yml", "dependency-review.yml", "security-scan.yml")
BRANCH_FILTERS = ("branches", "branches-ignore")
ACTION_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
IMAGE_PIN = re.compile(r"^docker://[\w.-]+(?:/[\w.-]+)*@sha256:[0-9a-f]{64}$")
# Which character continues a line, per shell, and what to call it in a message.
CONTINUATIONS = {"pwsh": ("`", "backtick"), "bash": ("\\", "backslash")}
MISSING = object()

problems = []


def fail(message):
    problems.append(message)


def event_map(spec):
    """Normalize an `on:` value to {event: configuration}, or None if unusable."""
    if spec is None:
        return {}
    if isinstance(spec, str):
        return {spec: None}
    if isinstance(spec, list):
        return {str(event): None for event in spec}
    if isinstance(spec, dict):
        return spec
    return None


def uses_entries(data):
    """Yield (where, value) for every `uses:` in a workflow, jobs and steps alike."""
    for job_name, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        if "uses" in job:
            yield f"job {job_name!r}", str(job["uses"])
        for number, step in enumerate(job.get("steps") or [], 1):
            if isinstance(step, dict) and "uses" in step:
                yield f"job {job_name!r} step {number}", str(step["uses"])


def check_triggers(label, data):
    # PyYAML resolves the bare key `on` as the boolean True under YAML 1.1.
    spec = data.get("on", data.get(True, MISSING))
    if spec is MISSING:
        return fail(f"{label} has no on: trigger block")
    mapping = event_map(spec)
    if mapping is None:
        return fail(f"{label}: on: must be a mapping, a list or an event name")
    if "pull_request" not in mapping:
        return fail(
            f"{label} does not trigger on pull_request at all, so no run is created "
            "for a pull request"
        )

    config = mapping["pull_request"]
    if config is not None and not isinstance(config, dict):
        return fail(f"{label}: pull_request must be empty or a mapping, got {config!r}")
    filters = [key for key in BRANCH_FILTERS if key in (config or {})]
    if filters:
        return fail(
            f"{label} filters pull_request by {', '.join(filters)} "
            f"({config[filters[0]]!r}); a stacked pull request targets the branch "
            "below it, so that filter skips it while the file still parses"
        )
    detail = f" ({', '.join(sorted(config))} set)" if config else ""
    print(f"ok {label}: pull_request runs for every branch{detail}")


def check_timeouts(label, data):
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return fail(f"{label} has no jobs mapping, so its jobs cannot be checked")

    checked = 0
    for name, job in jobs.items():
        if not isinstance(job, dict):
            fail(f"{label}: job {name!r} must be a mapping")
            continue
        if "uses" in job:
            # Reusable workflow call: the callee's jobs carry their own timeouts.
            continue
        checked += 1
        value = job.get("timeout-minutes")
        if value is None:
            fail(
                f"{label}: job {name!r} has no timeout-minutes, so it inherits GitHub's "
                "six-hour default; a hung download, trace or upload would hold a runner "
                "until then"
            )
        elif isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            fail(
                f"{label}: job {name!r} has timeout-minutes {value!r}; "
                "expected a positive whole number of minutes"
            )
    print(f"ok {label}: {checked} job(s) set timeout-minutes")


def shell_of(step, job, data):
    """The shell a `run:` block executes in, resolved the way GitHub resolves it."""
    for candidate in (
        step.get("shell"),
        ((job.get("defaults") or {}).get("run") or {}).get("shell"),
        ((data.get("defaults") or {}).get("run") or {}).get("shell"),
    ):
        if not isinstance(candidate, str) or not candidate:
            continue
        lowered = candidate.lower()
        if "pwsh" in lowered or "powershell" in lowered:
            return "pwsh"
        if "bash" in lowered or lowered.startswith("sh"):
            return "bash"
        return None  # cmd, python or another shell: neither continuation rule applies
    runner = str(job.get("runs-on") or "").lower()
    return "pwsh" if "windows" in runner else "bash"


def run_blocks(data):
    """Yield (where, run text, shell) for every `run:` block in a workflow."""
    for job_name, job in (data.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for number, step in enumerate(job.get("steps") or [], 1):
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                name = step.get("name")
                where = f"job {job_name!r} step {number}"
                yield (
                    f"{where} ({name!r})" if name else where
                ), step["run"], shell_of(step, job, data)


def masked_lines(lines, shell):
    """Yield each line with its literal text blanked to spaces, same length.

    Quoted text, comments, here-documents and here-strings are not code: a continuation
    character inside them is literal and continues nothing, so the caller looks at the
    masked line to decide whether a match is real.
    """
    quoted = None
    heredoc = None
    strip_tabs = False
    block_comment = False
    for line in lines:
        if heredoc is not None or block_comment:
            yield " " * len(line)
            if heredoc is not None:
                probe = line.lstrip("\t") if strip_tabs else line
                if probe.strip() == heredoc:
                    heredoc = None
            if block_comment and "#>" in line:
                block_comment = False
            continue

        out = list(line)
        index = 0
        while index < len(line):
            char = line[index]
            if quoted is not None:
                out[index] = " "
                if char == "\\" and quoted != "'":
                    if index + 1 < len(line):
                        out[index + 1] = " "
                        index += 2
                        continue
                elif char == quoted:
                    quoted = None
                index += 1
                continue
            if char in "'\"":
                quoted = char
                out[index] = " "
            elif char == "#" and (index == 0 or line[index - 1] in " \t"):
                out[index:] = " " * (len(line) - index)
                break
            elif shell == "pwsh" and line.startswith("<#", index):
                close = line.find("#>", index)
                end = len(line) if close < 0 else close + 2
                out[index:end] = " " * (end - index)
                block_comment = close < 0
                index = end
                continue
            index += 1
        masked = "".join(out)
        yield masked

        # A here-document or here-string starts on the line that opens it and runs to
        # its terminator, so only look for an opener in code.
        if quoted is None and heredoc is None:
            if shell == "bash":
                opener = re.search(r"<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\1", line)
                if opener and masked.startswith("<<", opener.start()):
                    strip_tabs = opener.group(0).startswith("<<-")
                    heredoc = opener.group(2)
            else:
                opener = re.search(r"@(['\"])\s*$", line)
                if opener and masked[opener.start()] == "@":
                    heredoc = opener.group(1) + "@"


def check_continuations(label, data):
    """Fail on a code line whose continuation character is followed by whitespace."""
    checked = 0
    for where, run, shell in run_blocks(data):
        if shell is None:
            continue
        checked += 1
        character, spoken = CONTINUATIONS[shell]
        pattern = re.compile(re.escape(character) + r"[ \t]+$")
        lines = run.splitlines()
        for number, (line, masked) in enumerate(zip(lines, masked_lines(lines, shell)), 1):
            match = pattern.search(line)
            if not match or masked[match.start()] == " ":
                continue
            fail(
                f"{label}: {where} line {number} of its {shell} run: block puts "
                f"whitespace after a continuation {spoken} ({line.lstrip()!r}); "
                f"{shell} ends the line at the whitespace, so the continuation is "
                "lost and the rest of the command becomes a separate statement"
            )
    return checked


def check_pins(label, data):
    pinned = 0
    for where, value in uses_entries(data):
        if value.startswith("./"):
            continue  # local workflow: a repository path, not something to pin
        pinned += 1
        if value.startswith("docker://"):
            ok, expected = IMAGE_PIN.match(value), "an image digest"
        else:
            ok, expected = ACTION_PIN.match(value), "a commit SHA"
        if not ok:
            fail(
                f"{label}: {where} uses {value!r}, which is not pinned to {expected}; "
                "a moved tag or branch would change what runs on a commit that already "
                "passed"
            )
    print(f"ok {label}: {pinned} action/image reference(s) pinned")


def main():
    try:
        import yaml
    except ModuleNotFoundError:
        return (
            "check-workflows.py needs PyYAML: python3 -m pip install pyyaml==6.0.4 "
            "(CI installs it before running this check)"
        )

    paths = sorted(WORKFLOW_DIR.glob("*.yml")) if WORKFLOW_DIR.is_dir() else []
    if not paths:
        return fail(".github/workflows has no .yml files") or "no workflows found"

    loaded = {}
    run_block_count = 0
    for path in paths:
        label = path.relative_to(ROOT).as_posix()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
            fail(f"{label} is not valid YAML{where}: {error}")
            continue
        if not isinstance(data, dict):
            fail(f"{label} must be a mapping at the top level")
            continue
        loaded[path.name] = data
        check_timeouts(label, data)
        check_pins(label, data)
        run_block_count += check_continuations(label, data)

    present = {path.name for path in paths}
    for name in PR_WORKFLOWS:
        if name not in present:
            fail(f".github/workflows/{name} is missing")
        elif name in loaded:
            check_triggers(f".github/workflows/{name}", loaded[name])

    if problems:
        for message in problems:
            print(f"FAIL: {message}", file=sys.stderr)
        return (
            f"{len(problems)} problem(s) in the workflows' triggers, timeouts, pins "
            "or continuations"
        )

    print(f"ok {len(PR_WORKFLOWS)} pull-request workflows: trigger not filtered by branch")
    print(f"ok {len(loaded)} workflows: every job sets a timeout and every use is pinned")
    print(
        f"ok {run_block_count} run: block(s): no whitespace after a line-continuation "
        "character"
    )
    return 0


if __name__ == "__main__":
    result = main()
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(1)
    sys.exit(result)
