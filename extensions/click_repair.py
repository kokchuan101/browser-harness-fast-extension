# fast-browser-harness extension: click_repair. click_name(name) and click_text(text): exact clicks that repair a miss safely.
# Paste this whole file at the end of your browser-harness agent_helpers.py ($BH_AGENT_WORKSPACE, by default
# ~/.config/browser-harness/agent-workspace/agent_helpers.py). Add frame_wait.py too, so clicks wait on the page; without it they do not wait.
# Tested with browser-harness 0.1.13. Generated from fast_helpers.py by tests/build_extensions.py; edit fast_helpers.py,
# not this file. Technique from jev-ultrafast (github.com/browser-use/jev-ultrafast).
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
