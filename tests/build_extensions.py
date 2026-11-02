#!/usr/bin/env python3
"""Copy each extension of fast_all.py into extensions/<name>.py, a standalone snippet for agent_helpers.py.

    python3 tests/build_extensions.py           write the extensions
    python3 tests/build_extensions.py --check   exit 1 when an extension file is out of date
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "fast_all.py")
OUT = os.path.join(ROOT, "extensions")

# name: (what it adds, needs the shared page library, how it pairs with other extensions)
EXTENSIONS = {
    "frame_wait": ("settle() and wait_until(js): wait on the page instead of a fixed sleep.", False,
                   "It needs no other extension."),
    "indexed_map": ("snapshot(), click_idx(n) and type_idx(n, text): read the page as a numbered map, act by number.",
                    True, "Add frame_wait.py too, so clicks wait on the page; without it they do not wait."),
    "click_repair": ("click_name(name) and click_text(text): exact clicks that repair a miss safely.", True,
                     "Add frame_wait.py too, so clicks wait on the page; without it they do not wait."),
    "marked_shot": ("capture_marked(path, marks): a screenshot with red boxes on chosen controls.", True,
                    "Boxes by number ({'idx': n}) need indexed_map.py; CSS and text marks work alone."),
}


def sections(text):
    found = dict(re.findall(r"^# --- extension: (\w+)\n(.*?)^# --- end extension\n", text, re.S | re.M))
    missing = [n for n in ["core"] + list(EXTENSIONS) if n not in found]
    if missing:
        raise SystemExit("fast_all.py has no extension named %s" % missing)
    return found


def render(name, found):
    what, core, pairs = EXTENSIONS[name]
    head = ("# fast-browser-harness extension: %s. %s\n"
            "# Paste this whole file at the end of your browser-harness agent_helpers.py ($BH_AGENT_WORKSPACE, by default\n"
            "# ~/.config/browser-harness/agent-workspace/agent_helpers.py). %s\n"
            "# Tested with browser-harness 0.1.13. Generated from fast_all.py by tests/build_extensions.py; edit fast_all.py,\n"
            "# not this file. Technique from jev-ultrafast (github.com/browser-use/jev-ultrafast).\n"
            % (name, what, pairs))
    return head + (found["core"] if core else "") + found[name]


def main(args):
    found = sections(open(SRC).read())
    stale = []
    outputs = [(name, render(name, found)) for name in EXTENSIONS]
    for name, text in outputs:
        path = os.path.join(OUT, name + ".py")
        current = open(path).read() if os.path.exists(path) else None
        if current != text:
            stale.append(name)
            if "--check" not in args:
                os.makedirs(OUT, exist_ok=True)
                with open(path, "w") as f:
                    f.write(text)
    if "--check" in args:
        print("extensions up to date" if not stale else "extensions out of date: %s (run tests/build_extensions.py)" % stale)
        return 1 if stale else 0
    print("wrote %s" % (stale or "nothing, extensions were up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
