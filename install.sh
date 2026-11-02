#!/usr/bin/env bash
# fast-browser-harness install: backs up the browser-harness agent workspace to agent-workspace.bak, checks the
# copy is identical, and only then adds fast_all.py and one load line to agent_helpers.py.
# Stops and changes nothing if agent-workspace.bak already exists. Revert with revert.sh.
WS="${BH_AGENT_WORKSPACE:-$HOME/.config/browser-harness/agent-workspace}"
mkdir -p "$WS" \
  && { test ! -e "$WS.bak" || { echo "stopped: $WS.bak already exists. Nothing was changed."; false; }; } \
  && cp -Rp "$WS" "$WS.bak" \
  && diff -r "$WS" "$WS.bak" \
  && echo "backup ok, identical copy: $WS.bak" \
  && curl -fsSL https://raw.githubusercontent.com/<owner>/fast-browser-harness/main/fast_all.py -o "$WS/fast_all.py" \
  && echo >> "$WS/agent_helpers.py" \
  && sed -n 's/^#   \(import os as _o, sys as _s; .*\)$/\1/p' "$WS/fast_all.py" >> "$WS/agent_helpers.py" \
  && echo "installed: $WS/fast_all.py, and one load line at the end of $WS/agent_helpers.py"
