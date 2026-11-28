#!/usr/bin/env python3
"""Pre-flight the stacked pull requests: bases are the previous tips, merges are clean.

The five branches are stacked, so a mistake in the chain — a branch based on the wrong
tip, a base that moved under it, a conflict that only appears when the branches are
merged into `main` in order — is invisible until review, and then every later pull
request's diff is wrong. This guard rehearses the whole sequence with git alone:

1. every branch resolves, and each pull request's base is the branch below it;
2. for pull requests 2–5 that base tip is an ancestor of the head, so the diff can
   only contain that pull request's own commits. Pull request 1's base is allowed to
   have moved, and its divergence is reported with how many commits it is ahead;
3. the branches are merged into a simulated `main` in order with
   `git merge-tree --write-tree`, which reports conflicts without touching a worktree,
   and each clean tree is wrapped in a throwaway commit so the next merge starts from
   it;
4. the final tree is reported, so a `main` that carries content the stack does not is
   visible rather than assumed away.

Nothing is checked out, no ref is moved, and no object is referenced: the rehearsal
commits are dangling objects. It needs the branch refs locally; `--fetch` downloads them
from `origin` first. Run it before opening or retargeting a pull request:

    python3 Tools/check-stack.py --fetch

`Tools/test_check_stack.py` pins its rules against throwaway repositories and runs in
`Validate` as `Self-test the stack check`, so the rehearsal is repeatable rather than
one-off. Needs git 2.38 or newer for `merge-tree --write-tree`.

Usage:
    python3 Tools/check-stack.py [--fetch] [--remote NAME]
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STACK = [
    "main",
    "pr/installer-ci",
    "fix/windows-trace-route-v2",
    "ci/packaging",
    "docs/rewrite",
    "fix/doh-cap-csv-cr",
]
IDENTITY = [
    "-c",
    "user.name=stack-check",
    "-c",
    "user.email=stack-check@example.invalid",
]


class StackError(Exception):
    """A ref, object or merge the guard cannot work with."""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def git_ok(repo, *args):
    completed = git(repo, *args)
    if completed.returncode != 0:
        raise StackError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def tip(repo, name, remote="origin"):
    """The commit a branch ref points at, preferring the remote-tracking ref."""
    for ref in (f"refs/remotes/{remote}/{name}", f"refs/heads/{name}", name):
        completed = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if completed.returncode == 0:
            return completed.stdout.strip()
    raise StackError(f"branch '{name}' does not exist (try --fetch)")


def is_ancestor(repo, older, newer):
    return git(repo, "merge-base", "--is-ancestor", older, newer).returncode == 0


def ahead_behind(repo, base, head):
    counts = git_ok(
        repo, "rev-list", "--left-right", "--count", f"{base}...{head}"
    ).split()
    behind, ahead = int(counts[0]), int(counts[1])
    return ahead, behind


def summary(repo, base, head):
    """Commits, files and line counts of one pull request's diff."""
    commits = int(git_ok(repo, "rev-list", "--count", f"{base}..{head}"))
    names = git_ok(repo, "diff", "--name-only", f"{base}...{head}").splitlines()
    added = removed = 0
    for line in git_ok(repo, "diff", "--numstat", f"{base}...{head}").splitlines():
        parts = line.split("\t")
        if len(parts) < 2 or parts[0] == "-":
            continue
        added += int(parts[0])
        removed += int(parts[1])
    return {
        "commits": commits,
        "files": len([name for name in names if name]),
        "added": added,
        "removed": removed,
    }


def merge(repo, left, right):
    """The tree of merging `right` into `left`, or the conflicts that stop it."""
    completed = git(repo, "merge-tree", "--write-tree", "--no-messages", left, right)
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode == 0 and lines:
        return lines[0].strip(), []
    conflicts = [line.strip() for line in lines[1:] if line.strip()]
    if not conflicts:
        conflicts = [completed.stderr.strip() or "merge failed with no detail"]
    return None, conflicts


def rehearsal(repo, branches, remote="origin"):
    """Rehearse the stack; returns (problems, results, final tree, last head tree)."""
    problems, results = [], []
    tips = [tip(repo, name, remote) for name in branches]
    parent = tips[0]
    for index in range(1, len(branches)):
        base, head = branches[index - 1], branches[index]
        base_tip, head_tip = tips[index - 1], tips[index]
        step = {
            "pull_request": index,
            "head": head,
            "head_tip": head_tip,
            "base": base,
            "base_tip": base_tip,
        }
        step.update(summary(repo, base_tip, head_tip))
        step["ancestor"] = is_ancestor(repo, base_tip, head_tip)
        step["ahead"], step["behind"] = ahead_behind(repo, base_tip, head_tip)
        if not step["ancestor"]:
            if index == 1:
                step["note"] = (
                    f"base {base} moved after the branch point: "
                    f"{step['behind']} commit(s) on it are not on this branch; "
                    f"allowed if the merge is clean"
                )
            else:
                problems.append(
                    f"PR {index} ({head}) is not based on {base}: "
                    f"its diff would include another pull request's commits"
                )
        tree, conflicts = merge(repo, parent, head_tip)
        step["clean"] = not conflicts
        step["conflicts"] = conflicts
        if conflicts:
            problems.append(
                f"PR {index} ({head}) conflicts when merged into main "
                f"after PR {index - 1}: " + "; ".join(conflicts[:3])
            )
            results.append(step)
            continue
        step["tree"] = tree
        parent = git_ok(
            repo,
            *IDENTITY,
            "commit-tree",
            tree,
            "-p",
            parent,
            "-p",
            head_tip,
            "-m",
            f"stack rehearsal: PR {index}",
        )
        results.append(step)
    final_tree = git_ok(repo, "rev-parse", f"{parent}^{{tree}}")
    last_tree = git_ok(repo, "rev-parse", f"{tips[-1]}^{{tree}}")
    return problems, results, final_tree, last_tree


def run(branches=STACK, remote="origin", repo=ROOT):
    problems, results, final_tree, last_tree = rehearsal(repo, branches, remote)
    for step in results:
        if step["clean"]:
            detail = (
                f"{step['commits']} commit(s), {step['files']} file(s), "
                f"+{step['added']} −{step['removed']}; clean"
            )
        else:
            detail = "CONFLICTS: " + "; ".join(step["conflicts"][:3])
        ancestry = ""
        if not step["ancestor"]:
            ancestry = "; " + step.get("note", "base is not an ancestor")
        allowed = step["clean"] and (step["ancestor"] or step["pull_request"] == 1)
        print(
            f"{'ok' if allowed else 'FAIL'} PR {step['pull_request']} {step['head']} "
            f"({step['head_tip'][:7]}): {detail}{ancestry}"
        )
    same = final_tree == last_tree
    print(
        f"{'ok' if same else 'note'} final tree {final_tree[:7]} "
        + ("matches" if same else "differs from")
        + f" {branches[-1]}'s tree {last_tree[:7]}"
    )
    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        print(f"{len(problems)} stack problem(s)", file=sys.stderr)
        return 1
    print(f"{len(results)} merge(s) into main are conflict-free")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fetch", action="store_true", help="fetch the branches from the remote first"
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="remote to resolve and fetch (default: origin)",
    )
    args = parser.parse_args(argv)
    if args.fetch:
        refspec = f"+refs/heads/*:refs/remotes/{args.remote}/*"
        fetched = git(ROOT, "fetch", args.remote, refspec)
        if fetched.returncode != 0:
            print(
                f"FAIL: could not fetch {args.remote}: {fetched.stderr.strip()}",
                file=sys.stderr,
            )
            return 1
    try:
        return run(remote=args.remote)
    except StackError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
