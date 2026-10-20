#!/usr/bin/env python3
"""Claude Code SessionStart hook: session discipline and clean-room reminders.

Prints the project's session rules to stdout, which Claude Code adds to the
session's context. Also warns when the clean-room guard has no blocklist
terms, because the guard then blocks every guarded tool call.

Standard library only. Always exits 0.
"""

import os
import sys

HOME = os.path.expanduser("~")
BLOCKLIST = os.environ.get(
    "CLEANROOM_BLOCKLIST", os.path.join(HOME, ".claude", "cleanroom-blocklist.txt")
)
LAB = os.path.expanduser(os.environ.get("CLEANROOM_LAB", "~/Develop/rusty-arms/ma-lab"))

RULES = """\
Rusty Arms session rules (from the agent-kit plugin):

Session discipline
1. Start by reading this repo's PROGRESS.md, if it has one, and `git log -10`.
   Project-wide status is in core's PROGRESS.md.
2. One task per session.
3. Make small commits, one per step.
4. Before ending, or as soon as a usage-limit warning appears, update
   PROGRESS.md with exactly where you stopped.

Clean room (full policy: core's docs/clean-room.md)
- Never access, search for, fetch, clone or read the 2019 source leak or
  anything built on it, the community asset compiler, archive copies of the
  source or prototype discs, the community HD texture pack, or decompiler
  output of the retail executable.
- Never commit retail game data, disc images, extracted files, screenshots or
  captures, or anything from the lab.
- If forbidden material appears: stop, don't summarise or quote it, tell the
  owner, and log an incident in core's docs/provenance-log.md.
- A blocked tool call is the answer. Report it; never route around it.
- Never edit verifiers, golden data or guard scripts to make a check pass.
"""

OBSERVER = """\
This session started inside the lab, so it is an OBSERVER session. Follow the
lab's CLAUDE.md: write what you learn as specs in your own words, never copy
code or retail bytes into a repo, and log every fact's provenance.
"""


def has_terms():
    try:
        with open(BLOCKLIST, encoding="utf-8") as f:
            if any(t.strip() and not t.lstrip().startswith("#") for t in f):
                return True
    except OSError:
        pass
    return any(t.strip() for t in os.environ.get("CLEANROOM_BLOCKLIST_TERMS", "").split(","))


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def main():
    print(RULES)
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    if inside(cwd, LAB):
        print(OBSERVER)
    if not has_terms():
        if os.environ.get("CLAUDE_CODE_REMOTE"):
            print(
                "WARNING: the clean-room guard has no blocklist terms. Set "
                "CLEANROOM_BLOCKLIST_TERMS in this cloud environment."
            )
        else:
            print(
                f"WARNING: the clean-room guard has no blocklist terms ({BLOCKLIST} is "
                "missing), so it will block every guarded tool call. Tell the owner."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
