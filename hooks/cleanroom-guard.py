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
- Exits 2 if a local reading tool (Bash, Read, Grep, Glob) reaches into the
  fence (~/Develop) anywhere outside the workspace (~/Develop/rusty-arms), so
  no session goes looking through the owner's other code. That includes a
  session started there, a glob that could expand into it, and a search that
  would walk into it from above, such as `find /` or `grep -r ~`. Bash is
  checked word by word, best effort, like the lab check.
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
(lab folder), CLEANROOM_FENCE and CLEANROOM_WORKSPACE (the fence and the
workspace inside it). Standard library only.
"""

import json
import os
import shlex
import sys

HOME = os.path.expanduser("~")
BLOCKLIST = os.environ.get(
    "CLEANROOM_BLOCKLIST", os.path.join(HOME, ".claude", "cleanroom-blocklist.txt")
)
LAB = os.environ.get("CLEANROOM_LAB", "~/Develop/rusty-arms/ma-lab")
FENCE = os.environ.get("CLEANROOM_FENCE", "~/Develop")
WORKSPACE = os.environ.get("CLEANROOM_WORKSPACE", "~/Develop/rusty-arms")
POLICY = "https://github.com/rusty-arms/core/blob/main/docs/clean-room.md"

# Tools whose input can read local files or the web. Only these are lab-checked.
LAB_CHECKED_TOOLS = {"Bash", "Read", "Grep", "Glob", "WebFetch", "WebSearch"}
# Tools that read the local file system. Only these are fence-checked.
FENCE_CHECKED_TOOLS = {"Bash", "Read", "Grep", "Glob"}
GLOB_CHARS = "*?["


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


def under(path, root):
    """Like inside(), on already-normalised lower-case strings, without touching the disk."""
    return path == root or path.startswith(root.rstrip("/") + "/")


def text_forms(path):
    """The lower-case ways a command can spell an absolute path under the home folder."""
    forms = {path.lower()}
    if under(path, HOME):
        rest = path[len(HOME) :].lower()
        forms |= {"~" + rest, "$home" + rest, "${home}" + rest}
    return forms


def continues_name(char):
    return char.isalnum() or char in "-_."


def text_escapes_workspace(text, fence, workspace):
    """True if the text spells a place in the fence that isn't in the workspace."""
    tail = workspace[len(fence) :].lower()
    for form in text_forms(fence):
        start = text.find(form)
        while start >= 0:
            rest = text[start + len(form) :]
            start = text.find(form, start + 1)
            if rest[:1] and continues_name(rest[0]):
                continue  # a different folder, such as ~/Developer
            if rest.startswith(tail) and not (rest[len(tail) :][:1] and continues_name(rest[len(tail)])):
                continue
            return True
    return False


def path_words(tool, tool_input):
    """Words in the tool's input that may be paths."""
    words = [tool_input.get(key) for key in ("file_path", "path", "notebook_path")]
    words = [w for w in words if isinstance(w, str) and w]
    pattern = tool_input.get("pattern")
    if tool == "Glob" and isinstance(pattern, str) and pattern:
        base = tool_input.get("path")
        words.append(os.path.join(base, pattern) if isinstance(base, str) and base else pattern)
    if tool in ("Grep", "Glob") and not tool_input.get("path"):
        words.append(".")  # they search the session's folder by default
    command = tool_input.get("command")
    if tool == "Bash" and isinstance(command, str):
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            tokens = list(lexer)
        except ValueError:
            tokens = command.split()
        for token in tokens:
            for part in token.split("="):
                if "/" in part or part[:1] in ("~", "$", "."):
                    words.append(part)
    return words


def resolve(word, cwd):
    for prefix in ("${HOME}", "$HOME"):
        if word.startswith(prefix):
            word = HOME + word[len(prefix) :]
    word = os.path.expanduser(word)
    if not os.path.isabs(word):
        word = os.path.join(cwd, word)
    return os.path.normpath(word).lower()


def escapes_workspace(path, fence, workspace):
    """True if a resolved path can reach the fence outside the workspace."""
    cuts = [path.find(c) for c in GLOB_CHARS if c in path]
    if cuts:
        literal = path[: min(cuts)]
        if literal.startswith(workspace.rstrip("/") + "/"):
            return False  # the glob stays inside the workspace
        return fence.startswith(literal) or under(literal, fence)
    if under(path, workspace):
        return False
    # Inside the fence, or a folder above it that a search would walk through.
    return under(path, fence) or under(fence, path)


def check_fence(tool, tool_input, text, cwd):
    fence = os.path.normpath(os.path.expanduser(FENCE))
    workspace = os.path.normpath(os.path.expanduser(WORKSPACE))
    fence_l, workspace_l = fence.lower(), workspace.lower()
    cwd = os.path.normpath(cwd or os.getcwd())
    reason = "input reaches into ~/Develop outside ~/Develop/rusty-arms"
    if under(cwd.lower(), fence_l) and not under(cwd.lower(), workspace_l):
        block("this session started in ~/Develop outside ~/Develop/rusty-arms")
    if text_escapes_workspace(text, fence, workspace):
        block(reason)
    for word in path_words(tool, tool_input):
        if escapes_workspace(resolve(word, cwd), fence_l, workspace_l):
            block(reason)


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
    tool = data.get("tool_name", "Read")
    if tool not in LAB_CHECKED_TOOLS:
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    if tool in FENCE_CHECKED_TOOLS and isinstance(tool_input, dict):
        check_fence(tool, tool_input, text, data.get("cwd") or "")

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
