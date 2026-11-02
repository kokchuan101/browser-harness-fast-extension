# browser-harness-fast-extension extension: frame_wait. settle() and wait_until(js): wait on the page instead of a fixed sleep.
# Paste this whole file at the end of your browser-harness agent_helpers.py ($BH_AGENT_WORKSPACE, by default
# ~/.config/browser-harness/agent-workspace/agent_helpers.py). It needs no other extension.
# Tested with browser-harness 0.1.13. Generated from fast_helpers.py by tests/build_extensions.py; edit fast_helpers.py,
# not this file. Technique from jev-ultrafast (github.com/browser-use/jev-ultrafast).
import time as _fast_time

from browser_harness.helpers import cdp as _fast_cdp, js as _fast_js

_FAST_SETTLE_JS = r"""
((frames, cap, wantOptions, optCap) => new Promise(res => {
  let n = 0, done = false; const fin = v => { if (!done) { done = true; res(v); } };
  setTimeout(() => fin('cap'), wantOptions ? optCap : cap);
  const shown = e => { const r = e.getBoundingClientRect(); return r.width && r.height && r.bottom > 0 && r.top < innerHeight; };
  const tick = () => {
    if (done) return;
    n++;
    if (n >= frames && (!wantOptions || [...document.querySelectorAll('[role=option]')].some(shown))) fin('ready');
    else requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}))(%d, %d, %s, %d)
"""


def settle(frames=2, cap_ms=50, options=False, options_cap_ms=200):
    """Wait until the page has drawn `frames` animation frames (at most cap_ms), or with options=True until a
    role=option is visible (at most options_cap_ms: suggestions under a typed combobox). Use it after input instead
    of a fixed sleep. It turns on focus emulation first: without it, a background tab draws no frames. It does not
    wait for network data: follow it with wait_until(<js condition>). Returns 'ready', or 'cap' when the cap ran out."""
    try:
        _fast_cdp("Emulation.setFocusEmulationEnabled", enabled=True)
    except Exception:
        pass
    r = _fast_cdp("Runtime.evaluate", awaitPromise=True, returnByValue=True,
                  expression=_FAST_SETTLE_JS % (frames, cap_ms, "true" if options else "false", options_cap_ms))
    return (r.get("result") or {}).get("value")


def wait_until(expr, timeout=30, interval=0.1):
    """Poll a JS expression until it is truthy and return its value, or None on timeout. Errors while the page
    navigates count as 'not yet'. A DOM element comes back as {} (false in Python): test '!!document.querySelector(...)'."""
    end = _fast_time.time() + timeout
    while True:
        try:
            v = _fast_js(expr)
            if v:
                return v
        except Exception:
            pass
        if _fast_time.time() >= end:
            return None
        _fast_time.sleep(interval)
