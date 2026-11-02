# browser-harness-fast-extension extension: marked_shot. capture_marked(path, marks): a screenshot with red boxes on chosen controls.
# Paste this whole file at the end of your browser-harness agent_helpers.py ($BH_AGENT_WORKSPACE, by default
# ~/.config/browser-harness/agent-workspace/agent_helpers.py). Boxes by number ({'idx': n}) need indexed_map.py; CSS and text marks work alone.
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
