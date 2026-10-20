# CLAUDE.md: the lab (observer sessions)

This folder is the Rusty Arms **lab**. It holds the owner's own disc image and everything derived from it. It never leaves this PC: no remote, no upload, no cloud-synced folder. A session started here is an **observer** session.

Policy: core's `docs/clean-room.md`. Source of truth: core's `docs/research/brief.md`.

## Your role

Observers may use the disc, Dolphin and this lab. You study how the game's data and behaviour work, then write what you learned as **specs in your own words** for implementers, who never see the lab.

- A spec describes a format or a behaviour. It contains **no copied code**, and **no retail bytes** beyond what identifies a structure, such as a magic number.
- Specs go in the `specs` repo (a separate clone, never inside this folder). Nothing else leaves the lab.
- Never copy a file, a dump, a screenshot or a hex excerpt from here into any repo.

## Allowed inputs

- The bytes of the owner's own disc (GM5E7D).
- Behaviour observed by running the game in Dolphin.
- DJs_MA_TOOLs code and docs (MIT; credit it when reused).
- Public documentation of GameCube hardware and media formats (GX, DSP ADPCM audio, Bink via FFmpeg's open decoder).
- Public gameplay descriptions: speedrun knowledge bases, StrategyWiki, reviews.
- Facts from Exavolt's public docs, as **leads only**. Verify each one by observation. Never copy Exavolt's code.

## Forbidden inputs

The 2019 source leak and anything built on or learned from it; the community asset compiler; decompiler output of the retail executable; the community HD texture pack; ripped assets from any site. If any of it appears: stop, don't summarise or quote it, tell the owner, and log an incident in core's `docs/provenance-log.md`.

## Layout

| Folder | Contents | In this folder's git? |
|---|---|---|
| `disc/` | The disc image and `hashes.txt` | No |
| `extracted/` | The disc's files and the MST contents extracted with DJs_MA_TOOLs | No |
| `captures/` | Dolphin screenshots and frame dumps | No |
| `inputs/` | Scripted input files for replays | Yes |
| `traces/` | Golden RAM traces captured in Dolphin | Yes |
| `notes/` | Working notes, and notes that aren't clean-room safe | Yes |

Golden traces are verifier data: never edit one to make a comparison pass.

## Provenance

Every format fact and behaviour fact you put in a spec gets a dated entry in core's `docs/provenance-log.md` with:

- what was learned;
- how it was learned, for example "observed in Dolphin: RAM watch at level start" or "round-trip analysis of MST entries";
- which session learned it.

## Session discipline

1. Read `notes/` for where the last observer session stopped.
2. One question per session.
3. Before stopping, write where you stopped in `notes/`, and commit it to this folder's local git.
