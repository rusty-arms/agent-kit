# CLAUDE.md: agent-kit

## What this repo is

`agent-kit` is the Rusty Arms Claude Code plugin: the clean-room guard, the format/lint hook, the session rules, the reviewer subagent and the lab's observer profile. See [README.md](README.md).

It holds **no code from the original game and no game data**, and it never will. Project policy, decisions and status live in `core`: `docs/clean-room.md`, `docs/decisions/`, `PROGRESS.md`.

## Clean-room rules (short form)

- **Never** access, search for, fetch, clone or read: the 2019 source leak or anything built on it; the community asset compiler; archive copies of the source or prototype discs; the community HD texture pack; decompiler output of the retail executable.
- **Never** read anything in the lab (`~/Develop/rusty-arms/ma-lab`).
- If forbidden material appears anyway: stop, don't summarise or quote it, tell the owner, and log an incident in core's `docs/provenance-log.md`.
- **Never commit** retail game data, disc images, extracted files, screenshots or captures of the game, anything from the lab, or blocklist terms. Test fixtures use made-up terms such as `forbidden-example-term`.
- In committed files, describe forbidden material generically.

## Session discipline

1. Start by reading core's `PROGRESS.md` and this repo's `git log -10`.
2. One task per session.
3. Make small commits, one per step.
4. Record where you stopped in core's `PROGRESS.md` (agent-kit row) before ending the session.

## Approval

Changes to `.github/`, to `hooks/cleanroom-guard.py` and to `tests/` need the owner's explicit approval in the chat. The guard and its tests are what every other repo relies on.

## Guard rails

- **Never weaken** the guard, its tests, `scripts/check_no_retail.py`, `.githooks/` or `.github/workflows/guard.yml` to make a check pass. A change to the guard comes with tests that show the stronger behaviour.
- Do not route around a blocked tool call. A block is the answer; report it.
- `scripts/check_no_retail.py` and `scripts/check_links.py` are copies of core's. Change them in core first, then copy them here unchanged.
- This repo's `.claude/settings.json` runs the hooks from the working tree, so you test your own changes as you make them. If the plugin is also installed for your user, each hook runs twice; that is harmless.

## Layout

- `.claude-plugin/`: `plugin.json` and the `rusty-arms` marketplace.
- `hooks/`: `hooks.json` and the three hook scripts (standard library only).
- `agents/reviewer.md`: the read-only reviewer.
- `profiles/lab/`: the observer profile and its install script.
- `tests/test_hooks.py`: runs each hook as a subprocess, with a temporary blocklist and lab.
- `scripts/`: the retail-data guard and link checker, copied from core.

## Checks

```sh
python3 -m unittest discover -s tests
python3 scripts/check_no_retail.py --all
python3 scripts/check_links.py
yamllint -s .
claude plugin validate .
```
