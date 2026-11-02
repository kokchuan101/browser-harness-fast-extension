# fast-browser-harness extension: indexed_map. snapshot(), click_idx(n) and type_idx(n, text): read the page as a numbered map, act by number.
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
