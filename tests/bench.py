# Benchmark: the accessibility-tree route against the indexed map (snapshot), on the same public pages.
# Run with tests/run.sh bench (plain browser-harness 0.1.13 with fast_helpers.py loaded). Each page: 3 runs per route in one background tab at 1120x780, medians.
# Prints a Markdown table and writes bench.json to $FB_OUT.
#
# Accessibility route = what an agent does without a map: Accessibility.getFullAXTree, then DOM.getBoxModel for each
# interactive node to learn where it is, then a screenshot to see the page.
# Indexed map = snapshot() from fast_helpers.py: one Runtime.evaluate returns the numbered controls in view plus the visible text.
import json
import os
import statistics as st
import time

PAGES = [("Wikipedia main page", "https://en.wikipedia.org/wiki/Main_Page"),
         ("GitHub repo page", "https://github.com/browser-use/browser-harness"),
         ("MDN <input> docs", "https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input")]
ROLES = {"button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "option", "combobox", "textbox",
         "searchbox", "spinbutton"}
RUNS = 3
W, H = 1120, 780


def ms(t0):
    return (time.perf_counter() - t0) * 1000


def a11y_route():
    t0 = time.perf_counter()
    nodes = cdp("Accessibility.getFullAXTree")["nodes"]
    t_tree = ms(t0)
    cand = [n for n in nodes if not n.get("ignored") and n.get("backendDOMNodeId")
            and (n.get("role") or {}).get("value") in ROLES]
    lines_all, lines_view = [], []
    t1 = time.perf_counter()
    for n in cand:
        line = "%s | %s" % (n["role"]["value"], ((n.get("name") or {}).get("value") or "")[:100])
        if (n.get("name") or {}).get("value"):
            lines_all.append(line)
        try:
            q = cdp("DOM.getBoxModel", backendNodeId=n["backendDOMNodeId"])["model"]["content"]
        except Exception:
            continue
        x, y = sum(q[0::2]) / 4, sum(q[1::2]) / 4
        if 0 <= x < W and 0 <= y < H and (n.get("name") or {}).get("value"):
            lines_view.append(line)
    t_box = ms(t1)
    t2 = time.perf_counter()
    shot = cdp("Page.captureScreenshot", format="png", _response_timeout=60)["data"]
    t_shot = ms(t2)
    return {"ms": t_tree + t_box + t_shot, "tree_ms": t_tree, "box_ms": t_box, "shot_ms": t_shot,
            "cdp_calls": 1 + len(cand) + 1, "ax_nodes": len(nodes), "tree_kb": len(json.dumps(nodes)) / 1024,
            "chars_all": len("\n".join(lines_all)), "chars_in_view": len("\n".join(lines_view)),
            "in_view": len(lines_view), "png_kb": len(shot) * 3 / 4 / 1024}


def map_route():
    t0 = time.perf_counter()
    s = snapshot()
    t = ms(t0)
    controls = s.split("\n--- visible text ---\n")[0]
    return {"ms": t, "cdp_calls": 1, "chars": len(s), "chars_controls": len(controls),
            "in_view": controls.count("\n")}


def two_frames(focus):
    cdp("Emulation.setFocusEmulationEnabled", enabled=focus)
    t0 = time.perf_counter()
    try:
        cdp("Runtime.evaluate", expression="new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))",
            awaitPromise=True, returnByValue=True, _response_timeout=3)
        return round(ms(t0))
    except Exception:
        return "timeout > 3 s"


def med(rows, key):
    return st.median(r[key] for r in rows)


out = {"viewport": [W, H], "runs": RUNS, "pages": {}}
tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab)
cdp("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
try:
    for label, url in PAGES:
        goto_url(url)
        wait_for_load(30)
        frames = {"no_focus_emulation": two_frames(False), "focus_emulation": two_frames(True)}
        settle()
        time.sleep(1.5)                                            # let late content land; the same page for both routes
        a = [a11y_route() for _ in range(RUNS)]
        m = [map_route() for _ in range(RUNS)]
        out["pages"][label] = {"url": url, "a11y_runs": a, "map_runs": m, "two_frames_ms": frames}
finally:
    cdp("Emulation.clearDeviceMetricsOverride")
    cdp("Target.closeTarget", targetId=tab)

print("| Page | Accessibility route: time | CDP calls | Text to the model | Indexed map: time | CDP calls | Text to the model | Two frames in a background tab |")
print("|---|---|---|---|---|---|---|---|")
for label, p in out["pages"].items():
    a, m = p["a11y_runs"], p["map_runs"]
    print("| %s | %.0f ms (tree %.0f, boxes %.0f, PNG %.0f) | %d | %s chars in view (%s all) + a %.0f KB screenshot | %.1f ms | 1 | %s chars (%s for the %d controls) | %s without focus emulation, %s ms with |" % (
        label, med(a, "ms"), med(a, "tree_ms"), med(a, "box_ms"), med(a, "shot_ms"), med(a, "cdp_calls"),
        format(int(med(a, "chars_in_view")), ","), format(int(med(a, "chars_all")), ","), med(a, "png_kb"),
        med(m, "ms"), format(int(med(m, "chars")), ","), format(int(med(m, "chars_controls")), ","), int(med(m, "in_view")),
        p["two_frames_ms"]["no_focus_emulation"], p["two_frames_ms"]["focus_emulation"]))
dest = os.path.join(os.environ.get("FB_OUT", "/tmp/browser-harness-fast-extension-out"), "bench.json")
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w") as f:
    json.dump(out, f, indent=1)
print("saved", dest)
