# agent-kit

Guard rails for Claude Code sessions on the Rusty Arms project, packaged as a Claude Code plugin. Install it once and every session gets the same clean-room guard, format/lint checks, session rules and reviewer, whichever repo it starts in.

Project policy lives in core: [clean-room policy](https://github.com/rusty-arms/core/blob/main/docs/clean-room.md), [guard setup](https://github.com/rusty-arms/core/blob/main/docs/setup/claude-guard.md) and [project status](https://github.com/rusty-arms/core/blob/main/PROGRESS.md).

## What it contains

| Part | File | What it does |
|---|---|---|
| Clean-room guard | [`hooks/cleanroom-guard.py`](hooks/cleanroom-guard.py) | `PreToolUse` hook. Blocks any tool call whose input contains a blocklist term, including writes and MCP tools. Blocks reading tools (`Bash`, `Read`, `Grep`, `Glob`, `WebFetch`, `WebSearch`) that touch the lab, unless the session started inside the lab. Blocks local reading tools (`Bash`, `Read`, `Grep`, `Glob`) from anything in `~/Develop` outside `~/Develop/rusty-arms`, including searches that would walk into it from above, such as `find /`. Fails closed when it has no terms. |
| Format and lint | [`hooks/format-lint.py`](hooks/format-lint.py) | `PostToolUse` hook on `Edit` and `Write`. Formats and lints Python with `ruff` when installed (otherwise checks syntax), lints YAML with `yamllint` when installed, checks that JSON parses and that Markdown links resolve. |
| Session rules | [`hooks/session-start.py`](hooks/session-start.py) | `SessionStart` hook. Adds the session discipline and short clean-room rules to every session, marks lab sessions as observer sessions, and warns when the guard has no blocklist terms. |
| Reviewer | [`agents/reviewer.md`](agents/reviewer.md) | Read-only Sonnet subagent that checks work against evidence: the brief, the specs, the provenance log, the tests. |
| Lab profile | [`profiles/lab/`](profiles/lab/) | `CLAUDE.md` and `.claude/settings.json` for the lab, so sessions there run as observers. |

The hooks use the Python standard library only.

## Install

### 1. Create the blocklist first

The guard blocks every guarded tool call until it has blocklist terms, so create them before installing. Follow step 1 of core's [guard setup](https://github.com/rusty-arms/core/blob/main/docs/setup/claude-guard.md): one lower-case term per line in `~/.claude/cleanroom-blocklist.txt`. Cloud environments use the `CLEANROOM_BLOCKLIST_TERMS` variable instead. The terms are never committed anywhere.

### 2. Install the plugin for your user

Install at user scope, so sessions started outside a project repo are guarded too. In Claude Code:

```text
/plugin install agent-kit --marketplace rusty-arms/agent-kit
```

Or from a shell:

```sh
claude plugin marketplace add rusty-arms/agent-kit
claude plugin install agent-kit@rusty-arms --scope user
```

Restart Claude Code. The first message of a new session should include "Rusty Arms session rules". To update later: `claude plugin marketplace update rusty-arms`, then restart.

A project repo can also enable the plugin for everyone who opens it, by adding this to its `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "rusty-arms": { "source": { "source": "github", "repo": "rusty-arms/agent-kit" } }
  },
  "enabledPlugins": { "agent-kit@rusty-arms": true }
}
```

### 3. Install the lab profile

After creating the lab (section 3 of core's [owner checklist](https://github.com/rusty-arms/core/blob/main/docs/setup/owner-checklist.md)), run from a clone of this repo:

```sh
profiles/lab/install.sh                # default ~/Develop/rusty-arms/ma-lab
profiles/lab/install.sh /path/to/lab   # or another lab folder
```

It copies `CLAUDE.md` and `.claude/settings.json` into the lab and never overwrites an existing file. Commit both to the lab's local git. The settings enable this plugin for the lab and deny network, push and remote commands, and edits to the profile and to golden traces.

### Settings

| Variable | Default | Use |
|---|---|---|
| `CLEANROOM_BLOCKLIST` | `~/.claude/cleanroom-blocklist.txt` | Blocklist file. |
| `CLEANROOM_BLOCKLIST_TERMS` | unset | Comma-separated terms, for cloud environments. |
| `CLEANROOM_LAB` | `~/Develop/rusty-arms/ma-lab` | The lab folder. |
| `CLEANROOM_FENCE` | `~/Develop` | The folder sessions may not look through, apart from the workspace. |
| `CLEANROOM_WORKSPACE` | `~/Develop/rusty-arms` | The one place inside the fence that sessions may read. |

The fence applies to every session with the plugin enabled, wherever it starts. A session started in another project under `~/Develop` is blocked from reading anything. To work on such a project with Claude Code, turn the plugin off for it in that project's `.claude/settings.json`: `"enabledPlugins": { "agent-kit@rusty-arms": false }`.

## Develop

```sh
python3 -m unittest discover -s tests   # run every hook as Claude Code runs it
python3 scripts/check_no_retail.py --all
python3 scripts/check_links.py
yamllint -s .
claude plugin validate .
```

CI runs the first four on every push and pull request. `.githooks/pre-commit` runs the retail-data guard; enable it with `git config core.hooksPath .githooks`.

## Licence

MIT OR Apache-2.0, at your option: [LICENSE-MIT](LICENSE-MIT), [LICENSE-APACHE](LICENSE-APACHE).
