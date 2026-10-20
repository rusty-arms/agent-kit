"""Tests for the plugin's hooks. Run with: python3 -m unittest discover -s tests

Each hook runs as a subprocess, exactly as Claude Code runs it, with a
temporary blocklist and lab folder. These tests are verifiers: never weaken
one to make a change pass.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "cleanroom-guard.py")
FORMAT_LINT = os.path.join(ROOT, "hooks", "format-lint.py")
SESSION_START = os.path.join(ROOT, "hooks", "session-start.py")

TERM = "forbidden-example-term"


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = os.path.join(self.tmp.name, "test-lab")
        self.outside = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.lab)
        os.makedirs(self.outside)
        self.blocklist = os.path.join(self.tmp.name, "blocklist.txt")
        with open(self.blocklist, "w", encoding="utf-8") as f:
            f.write(f"# comment\n{TERM}\n")
        self.env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAUDE_CODE_REMOTE", "CLEANROOM_BLOCKLIST_TERMS", "CLAUDE_PROJECT_DIR")
        }
        self.env["CLEANROOM_BLOCKLIST"] = self.blocklist
        self.env["CLEANROOM_LAB"] = self.lab

    def run_hook(self, script, payload, **env):
        result = subprocess.run(
            [sys.executable, script],
            input=json.dumps(payload) if not isinstance(payload, str) else payload,
            capture_output=True,
            text=True,
            env={**self.env, **env},
            check=False,
        )
        return result.returncode, result.stdout, result.stderr


class GuardTests(HookCase):
    def guard(self, tool, tool_input, cwd=None, **env):
        payload = {"tool_name": tool, "tool_input": tool_input, "cwd": cwd or self.outside}
        return self.run_hook(GUARD, payload, **env)[0]

    def test_allows_ordinary_calls(self):
        self.assertEqual(self.guard("WebFetch", {"url": "https://docs.github.com/"}), 0)
        self.assertEqual(self.guard("Bash", {"command": "git status"}), 0)

    def test_blocks_terms_in_reading_tools(self):
        self.assertEqual(self.guard("WebFetch", {"url": f"https://example.com/{TERM}"}), 2)
        self.assertEqual(self.guard("WebSearch", {"query": TERM.upper()}), 2)
        self.assertEqual(self.guard("Bash", {"command": f"git clone https://x/{TERM}"}), 2)

    def test_blocks_terms_in_writes_and_mcp_tools(self):
        self.assertEqual(self.guard("Write", {"file_path": "a.md", "content": TERM}), 2)
        self.assertEqual(self.guard("Edit", {"file_path": "a.md", "new_string": TERM}), 2)
        self.assertEqual(self.guard("mcp__github__search_code", {"query": TERM}), 2)

    def test_terms_from_environment(self):
        os.remove(self.blocklist)
        self.assertEqual(
            self.guard(
                "WebSearch", {"query": "other-term"}, CLEANROOM_BLOCKLIST_TERMS="a,other-term"
            ),
            2,
        )
        self.assertEqual(
            self.guard("WebSearch", {"query": "fine"}, CLEANROOM_BLOCKLIST_TERMS="a,other-term"), 0
        )

    def test_blocks_lab_from_outside(self):
        self.assertEqual(self.guard("Read", {"file_path": os.path.join(self.lab, "x")}), 2)
        self.assertEqual(self.guard("Bash", {"command": "ls ../test-lab"}), 2)
        self.assertEqual(self.guard("Grep", {"pattern": "x", "path": self.lab}), 2)

    def test_blocks_lab_home_forms(self):
        home_lab = os.path.join(os.path.expanduser("~"), "test-home-lab")
        for text in (
            "cat ~/test-home-lab/x",
            "cat $HOME/test-home-lab/x",
            "cat ${HOME}/test-home-lab/x",
        ):
            self.assertEqual(
                self.guard("Bash", {"command": text}, CLEANROOM_LAB="~/test-home-lab"), 2, text
            )
        self.assertEqual(
            self.guard("Bash", {"command": f"cat {home_lab}/x"}, CLEANROOM_LAB="~/test-home-lab"), 2
        )

    def test_allows_lab_from_inside(self):
        inner = os.path.join(self.lab, "notes")
        os.makedirs(inner)
        self.assertEqual(
            self.guard("Read", {"file_path": os.path.join(self.lab, "x")}, cwd=self.lab), 0
        )
        self.assertEqual(self.guard("Bash", {"command": f"ls {self.lab}"}, cwd=inner), 0)

    def test_lab_session_still_blocks_terms(self):
        self.assertEqual(self.guard("WebSearch", {"query": TERM}, cwd=self.lab), 2)

    def test_writes_and_mcp_may_name_the_lab(self):
        self.assertEqual(self.guard("Write", {"file_path": "a.md", "content": self.lab}), 0)
        self.assertEqual(self.guard("mcp__chat__reply", {"text": f"the lab is {self.lab}"}), 0)

    def test_missing_tool_name_is_lab_checked(self):
        payload = {"tool_input": {"file_path": os.path.join(self.lab, "x")}, "cwd": self.outside}
        self.assertEqual(self.run_hook(GUARD, payload)[0], 2)

    def test_fails_closed_without_terms(self):
        os.remove(self.blocklist)
        code, _, err = self.run_hook(
            GUARD, {"tool_name": "Read", "tool_input": {}, "cwd": self.outside}
        )
        self.assertEqual(code, 2)
        self.assertIn("no blocklist terms", err)

    def test_cloud_session_without_terms_only_warns(self):
        os.remove(self.blocklist)
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "README.md"},
            "cwd": self.outside,
        }
        code, _, err = self.run_hook(GUARD, payload, CLAUDE_CODE_REMOTE="true")
        self.assertEqual(code, 0)
        self.assertIn("warning", err)
        payload["tool_input"]["file_path"] = os.path.join(self.lab, "x")
        self.assertEqual(self.run_hook(GUARD, payload, CLAUDE_CODE_REMOTE="true")[0], 2)

    def test_unparseable_input_is_blocked(self):
        self.assertEqual(self.run_hook(GUARD, "not json")[0], 2)


class FormatLintTests(HookCase):
    def lint(self, name, content):
        path = os.path.join(self.outside, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": self.outside}
        return self.run_hook(FORMAT_LINT, payload, CLAUDE_PROJECT_DIR=self.outside)[0]

    def test_json(self):
        self.assertEqual(self.lint("ok.json", '{"a": 1}'), 0)
        self.assertEqual(self.lint("bad.json", "{"), 2)

    def test_python_syntax(self):
        self.assertEqual(self.lint("ok.py", "x = 1\n"), 0)
        self.assertEqual(self.lint("bad.py", "def (:\n"), 2)

    def test_markdown_outside_git_is_skipped(self):
        self.assertEqual(self.lint("a.md", "[x](missing.md)\n"), 0)

    def test_markdown_links_in_a_repo(self):
        subprocess.run(["git", "init", "-q", self.outside], check=True)
        self.assertEqual(self.lint("good.md", "[x](good.md)\n"), 0)
        self.assertEqual(self.lint("bad.md", "[x](missing.md)\n"), 2)

    def test_missing_file_is_ignored(self):
        payload = {"tool_input": {"file_path": os.path.join(self.outside, "none.py")}}
        self.assertEqual(self.run_hook(FORMAT_LINT, payload)[0], 0)


class SessionStartTests(HookCase):
    def start(self, cwd, **env):
        return self.run_hook(SESSION_START, "", CLAUDE_PROJECT_DIR=cwd, **env)

    def test_prints_rules(self):
        code, out, _ = self.start(self.outside)
        self.assertEqual(code, 0)
        self.assertIn("One task per session", out)
        self.assertNotIn("OBSERVER", out)
        self.assertNotIn("WARNING", out)

    def test_marks_lab_sessions_as_observer(self):
        self.assertIn("OBSERVER", self.start(self.lab)[1])

    def test_warns_without_terms(self):
        os.remove(self.blocklist)
        code, out, _ = self.start(self.outside)
        self.assertEqual(code, 0)
        self.assertIn("WARNING", out)


class ManifestTests(unittest.TestCase):
    def load(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            return json.load(f)

    def test_hook_scripts_exist(self):
        hooks = self.load("hooks", "hooks.json")["hooks"]
        for groups in hooks.values():
            for group in groups:
                for hook in group["hooks"]:
                    script = hook["command"].split("${CLAUDE_PLUGIN_ROOT}/", 1)[1].rstrip('"')
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, script)), script)

    def test_guard_covers_reading_writing_and_mcp_tools(self):
        matchers = [g["matcher"] for g in self.load("hooks", "hooks.json")["hooks"]["PreToolUse"]]
        tools = set("|".join(matchers).split("|"))
        for tool in (
            "WebFetch",
            "WebSearch",
            "Bash",
            "Read",
            "Grep",
            "Glob",
            "Edit",
            "Write",
            "mcp__.*",
        ):
            self.assertIn(tool, tools)

    def test_marketplace_points_at_this_plugin(self):
        plugin = self.load(".claude-plugin", "plugin.json")
        market = self.load(".claude-plugin", "marketplace.json")
        self.assertIn(plugin["name"], [p["name"] for p in market["plugins"]])

    def test_lab_profile_enables_the_plugin(self):
        settings = self.load("profiles", "lab", ".claude", "settings.json")
        plugin = self.load(".claude-plugin", "plugin.json")
        market = self.load(".claude-plugin", "marketplace.json")
        self.assertTrue(settings["enabledPlugins"][f"{plugin['name']}@{market['name']}"])


if __name__ == "__main__":
    unittest.main()
