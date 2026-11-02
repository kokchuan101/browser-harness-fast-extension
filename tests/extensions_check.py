# Checks one extensions/*.py file (or all of them together, EXT=all) pasted alone into agent_helpers.py of plain
# browser-harness 0.1.13. Run with tests/run.sh extensions. Prints PASS/FAIL lines.
import os
import time

EXT = os.environ["EXT"]
OUT = os.environ.get("FB_OUT", "/tmp/browser-harness-fast-extension-out")
OWN = {"frame_wait": ["settle", "wait_until"], "indexed_map": ["snapshot", "click_idx", "type_idx"],
       "click_repair": ["click_name", "click_text"], "marked_shot": ["capture_marked"]}
ALL = sum(OWN.values(), [])
tabs = []


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, str(e)[:300])
    print("%s %s: %s: %s" % ("PASS" if ok else "FAIL", EXT, name, detail))


def raises(fn, text):
    try:
        fn()
    except Exception as e:
        return text in str(e), str(e)[:160]
    return False, "no error raised"


def until(expr, timeout):
    """The check's own poll, so an extension is tested without the frame_wait extension's wait_until."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            if js(expr):
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def open_page(url):
    tabs.append(new_tab(url)); wait_for_load(30)
    js("1")


want = ALL if EXT == "all" else OWN[EXT]
have = [n for n in ALL if n in globals()]
check("loads its names and no others", lambda: (have == want, "defined: %s" % have))

if EXT in ("frame_wait", "all"):
    def t():
        open_page("https://en.wikipedia.org/wiki/Main_Page"); settle()
        r = [settle(cap_ms=1000) for _ in range(3)]   # frames arrive at all; a 50 ms cap can run out while the page loads
        w = wait_until("document.readyState === 'complete'", 10)
        return r == ["ready"] * 3 and w is True, "settle %s, wait_until %r" % (r, w)
    check("settle and wait_until work in a background tab", t)

if EXT in ("indexed_map", "all"):
    def t():
        open_page("https://en.wikipedia.org/wiki/Main_Page")
        s = snapshot(text=False)
        n = next(int(l[1:l.index("]")]) for l in s.splitlines() if 'searchbox "Search Wikipedia"' in l)
        v = type_idx(n, "Ada Lovelace", enter=True)
        ok = until("location.pathname === '/wiki/Ada_Lovelace'", 20)
        return v == "Ada Lovelace" and bool(ok), "typed into [%d]: %r, now at %s" % (n, v, js("location.pathname"))
    check("snapshot and type_idx reach the article", t)
    check("click_idx refuses a number from an old page", lambda: raises(lambda: click_idx(1, timeout=0.2), "no item [1]"))

if EXT in ("click_repair", "all"):
    def t():
        open_page("https://github.com/browser-use/browser-harness")
        return raises(lambda: click_name("Code", timeout=0.5), "controls match, so nothing was clicked")
    check("click_name refuses two matches", t)
    def t2():
        r = click_text("issues", timeout=0.5)
        ok = until("location.pathname.endsWith('/issues')", 20)
        return bool(ok) and r.get("recovered") == "found by its text in another case", "recovered=%r" % r.get("recovered")
    check("click_text repairs by case", t2)

if EXT in ("click_repair", "all"):
    def t3():
        open_page("https://en.wikipedia.org/wiki/Main_Page")
        js("""(() => { const h = document.createElement('div'); h.id = 'fast-ext-shadow';
              h.style.cssText = 'position:fixed;top:120px;left:120px;z-index:10';
              h.attachShadow({mode: 'open'}).innerHTML = '<button>Shadow button</button>';
              h.shadowRoot.querySelector('button').onclick = () => h.dataset.clicked = '1';
              document.body.appendChild(h); })()""")
        r = click_name("Shadow button", timeout=0.5)
        ok = js("document.getElementById('fast-ext-shadow').dataset.clicked === '1'")
        return ok and r.get("recovered") == "found in the accessibility tree", "recovered=%r, clicked=%r" % (r.get("recovered"), ok)
    check("click_name falls back to the accessibility tree", t3)

if EXT in ("marked_shot", "all"):
    def t():
        open_page("https://en.wikipedia.org/wiki/Ada_Lovelace")
        r = capture_marked(os.path.join(OUT, "ext-%s.png" % EXT), [{"css": "#firstHeading", "note": "title"}])
        return r["marked"] == 1 and os.path.getsize(r["path"]) > 1000, str(r)
    check("capture_marked boxes a CSS target", t)

for t in tabs:
    try:
        cdp("Target.closeTarget", targetId=t)
    except Exception:
        pass
