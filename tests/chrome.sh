#!/usr/bin/env bash
# Start or stop a dedicated Chrome for browser-harness: its own profile and port, in the background.
#   tests/chrome.sh start | stop | status
# Then point browser-harness at it: BU_CDP_URL=http://127.0.0.1:9444 BU_NAME=fast-bh browser-harness <<'PY' ... PY
# stop quits only the Chrome that uses this profile, never your daily Chrome.
set -euo pipefail
PORT="${FB_CHROME_PORT:-9444}"
PROFILE="${FB_CHROME_PROFILE:-$HOME/.config/browser-harness-fast-extension/chrome-profile}"
up() { curl -sf "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; }
case "${1:-start}" in
  start)
    if up; then echo "chrome already listening on ${PORT}"; exit 0; fi
    mkdir -p "$PROFILE"
    ARGS=(--remote-debugging-port="$PORT" --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check about:blank)
    if [[ "$(uname)" == "Darwin" ]]; then
      open -g -n -a "Google Chrome" --args "${ARGS[@]}"          # -g: background, keeps your keyboard focus
    else
      BIN="$(command -v google-chrome || command -v chromium || command -v chromium-browser)"
      nohup "$BIN" "${ARGS[@]}" >/dev/null 2>&1 &
    fi
    for _ in $(seq 1 120); do up && { echo "chrome ready on ${PORT}"; exit 0; }; sleep 0.5; done
    echo "chrome did not come up on ${PORT}" >&2; exit 1 ;;
  stop)
    pkill -f -- "--user-data-dir=${PROFILE}" && echo "chrome on ${PORT} closed" || echo "no chrome with this profile" ;;
  status)
    up && echo "chrome listening on ${PORT}" || { echo "chrome not running on ${PORT}"; exit 1; } ;;
  *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
