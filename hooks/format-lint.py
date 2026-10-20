#!/usr/bin/env python3
"""Claude Code PostToolUse hook: format and lint each file Claude edits.

Runs after Edit and Write. Exits 2 with the problems on stderr so Claude sees
them and fixes the file; exits 0 when the file is clean or has no checker.

- *.py: `ruff format` and `ruff check --fix` if ruff is installed, otherwise
  a syntax check.
- *.yml, *.yaml: yamllint, if installed.
- *.json: must parse.
- *.md: relative links must resolve (scripts/check_links.py).

Standard library only.
"""

import json
import os
import shutil
import subprocess
import sys


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def check(path, root):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        if shutil.which("ruff"):
            run(["ruff", "format", "--quiet", path])
            return run(["ruff", "check", "--fix", "--quiet", path])
        return run([sys.executable, "-m", "py_compile", path])
    if ext in (".yml", ".yaml"):
        code, _ = run([sys.executable, "-m", "yamllint", "--version"])
        if code != 0:
            return 0, ""
        return run([sys.executable, "-m", "yamllint", "-s", path])
    if ext == ".json":
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
        except ValueError as exc:
            return 1, f"invalid JSON: {exc}"
        return 0, ""
    if ext == ".md":
        script = os.path.join(root, "scripts", "check_links.py")
        if os.path.isfile(script):
            return run([sys.executable, script, path])
    return 0, ""


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    path = (data.get("tool_input") or {}).get("file_path")
    if not path or not os.path.isfile(path):
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    code, output = check(path, root)
    if code != 0:
        print(f"format-lint: {path} has problems; fix them:\n{output}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
