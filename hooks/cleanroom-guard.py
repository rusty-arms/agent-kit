#!/usr/bin/env python3
"""Claude Code PreToolUse hook: the clean-room guard.

Shipped by the agent-kit plugin (hooks/hooks.json) to every session that has
the plugin enabled. Policy: core's docs/clean-room.md and
docs/setup/claude-guard.md.

- Reads the hook input JSON from stdin.
- Flattens tool_input into one lower-case string.
- Exits 2 (blocking the tool call) if any blocklist term appears in it. This
  applies to every tool the plugin routes here, writes and MCP tools included,
  so forbidden names can't be fetched, searched for or written into a file.
- Exits 2 if a reading tool (Bash, Read, Grep, Glob, WebFetch, WebSearch)
  touches the lab folder, unless the session's cwd is itself inside the lab
  (observer sessions run from there). Writes and MCP tools are not lab-checked,
  so docs and messages can still name the lab's path.
- Otherwise exits 0.

The blocklist terms are never committed. They come from, in order:
  1. ~/.claude/cleanroom-blocklist.txt (one lower-case term per line,
     '#' for comments) on the owner's PC;
  2. the CLEANROOM_BLOCKLIST_TERMS environment variable (comma-separated),
     for cloud environments.
With no terms at all, every guarded call is blocked (fail closed), except in
a Claude Code cloud session (CLAUDE_CODE_REMOTE set), which only gets a
warning so it is not locked out before its environment is configured.

Environment overrides: CLEANROOM_BLOCKLIST (blocklist file), CLEANROOM_LAB
(lab folder). Standard library only.
"""

import json
import os
import sys

HOME = os.path.expanduser("~")
BLOCKLIST = os.environ.get(
    "CLEANROOM_BLOCKLIST", os.path.join(HOME, ".claude", "cleanroom-blocklist.txt")
)
LAB = os.environ.get("CLEANROOM_LAB", "~/Develop/rusty-arms/ma-lab")
POLICY = "https://github.com/rusty-arms/core/blob/main/docs/clean-room.md"

# Tools whose input can read local files or the web. Only these are lab-checked.
LAB_CHECKED_TOOLS = {"Bash", "Read", "Grep", "Glob", "WebFetch", "WebSearch"}


def block(reason):
    print(f"cleanroom-guard: blocked: {reason}. See {POLICY}; tell the owner.", file=sys.stderr)
    sys.exit(2)


def load_terms():
    terms = []
    try:
        with open(BLOCKLIST, encoding="utf-8") as f:
            terms += [t.strip().lower() for t in f if t.strip() and not t.lstrip().startswith("#")]
    except OSError:
        pass
    env_terms = os.environ.get("CLEANROOM_BLOCKLIST_TERMS", "")
    terms += [t.strip().lower() for t in env_terms.split(",") if t.strip()]
    return terms


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        block("could not parse hook input")

    text = json.dumps(data.get("tool_input", {}), ensure_ascii=False).lower()

    terms = load_terms()
    if not terms:
        if os.environ.get("CLAUDE_CODE_REMOTE"):
            print(
                "cleanroom-guard: warning: no blocklist terms; set CLEANROOM_BLOCKLIST_TERMS "
                "in this cloud environment.",
                file=sys.stderr,
            )
        else:
            block(f"no blocklist terms ({BLOCKLIST} missing and CLEANROOM_BLOCKLIST_TERMS unset)")

    for term in terms:
        if term in text:
            block("input matches a clean-room blocklist term")

    # A missing tool_name (older callers, tests) is treated as a reading tool.
    if data.get("tool_name", "Read") not in LAB_CHECKED_TOOLS:
        sys.exit(0)

    lab_raw = LAB.rstrip("/").lower()
    lab_abs = os.path.expanduser(LAB).rstrip("/")
    lab_name = os.path.basename(lab_abs).lower()
    # Raw form (~/...), expanded form, $HOME forms, and the folder name
    # itself so relative paths are caught too.
    lab_forms = {
        lab_raw,
        lab_abs.lower(),
        lab_name,
        lab_raw.replace("~", "$home", 1),
        lab_raw.replace("~", "${home}", 1),
    }
    if any(form and form in text for form in lab_forms):
        cwd = data.get("cwd") or ""
        if not (cwd and inside(cwd, lab_abs)):
            block("input touches the lab folder from outside the lab")

    sys.exit(0)


if __name__ == "__main__":
    main()
