#!/usr/bin/env python3
"""Fail on broken links in Markdown files.

External links (http/https/mailto) are not fetched. Every other target must
resolve to a file or directory relative to the Markdown file that contains it,
and must use a relative path or a supported URL scheme. Links inside fenced code
blocks are ignored, so JSON examples cannot produce false positives.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r'!?\[[^\]]*\]\(\s*([^)\s]+?)\s*(?:"[^"]*")?\)')
EXTERNAL = ("http://", "https://", "mailto:")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
FENCE = re.compile(r"^\s*(```|~~~)")


def lines_without_fences(path):
    """Yield (line_number, text), blanking out fenced code blocks."""
    inside = False
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            inside = not inside
            yield number, ""
            continue
        yield number, "" if inside else line


def main():
    files = [path for path in sorted(ROOT.rglob("*.md")) if ".git" not in path.parts]
    total = 0
    problems = []

    for path in files:
        for number, line in lines_without_fences(path):
            for target in LINK.findall(line):
                total += 1
                if target.startswith(EXTERNAL) or target.startswith("#"):
                    continue
                if SCHEME.match(target):
                    problems.append((path, number, target, "unsupported link scheme"))
                    continue
                relative = target.split("#")[0].split("?")[0]
                if relative and not (path.parent / relative).exists():
                    problems.append((path, number, target, "missing target"))

    for path, number, target, reason in problems:
        print(f"{path.relative_to(ROOT)}:{number}: {reason}: {target}", file=sys.stderr)

    if problems:
        sys.exit(f"{len(problems)} broken link(s) in {len(files)} Markdown files")

    print(f"{total} links in {len(files)} Markdown files resolve")


if __name__ == "__main__":
    main()
