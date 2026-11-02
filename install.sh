#!/usr/bin/env bash
# fast-browser-harness install.
# 1. Stops and changes nothing if a backup from an earlier install is still there.
# 2. Backs up the browser-harness agent workspace to agent-workspace.bak, and each browser-harness skill file to
#    SKILL.md.bak, and checks that every copy is identical. Nothing else changes until all backups are in place.
# 3. Adds fast_all.py and one load line to agent_helpers.py, and a "Fast page reading" section to each skill file.
# Revert with revert.sh. Plugin caches are not edited (browser-harness's install guide says not to).
set -euo pipefail
WS="${BH_AGENT_WORKSPACE:-$HOME/.config/browser-harness/agent-workspace}"
URL="${FAST_BH_URL:-https://raw.githubusercontent.com/<owner>/fast-browser-harness/main}"
SKILL_FILES="$HOME/.claude/skills/browser-harness/SKILL.md ${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"

stop() { echo "stopped: $1"; exit 1; }

# 1. Nothing in the way
[ ! -e "$WS.bak" ] || stop "$WS.bak already exists. Nothing was changed."
for f in $SKILL_FILES; do
  [ ! -e "$f.bak" ] || stop "$f.bak already exists. Nothing was changed."
done

# 2. Back up, and check each copy is identical
mkdir -p "$WS"
cp -Rp "$WS" "$WS.bak"
diff -r "$WS" "$WS.bak" >/dev/null || stop "the backup $WS.bak is not identical. Nothing else was changed."
echo "backup ok, identical copy: $WS.bak"
for f in $SKILL_FILES; do
  if [ -f "$f" ]; then
    cp -p "$f" "$f.bak"
    cmp -s "$f" "$f.bak" || stop "the backup $f.bak is not identical. Nothing else was changed."
    echo "backup ok, identical copy: $f.bak"
  fi
done

# 3. Install
curl -fsSL "$URL/fast_all.py" -o "$WS/fast_all.py"
if ! grep -q '"fast_all.py"' "$WS/agent_helpers.py" 2>/dev/null; then
  echo >> "$WS/agent_helpers.py"
  sed -n 's/^#   \(import os as _o, sys as _s; .*\)$/\1/p' "$WS/fast_all.py" >> "$WS/agent_helpers.py"
fi
echo "installed: $WS/fast_all.py, and one load line at the end of $WS/agent_helpers.py"

found=no
for f in $SKILL_FILES; do
  [ -f "$f" ] || continue
  found=yes
  if ! grep -q "fast-browser-harness: start" "$f"; then
    cat >> "$f" <<'SECTION'

<!-- fast-browser-harness: start -->
## Fast page reading (fast-browser-harness)

`fast_all.py` in the agent workspace adds these helpers. Use them before the accessibility-tree route in "Page Workflow".

- Read the page with `print(snapshot())`. One call returns the visible controls as numbered lines, `[n] role "name" =value state`, then the visible text.
- Let Haiku choose. Give the snapshot and the goal to a Haiku subagent and ask for one line: the number `[n]` to use next, `DONE`, or `STUCK`. Use each answer once. The answer is only ever a number, never a selector or code.
- Act with `click_idx(n)` or `type_idx(n, "text", enter=True)`. If the control is gone, disabled or covered, nothing is clicked: take a new snapshot.
- Wait with `settle()` after input, or `wait_until("<js condition>")` for data, never a fixed sleep. Take a new snapshot after each action.
- `click_name(name)` and `click_text(text)` click by exact name or text. A `[fast recovered] ...` line means the target was found another way; check that step. They click only when exactly one control matches.
- Shadow DOM, iframes and canvas content are not in the snapshot. For those, use "Page Workflow".
<!-- fast-browser-harness: end -->
SECTION
  fi
  echo "added the Fast page reading section to $f"
done
[ "$found" = yes ] || echo "note: no browser-harness skill file in ~/.claude/skills or ~/.codex/skills, so agents are not told about the helpers"
