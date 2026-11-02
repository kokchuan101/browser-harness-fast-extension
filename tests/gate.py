# Gate for fast_helpers.py on public pages (Wikipedia, GitHub), in plain browser-harness 0.1.13.
# Run with tests/run.sh gate: fast_helpers.py is loaded by its load line from an agent_helpers.py that has its own helper.
# Prints PASS/FAIL lines and "GATE x/y". Live pages change: read a FAIL's detail before blaming a helper.
import os
import sys
import time

OUT = os.environ.get("FB_OUT", "/tmp/browser-harness-fast-extension-out")
results, opened = [], []


def check(name, fn):
    t0 = time.perf_counter()
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, str(e)[:300])
    results.append(ok)
    print("%s %s (%d ms): %s" % ("PASS" if ok else "FAIL", name, round((time.perf_counter() - t0) * 1000), detail))


def raises(fn, text):
    try:
        fn()
    except Exception as e:
        return text in str(e), str(e)[:200]
    return False, "no error raised"


def index_of(snap, part):
    for line in snap.splitlines():
        if line.startswith("[") and part in line:
            return int(line[1:line.index("]")])
    raise RuntimeError("no line with %r in the snapshot" % part)


def path():
    return js("location.pathname")


def png(p):
    with open(p, "rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n" and os.path.getsize(p) > 1000


NAMES = ["snapshot", "click_idx", "type_idx", "settle", "wait_until", "click_name", "click_text", "capture_marked"]
import inspect
FAST = inspect.unwrap(click_name).__globals__ if "click_name" in globals() else {}   # the helpers' own namespace


def t_load():
    from browser_harness import paths
    own = sorted(f for f in os.listdir(paths.workspace_dir()) if not f.startswith("__"))
    missing = [n for n in NAMES if n not in globals()]
    mine = "my_own_helper" in globals() and my_own_helper() == "mine"
    return not missing and mine and own == ["agent_helpers.py", "fast_helpers.py"], \
        "missing %s; own helper still works: %s; workspace files %s" % (missing, mine, own)
check("load: the load line adds every helper and keeps the user's own", t_load)


def t_settle():
    opened.append(new_tab("https://en.wikipedia.org/wiki/Main_Page"))
    wait_for_load(30)
    settle()
    r = [settle(cap_ms=1000) for _ in range(3)]   # frames arrive at all; a 50 ms cap can run out while the page loads
    return r == ["ready"] * 3, "results %s in a background tab" % r
check("settle returns 'ready' in a background tab", t_settle)


def t_wait():
    ok1 = wait_until("document.readyState === 'complete'", 10)
    t0 = time.perf_counter(); none = wait_until("false", 0.3); took = time.perf_counter() - t0
    return ok1 is True and none is None and took < 1.5, "true case %r; false case %r after %.2f s" % (ok1, none, took)
check("wait_until returns the value, or None on timeout", t_wait)

snap = {}
def t_snapshot():
    s = snapshot(); short = snapshot(text=False); snap["main"] = short
    ok = (s.splitlines()[0].startswith("/wiki/Main_Page |") and 'searchbox "Search Wikipedia"' in s
          and "--- visible text ---" in s and "--- visible text ---" not in short and len(short) < len(s))
    return ok, "%d controls; %d chars with text, %d without" % (short.count("\n"), len(s), len(short))
check("snapshot returns the indexed map and the visible text", t_snapshot)


def t_type():
    n = index_of(snap["main"], 'searchbox "Search Wikipedia"')
    v = type_idx(n, "Ada Lovelace", enter=True)
    arrived = wait_until("location.pathname === '/wiki/Ada_Lovelace' && document.readyState === 'complete'", 20)
    return v == "Ada Lovelace" and bool(arrived), "typed into [%d], field value %r, then at %s" % (n, v, path())
check("type_idx types into [n] and presses Enter", t_type)

check("click_idx refuses a number from an old page", lambda: raises(lambda: click_idx(1, timeout=0.2), "no item [1]"))


def t_click_idx():
    n = index_of(snapshot(text=False), 'link "Talk"')
    p = click_idx(n)
    arrived = wait_until("location.pathname === '/wiki/Talk:Ada_Lovelace'", 20)
    return bool(arrived) and p["name"] == "Talk", "clicked [%d] %s %r, now at %s" % (n, p["role"], p["name"], path())
check("click_idx clicks item [n]", t_click_idx)


def t_case():
    wait_until("document.readyState === 'complete'", 15)
    r = click_name("article", role="link", timeout=1)               # the tab is named "Article"
    arrived = wait_until("location.pathname === '/wiki/Ada_Lovelace'", 20)
    return bool(arrived) and r.get("recovered") == "found by its name in another case", \
        "recovered=%r, now at %s" % (r.get("recovered"), path())
check("click_name repairs: same name in another case, one match", t_case)


def t_covered():
    wait_until("document.readyState === 'complete'", 15)
    js("""(() => { const b = document.createElement('button'); b.id = 'fast-gate-covered'; b.textContent = 'Covered button';
          b.style.cssText = 'position:fixed;top:120px;left:120px;z-index:10'; document.body.appendChild(b);
          const o = document.createElement('div'); o.id = 'fast-gate-overlay';
          o.style.cssText = 'position:fixed;inset:0;z-index:20;background:rgba(0,0,0,.05)'; document.body.appendChild(o); })()""")
    n = index_of(snapshot(text=False), 'button "Covered button"')
    ok, detail = raises(lambda: click_idx(n, timeout=0.3), "covered by div")
    js("document.getElementById('fast-gate-overlay').remove(); document.getElementById('fast-gate-covered').remove()")
    return ok, detail
check("click_idx clicks nothing when another element covers [n]", t_covered)


def t_loaded():
    js("""setTimeout(() => { const b = document.createElement('button'); b.id = 'fast-gate-late'; b.textContent = 'Late button';
          b.onclick = () => b.dataset.clicked = '1'; b.style.cssText = 'position:fixed;top:120px;left:120px;z-index:10';
          document.body.appendChild(b); }, 900)""")
    real = FAST["_fast_loaded"]
    FAST["_fast_loaded"] = lambda: True                              # pretend the machine is busy
    try:
        r = click_name("Late button", timeout=0.5)
    finally:
        FAST["_fast_loaded"] = real
    clicked = js("document.getElementById('fast-gate-late')?.dataset.clicked === '1'")
    js("document.getElementById('fast-gate-late')?.remove()")
    return clicked and r.get("recovered") == "found after waiting longer under load", \
        "recovered=%r, clicked=%r" % (r.get("recovered"), clicked)
check("click_name waits one more timeout when the machine is loaded", t_loaded)


def t_ax_fallback():
    js("""(() => { const h = document.createElement('div'); h.id = 'fast-gate-shadow';
          h.style.cssText = 'position:fixed;top:120px;left:120px;z-index:10';
          h.attachShadow({mode: 'open'}).innerHTML = '<button>Shadow button</button>';
          h.shadowRoot.querySelector('button').onclick = () => h.dataset.clicked = '1';
          document.body.appendChild(h); })()""")
    in_map = "Shadow button" in snapshot(text=False)
    r = click_name("Shadow button", timeout=0.5)
    clicked = js("document.getElementById('fast-gate-shadow').dataset.clicked === '1'")
    js("document.getElementById('fast-gate-shadow').remove()")
    return (not in_map) and clicked and r.get("recovered") == "found in the accessibility tree", \
        "in the map: %s; recovered=%r, clicked=%r" % (in_map, r.get("recovered"), clicked)
check("click_name falls back to the accessibility tree (a button in shadow DOM)", t_ax_fallback)


def t_marked():
    n = index_of(snapshot(text=False), 'searchbox "Search Wikipedia"')
    r = capture_marked(os.path.join(OUT, "gate-marked.png"),
                       [{"idx": n, "note": "search box [%d]" % n}, {"css": "#firstHeading", "note": "title"}])
    left = js("!!document.getElementById('__fast_marks')")
    return r["marked"] == 2 and not r["missing"] and png(r["path"]) and not left, "%s; overlay left: %s" % (r, left)
check("capture_marked boxes [n] and a CSS target, then removes the boxes", t_marked)


def t_ambiguous():
    opened.append(new_tab("https://github.com/browser-use/browser-harness"))
    wait_until("document.readyState === 'complete'", 30)
    before = path()
    ok, detail = raises(lambda: click_name("Code", timeout=0.5), "controls match, so nothing was clicked")
    return ok and path() == before, detail
check("click_name refuses when several controls share the name", t_ambiguous)


def t_text():
    r = click_text("issues", timeout=0.5)
    arrived = wait_until("location.pathname === '/browser-use/browser-harness/issues'", 20)
    return bool(arrived) and r.get("recovered") == "found by its text in another case", \
        "recovered=%r, now at %s" % (r.get("recovered"), path())
check("click_text repairs: same text in another case, one match", t_text)

for t in opened:
    try:
        cdp("Target.closeTarget", targetId=t)
    except Exception:
        pass
print("GATE %d/%d" % (sum(results), len(results)))
