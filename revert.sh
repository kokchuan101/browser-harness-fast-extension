#!/usr/bin/env bash
# browser-harness-fast-extension revert: puts agent-workspace.bak back in place of the browser-harness agent workspace.
# Anything added to the workspace after the install is lost.
WS="${BH_AGENT_WORKSPACE:-$HOME/.config/browser-harness/agent-workspace}"
test -d "$WS.bak" \
  && rm -rf "$WS" \
  && mv "$WS.bak" "$WS" \
  && echo "reverted: $WS is the backup again"
