#!/bin/sh
# Install the observer profile into the lab: CLAUDE.md and .claude/settings.json.
# Usage: profiles/lab/install.sh [LAB_DIR]   (default ~/Develop/rusty-arms/ma-lab)
# Never overwrites an existing file; compare and merge by hand instead.
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
lab="${1:-$HOME/Develop/rusty-arms/ma-lab}"

if [ ! -d "$lab" ]; then
  echo "install: $lab does not exist; create the lab first (core's owner checklist, section 3)." >&2
  exit 1
fi

mkdir -p "$lab/.claude"
for f in CLAUDE.md .claude/settings.json; do
  if [ -e "$lab/$f" ]; then
    echo "install: $lab/$f exists; left unchanged. Compare it with $here/$f." >&2
  else
    cp "$here/$f" "$lab/$f"
    echo "install: wrote $lab/$f"
  fi
done

echo "install: done. Commit both files to the lab's local git; never add a remote."
