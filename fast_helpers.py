# browser-harness-fast-extension: faster page reading for browser-harness, in one file.
# Put this file in your browser-harness agent workspace ($BH_AGENT_WORKSPACE, by default
# ~/.config/browser-harness/agent-workspace/) and load it from agent_helpers.py with this line:
#   import os as _o, sys as _s; _f = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "fast_helpers.py"); exec(compile(open(_f).read(), _f, "exec")) if _o.path.exists(_f) else print("browser-harness-fast-extension: fast_helpers.py not found, fast helpers not loaded", file=_s.stderr)
# Tested with browser-harness 0.1.13. Technique from jev-ultrafast (github.com/browser-use/jev-ultrafast).
# The "# --- extension:" markers cut this file into the single extensions in extensions/ (tests/build_extensions.py).
#
# HOW TO USE (for the agent driving the browser)
# - Read the page with print(snapshot()): one JavaScript call returns the visible controls in the viewport as
#   numbered lines, `[n] role "name" =value state`, then the visible text. Prefer it to the accessibility tree and
#   to screenshots. Shadow DOM, iframes and canvas content are not in it: when the target is not in the map, fall
#   back to browser-harness's original route (the accessibility tree, the box of the node, click_at_xy).
# - Let a Haiku subagent select the index: give it the snapshot and the goal, and ask for one line: [n], DONE or
#   STUCK. If Haiku fails, ask a stronger LLM. Use each answer once. The answer is only a number, never code.
# - Act by number: click_idx(n), or type_idx(n, "text", enter=True). A number is valid only for the last snapshot
#   on that page. If its node is gone, disabled or covered, the call raises an error and clicks nothing.
# - Wait on the page, never with a fixed sleep: settle() after input (two animation frames, at most 50 ms), or
#   wait_until("<js condition>") for data that loads. click_idx and type_idx already call settle().
# - Take a new snapshot after each action. Stop after three actions in a row that change nothing.
# - click_name(name) and click_text(text) click by exact name or text. A "[fast recovered] ..." line means the
#   target was found another way (more time under load, another case, the visible text, and last the
#   accessibility tree); check that step.
# - capture_marked(path, [{"idx": n, "note": "..."}]) saves a screenshot with boxes on controls.

# --- extension: core
import json as _fast_json
import time as _fast_time

from browser_harness.helpers import cdp as _fast_cdp, js as _fast_js

# Installed once per page as window.__fast. Item numbers [n] point at a WeakMap id for the DOM node, so a click
# re-finds the same node, never a new one at the same position. Shadow DOM and iframes are not searched.
_FAST_LIB = r"""
(() => {
  if (window.__fast && window.__fast.v === 1) return window.__fast;
  const ROLES = ['button','link','checkbox','radio','switch','tab','menuitem','menuitemcheckbox','menuitemradio',
                 'option','combobox','textbox','searchbox','spinbutton','gridcell','treeitem','row','slider'];
  const SEL = 'a[href],button,input,textarea,select,summary,[contenteditable=true],' + ROLES.map(r => '[role=' + r + ']').join(',');
  const ids = new WeakMap(), nodes = new Map();
  let next = 1;
  const f = {v: 1, last: []};
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  f.vis = e => !e.closest('[aria-hidden=true],[inert]') && e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
  f.usable = e => !['hidden','file'].includes(e.type) && f.vis(e) && !e.matches(':disabled') && !e.closest('[aria-disabled=true]');
  f.name = e => clean(e.getAttribute('aria-label') ||
      (e.getAttribute('aria-labelledby') || '').split(/\s+/).map(i => document.getElementById(i)?.innerText || '').join(' ') ||
      [...(e.labels || [])].map(l => l.innerText).join(' ') || (e.tagName === 'INPUT' ? '' : e.innerText) ||
      (['button','submit','reset'].includes(e.type) ? e.value : '') ||
      e.getAttribute('title') || e.getAttribute('placeholder') || e.getAttribute('alt') || '').slice(0, 80);
  f.role = e => { const r = e.getAttribute('role'); if (r) return r; const t = e.tagName;
    if (t === 'A') return 'link'; if (t === 'BUTTON' || t === 'SUMMARY') return 'button';
    if (t === 'SELECT') return 'combobox'; if (t === 'TEXTAREA' || e.isContentEditable) return 'textbox';
    if (t === 'INPUT') return ['checkbox','radio'].includes(e.type) ? e.type :
      ['button','submit','reset','image'].includes(e.type) ? 'button' : e.type === 'search' ? 'searchbox' : 'textbox';
    return t.toLowerCase(); };
  f.box = e => { const r = e.getBoundingClientRect(); return r.width && r.height ? r : null; };
  f.inView = r => { const x = r.x + r.width / 2, y = r.y + r.height / 2; return x >= 0 && y >= 0 && x < innerWidth && y < innerHeight; };
  f.controls = () => [...document.querySelectorAll(SEL)].filter(e => f.usable(e) && f.box(e));
  f.id = e => { if (!ids.has(e)) ids.set(e, next++); const i = ids.get(e); nodes.set(i, e); return i; };
  f.state = e => {
    let st = '';
    if (e.type === 'password') st += ' (password)';
    else if ('value' in e && !['BUTTON','LI','OPTION'].includes(e.tagName) && e.value) st += ' =' + JSON.stringify(String(e.value).slice(0, 60));
    if (e.type === 'checkbox' || e.type === 'radio') st += e.checked ? ' (checked)' : ' (unchecked)';
    for (const k of ['expanded','selected','checked']) { const v = e.getAttribute('aria-' + k); if (v !== null) st += ' ' + k + '=' + v; }
    return st;
  };
  f.snapshot = maxText => {
    for (const [i, e] of nodes) if (!e.isConnected) nodes.delete(i);
    const lines = [], last = [];
    for (const e of f.controls()) {
      if (!f.inView(f.box(e))) continue;
      last.push(f.id(e));
      lines.push('[' + last.length + '] ' + f.role(e) + ' "' + f.name(e) + '"' + f.state(e));
    }
    f.last = last;
    let text = '';
    if (maxText > 0) {
      const words = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), rg = document.createRange();
      let n, len = 0;
      while ((n = w.nextNode()) && len < maxText) {
        const v = n.textContent.trim(), p = n.parentElement;
        if (!v || !p || p.closest('script,style,noscript,template') || !f.vis(p)) continue;
        rg.selectNodeContents(n); const r = rg.getBoundingClientRect();
        if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth) { words.push(v); len += v.length + 1; }
      }
      text = words.join('\n').slice(0, maxText);
    }
    return [location.pathname + location.search + ' | ' + document.title].concat(lines).join('\n') +
           (text ? '\n--- visible text ---\n' + text : '');
  };
  f.item = n => {
    const id = f.last[n - 1];
    if (!id) return {error: 'no item [' + n + '] in the last snapshot on this page: call snapshot() again'};
    const e = nodes.get(id);
    if (!e || !e.isConnected) return {error: 'stale: item [' + n + '] is gone, call snapshot() again'};
    return {el: e};
  };
  // Where to click e: scroll it into view when needed, then check that the point really hits e (not an overlay).
  f.point = e => {
    if (!e.isConnected) return {error: 'stale: the element is gone'};
    if (e.matches(':disabled') || e.closest('[aria-disabled=true],[inert]') || !f.vis(e)) return {error: 'not clickable now (hidden or disabled)'};
    let r = f.box(e);
    if (!r) return {error: 'not clickable now (no size)'};
    if (r.top < 0 || r.bottom > innerHeight || r.left < 0 || r.right > innerWidth) { e.scrollIntoView({block: 'center', inline: 'nearest'}); r = f.box(e); }
    const x = r.x + r.width / 2, y = r.y + r.height / 2, hit = document.elementFromPoint(x, y);
    if (!hit || !(e === hit || e.contains(hit) || hit.contains(e))) return {error: 'covered by ' + (hit ? hit.tagName.toLowerCase() : 'nothing')};
    return {x, y, role: f.role(e), name: f.name(e)};
  };
  // Controls by accessible name: mode 'exact' or 'ci' (same text, any case). Never a substring.
  f.byName = (name, role, mode) => f.controls().filter(e => (!role || f.role(e) === role) &&
      (mode === 'ci' ? f.name(e).toLowerCase() === name.toLowerCase() : f.name(e) === name));
  // Innermost visible elements whose whole text is `text`: mode 'exact' or 'ci'. Never a substring.
  f.byText = (text, within, selector, mode) => {
    const root = within ? document.querySelector(within) : document;
    if (!root) return null;
    const t = e => clean(e.innerText !== undefined ? e.innerText : e.textContent);
    const match = e => mode === 'ci' ? t(e).toLowerCase() === text.toLowerCase() : t(e) === text;
    const els = [...root.querySelectorAll(selector || '*')].filter(e => f.box(e) && f.vis(e) && match(e));
    return els.filter(e => !els.some(o => o !== e && e.contains(o)));
  };
  return window.__fast = f;
})()
"""


def _fast_call(body, *args):
    """Run `body`, a JS function of (lib, ...args), in the page in one evaluate; return its JSON value."""
    return _fast_js("((f, ...a) => (%s)(f, ...a))(%s, %s)"
                    % (body, _FAST_LIB, ", ".join(_fast_json.dumps(a) for a in args)))


def _fast_focus():
    """Turn on focus emulation for the attached tab. In a hidden background tab some pages ignore clicks and no
    animation frames run until the page believes it has focus (GitHub's tabs, for example)."""
    try:
        if _fast_js("document.hasFocus()"):
            return
        _fast_cdp("Emulation.setFocusEmulationEnabled", enabled=True)
        _fast_cdp("Runtime.evaluate", awaitPromise=True, expression=(          # let the page react to the focus change
            "new Promise(r => { requestAnimationFrame(() => requestAnimationFrame(r)); setTimeout(r, 100); })"))
    except Exception:
        pass


def _fast_after_action():
    """Wait on the page with settle() when it is loaded (fast_helpers.py, or the frame_wait extension); otherwise do nothing."""
    fn = globals().get("settle")
    if fn:
        fn()
# --- end extension


# --- extension: frame_wait
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
# --- end extension


# --- extension: indexed_map
from browser_harness.helpers import click_at_xy as _fast_click_at_xy


def snapshot(text=True, max_text=6000):
    """The page as an indexed map, in one JavaScript call: a first line `path | title`, then one line per visible,
    enabled control in the viewport, `[n] role "name" =value state`, then the visible text (at most max_text chars)
    when text=True. A password field shows `(password)`, never its value. Act on a line with click_idx(n) or
    type_idx(n, text). Shadow DOM, iframes and canvas content are not in the map."""
    return _fast_call("(f, m) => f.snapshot(m)", max_text if text else 0)


def click_idx(n, timeout=1.5):
    """Real mouse click on item [n] of the last snapshot() on this page (it still works in a later browser-harness
    call, until the page navigates). It re-checks the node first: gone, disabled or covered by another element means
    no click and an error. Retries up to `timeout` s while the node is briefly hidden or covered, then waits with
    settle() when it is loaded. Returns {'x', 'y', 'role', 'name'} of what it clicked."""
    end = _fast_time.time() + timeout
    while True:
        p = _fast_call("(f, n) => { const it = f.item(n); return it.error ? it : f.point(it.el); }", n)
        if p and "error" not in p:
            break
        err = (p or {}).get("error", "no result")
        if ("not clickable" not in err and "covered" not in err) or _fast_time.time() > end:
            raise RuntimeError("click_idx(%d): %s" % (n, err))
        _fast_time.sleep(0.1)
    _fast_focus()
    _fast_click_at_xy(p["x"], p["y"])
    _fast_after_action()
    return p


def type_idx(n, text, replace=True, enter=False):
    """Click item [n] of the last snapshot() to focus it, then type `text`. replace=True first selects the field's
    content with the browser's selectAll editing command, so the text replaces it. enter=True presses Enter after
    typing. Returns the value of the focused field after typing."""
    click_idx(n)
    if replace:
        mod = 4 if "Mac" in (_fast_cdp("Browser.getVersion").get("userAgent") or "") else 2
        key = dict(key="a", code="KeyA", windowsVirtualKeyCode=65, modifiers=mod)
        _fast_cdp("Input.dispatchKeyEvent", type="rawKeyDown", commands=["selectAll"], **key)
        _fast_cdp("Input.dispatchKeyEvent", type="keyUp", **key)
    _fast_cdp("Input.insertText", text=text)
    _fast_after_action()
    value = _fast_js("(e => e && ('value' in e ? e.value : e.innerText))(document.activeElement)")
    if enter:
        from browser_harness.helpers import press_key as _fast_press_key
        _fast_press_key("Enter")
        _fast_after_action()
    return value
# --- end extension


# --- extension: click_repair
import os as _fast_os

from browser_harness.helpers import click_at_xy as _fast_click_at_xy

# When the target is not found in time, click_name and click_text try other ways to find the same control. A way
# that finds exactly one control is used and prints one "[fast recovered]" line. A way that finds several stops
# with an error, because a guess could click the wrong control. Matching is never by substring. The last way is
# browser-harness's original route: the accessibility tree and the box of the match.


def _fast_loaded():
    """True when the 1-minute load average is above the number of cores: pages render late, so waits run out."""
    try:
        return _fast_os.getloadavg()[0] > (_fast_os.cpu_count() or 4)
    except OSError:
        return False


def _fast_pick(body, args, index):
    """Run a finder in the page: (match count, click point or None, error). With index=None the point is set only
    when exactly one control matches."""
    r = _fast_call("(f, idx, ...a) => { const els = (%s)(f, ...a) || [];"
                   " const e = idx === null ? (els.length === 1 ? els[0] : null) : els.at(idx);"
                   " return Object.assign({count: els.length}, e ? f.point(e) : {}); }" % body, index, *args)
    return r["count"], (r if "x" in r else None), r.get("error")


def _fast_find_click(helper, label, body, args, index, timeout, recoveries):
    end, waited = _fast_time.time() + timeout, False
    while True:
        count, point, err = _fast_pick(body, args, index)
        if point:
            break
        if count > 1 and index is None:
            raise RuntimeError("%s(%s): %d controls match, so nothing was clicked; pass index= or use snapshot()"
                               % (helper, label, count))
        if _fast_time.time() > end:
            if not waited and _fast_loaded():                       # one more timeout when the machine is busy
                end, waited = _fast_time.time() + timeout, True
                continue
            reason = err or "not found within %s s" % timeout
            for how, rbody, rargs in (recoveries if index in (None, 0) else ()):
                if callable(rbody):
                    rcount, rpoint = rbody(*rargs)
                else:
                    rcount, rpoint, _ = _fast_pick(rbody, rargs, None)
                if rpoint:
                    print("[fast recovered] %s(%s): %s. Check this step's result." % (helper, label, how))
                    _fast_focus()
                    _fast_click_at_xy(rpoint["x"], rpoint["y"])
                    _fast_after_action()
                    return dict(rpoint, recovered=how)
                if rcount > 1:
                    raise RuntimeError("%s(%s): %s; %s finds %d controls, so nothing was clicked"
                                       % (helper, label, reason, how, rcount))
            raise RuntimeError("%s(%s): %s" % (helper, label, reason))
        _fast_time.sleep(0.1)
    if waited:
        print("[fast recovered] %s(%s): found after waiting longer under load. Check this step's result." % (helper, label))
    _fast_focus()
    _fast_click_at_xy(point["x"], point["y"])
    _fast_after_action()
    return dict(point, recovered="found after waiting longer under load") if waited else point


_FAST_AX_ROLES = {"button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "option", "combobox",
                  "textbox", "searchbox", "spinbutton"}


def _fast_ax_find(name, role):
    """browser-harness's original route, the last fallback: the accessibility tree, then the box of the match.
    It also finds controls inside shadow DOM, which the page map cannot see. Returns (match count, point or None)."""
    hits = []
    for n in _fast_cdp("Accessibility.getFullAXTree")["nodes"]:
        r = (n.get("role") or {}).get("value")
        if n.get("ignored") or not n.get("backendDOMNodeId") or ((n.get("name") or {}).get("value") or "").strip() != name:
            continue
        if (role and r != role) or (not role and r not in _FAST_AX_ROLES):
            continue
        hits.append((r, n["backendDOMNodeId"]))
    if len(hits) != 1:
        return len(hits), None
    try:
        _fast_cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=hits[0][1])
        q = _fast_cdp("DOM.getBoxModel", backendNodeId=hits[0][1])["model"]["content"]
    except Exception:
        return 1, None
    return 1, {"x": sum(q[0::2]) / 4, "y": sum(q[1::2]) / 4, "role": hits[0][0], "name": name}


_FAST_BY_NAME = "(f, name, role, mode) => f.byName(name, role, mode)"
_FAST_BY_TEXT = "(f, text, within, selector, mode) => f.byText(text, within, selector, mode)"


def click_name(name, role=None, index=None, timeout=10):
    """Real click on the visible, enabled control whose accessible name is exactly `name` (and whose role is
    `role`, when given), scrolled into view and checked for overlays. With several matches it clicks nothing and
    raises, unless you pass index= (0 is the first in page order). Retries until `timeout` s while the page renders.
    If nothing matches, it tries, in order: more time when the machine is loaded, the same name in another case,
    the same visible text, then browser-harness's original route (the accessibility tree, which also reaches shadow
    DOM). It clicks only on exactly one match and prints a '[fast recovered]' line."""
    label = ", ".join([repr(name)] + (["role=%r" % role] if role else []))
    return _fast_find_click("click_name", label, _FAST_BY_NAME, (name, role, "exact"), index, timeout, [
        ("found by its name in another case", _FAST_BY_NAME, (name, role, "ci")),
        ("found by its visible text", _FAST_BY_TEXT, (name, None, None, "exact")),
        ("found in the accessibility tree", _fast_ax_find, (name, role)),
    ])


def click_text(text, within=None, selector=None, index=None, timeout=10):
    """Real click on the innermost visible element whose whole text is exactly `text`. within: CSS selector of a
    container (a dialog); selector: limit to e.g. 'button'. Use it for targets that have no accessible role.
    Same rules as click_name: several matches raise unless index= is given. The recovery tries more time under load,
    the same text in another case, the accessible name, then the accessibility tree, and clicks only on exactly one
    match."""
    label = ", ".join([repr(text)] + ["%s=%r" % kv for kv in (("within", within), ("selector", selector)) if kv[1]])
    rec = [("found by its text in another case", _FAST_BY_TEXT, (text, within, selector, "ci"))]
    if not within and not selector:
        rec.append(("found by its accessible name", _FAST_BY_NAME, (text, None, "exact")))
        rec.append(("found in the accessibility tree", _fast_ax_find, (text, None)))
    return _fast_find_click("click_text", label, _FAST_BY_TEXT, (text, within, selector, "exact"), index, timeout, rec)
# --- end extension


# --- extension: marked_shot
import os as _fast_os

from browser_harness.helpers import capture_screenshot as _fast_capture_screenshot

_FAST_MARKS_JS = r"""
(f, marks, pad) => {
  const find = m => {
    if (m.idx) { const it = f.item(m.idx); return it.error ? null : it.el; }
    if (m.css) return [...document.querySelectorAll(m.css)].find(e => f.box(e)) || null;
    const els = f.byText(m.text, m.within, m.selector, 'exact');
    return els && els.length ? els[0] : null;
  };
  document.getElementById('__fast_marks')?.remove();
  const layer = document.createElement('div');
  layer.id = '__fast_marks';
  layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  const missing = [];
  marks.forEach((m, i) => {
    const e = find(m);
    if (!e) { missing.push(m.css || m.text || (m.idx ? '[' + m.idx + ']' : String(i + 1))); return; }
    const r = e.getBoundingClientRect();
    const box = document.createElement('div');
    box.style.cssText = `position:fixed;left:${r.left - pad}px;top:${r.top - pad}px;width:${r.width + 2 * pad}px;` +
      `height:${r.height + 2 * pad}px;border:3px dashed #e5484d;border-radius:4px;box-sizing:border-box`;
    layer.appendChild(box);
    if (m.note) {
      const chip = document.createElement('div');
      chip.textContent = m.note;
      const top = r.top - pad - 24 >= 0 ? r.top - pad - 24 : r.bottom + pad + 2;
      chip.style.cssText = `position:fixed;left:${Math.max(0, r.left - pad)}px;top:${top}px;background:#e5484d;color:#fff;` +
        'font:600 12px/18px system-ui,sans-serif;padding:2px 6px;border-radius:3px;white-space:nowrap';
      layer.appendChild(chip);
    }
  });
  document.body.appendChild(layer);
  return missing;
}
"""


def capture_marked(path, marks, pad=6):
    """Viewport screenshot with red dashed boxes on the given elements, as evidence a person can read.
    marks: a list of {'idx': n} (item [n] of the last snapshot()), {'css': selector} or {'text': exact visible
    text, optional 'within' and 'selector'}, each with an optional 'note' label. The boxes are a page overlay,
    removed after the shot. Returns {'path', 'marked', 'missing'}."""
    path = _fast_os.path.abspath(_fast_os.path.expanduser(path))
    _fast_os.makedirs(_fast_os.path.dirname(path), exist_ok=True)
    try:
        missing = _fast_call(_FAST_MARKS_JS, marks, pad) or []
        _fast_after_action()
        _fast_capture_screenshot(path)
    finally:
        _fast_js("document.getElementById('__fast_marks')?.remove()")
    return {"path": path, "marked": len(marks) - len(missing), "missing": missing}
# --- end extension
