#!/usr/bin/env bash
# fast-browser-harness revert: puts agent-workspace.bak back in place of the browser-harness agent workspace, and
# each SKILL.md.bak back in place of its skill file. Anything added to them after the install is lost.
set -euo pipefail
WS="${BH_AGENT_WORKSPACE:-$HOME/.config/browser-harness/agent-workspace}"
SKILL_FILES="$HOME/.claude/skills/browser-harness/SKILL.md ${CODEX_HOME:-$HOME/.codex}/skills/browser-harness/SKILL.md"

[ -d "$WS.bak" ] || { echo "stopped: no backup at $WS.bak. Nothing was changed."; exit 1; }
rm -rf "$WS"
mv "$WS.bak" "$WS"
echo "reverted: $WS is the backup again"
for f in $SKILL_FILES; do
  if [ -f "$f.bak" ]; then
    mv "$f.bak" "$f"
    echo "reverted: $f is the backup again"
  fi
done
