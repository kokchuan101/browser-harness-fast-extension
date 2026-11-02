#!/usr/bin/env bash
# Test fast_helpers.py and extensions/ in plain browser-harness 0.1.13, without touching your own install or agent workspace.
#   tests/run.sh gate    every helper, with fast_helpers.py loaded by its load line next to an existing agent_helpers.py
#   tests/run.sh extensions   each extensions/*.py file alone, then all four together
#   tests/run.sh bench   accessibility-tree route vs snapshot() on Wikipedia, GitHub and MDN
# browser-harness 0.1.13 runs from its own venv, each run uses a temporary BH_HOME (config, daemon files, agent
# workspace) and its own daemon name, and the Chrome from tests/chrome.sh on port 9444. Stop it: tests/chrome.sh stop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${FAST_CACHE:-$HOME/.cache/fast-browser-harness}/upstream-venv"
BH="$VENV/bin/browser-harness"
export FB_OUT="${FB_OUT:-/tmp/fast-browser-harness-out}" BH_TELEMETRY=0 BU_NAME=fast-bh
export BU_CDP_URL="${FAST_CDP_URL:-http://127.0.0.1:9444}"   # never inherit BU_CDP_URL: it may point at a shared Chrome

in_home() {   # in_home SCRIPT: run SCRIPT with a fresh temporary BH_HOME, stop its daemon, remove the folder
  local script="$1" home rc=0; home="$(mktemp -d /tmp/fbh.XXXXXX)"; mkdir -p "$home/agent-workspace"  # short path: socket limit
  if [ -n "${AGENT_HELPERS:-}" ]; then cat $AGENT_HELPERS > "$home/agent-workspace/agent_helpers.py"; fi
  if [ -n "${WORKSPACE_FILES:-}" ]; then cp $WORKSPACE_FILES "$home/agent-workspace/"; fi
  BH_HOME="$home" "$BH" < "$script" || rc=$?
  BH_HOME="$home" "$BH" --reload >/dev/null 2>&1 || true
  rm -rf "$home"; return $rc
}

python3 "$ROOT/tests/build_extensions.py" --check
[ -x "$BH" ] || { uv venv -q "$VENV" && uv pip install -q --python "$VENV/bin/python" "browser-harness==0.1.13"; }
"$ROOT/tests/chrome.sh" start
case "${1:-}" in
  gate|bench)   # fast_helpers.py next to an agent_helpers.py that has its own helper, loaded by the header's load line
    lines="$(mktemp)"; printf 'def my_own_helper():\n    return "mine"\n\n' > "$lines"
    sed -n 's/^#   \(import os as _o, sys as _s; .*\)$/\1/p' "$ROOT/fast_helpers.py" >> "$lines"
    AGENT_HELPERS="$lines" WORKSPACE_FILES="$ROOT/fast_helpers.py" in_home "$ROOT/tests/$1.py" || true
    rm -f "$lines" ;;
  extensions)
    out="$(mktemp)"
    for p in frame_wait indexed_map click_repair marked_shot all; do
      if [ "$p" = all ]; then files="$ROOT/extensions/frame_wait.py $ROOT/extensions/indexed_map.py $ROOT/extensions/click_repair.py $ROOT/extensions/marked_shot.py"
      else files="$ROOT/extensions/$p.py"; fi
      EXT=$p AGENT_HELPERS="$files" in_home "$ROOT/tests/extensions_check.py" 2>&1 | tee -a "$out" || true
    done
    echo "EXTENSIONS $(grep -c '^PASS' "$out")/$(grep -cE '^(PASS|FAIL)' "$out")"; rm -f "$out" ;;
  *) echo "usage: $0 gate|extensions|bench" >&2; exit 2 ;;
esac
