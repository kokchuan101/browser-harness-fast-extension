# browser-harness-fast-extension

This is an extension of [browser-harness](https://github.com/browser-use/browser-harness) that adds the
[jev-ultrafast](https://github.com/browser-use/jev-ultrafast) mechanism. The installation extends your current
browser-harness and offers to create helpers for your specific tests. It can only get faster from here.

Note: it modifies your current browser-harness. The installation backs it up first, just in case.

## What it changes

```text
        browser-harness                  with fast_helpers.py

        ┌────────────────────────────┐   ┌────────────────────────────┐
Read    │ Read the full A11y tree,   │   │ snapshot(): read the DOM   │  from jev-ultrafast
        │ then get the position of   │   │ as an indexed list (1      │
        │ the chosen control         │   │ call)                      │
        └──────────────┬─────────────┘   └──────────────┬─────────────┘
        ┌──────────────▼─────────────┐   ┌──────────────▼─────────────┐
Choose  │ The LLM selects from a     │   │ The LLM selects an element │  replaces paid Jev
        │ long list                  │   │ by index (Haiku, or a      │
        │                            │   │ stronger LLM if it fails)  │
        └──────────────┬─────────────┘   └──────────────┬─────────────┘
        ┌──────────────▼─────────────┐   ┌──────────────▼─────────────┐
Act     │ click_at_xy(x, y) at that  │   │ click_idx(n): check it is  │  from jev-ultrafast
        │ position                   │   │ the same control and       │
        │                            │   │ nothing covers it. Then    │
        │                            │   │ click it.                  │
        └──────────────┬─────────────┘   └──────────────┬─────────────┘
        ┌──────────────▼─────────────┐   ┌──────────────▼─────────────┐
Wait    │ No built-in wait after a   │   │ settle(): wait until the   │  from jev-ultrafast
        │ click. The agent sleeps or │   │ page draws. wait_until(js) │
        │ polls.                     │   │ for data that loads.       │
        └──────────────┬─────────────┘   └──────────────┬─────────────┘
        ┌──────────────▼─────────────┐   ┌──────────────▼─────────────┐
Miss    │ The agent retries by hand  │   │ click_name(),              │  new
        │                            │   │ click_text(): more time,   │
        │                            │   │ other case, text or name,  │
        │                            │   │ then the A11y tree. One    │
        │                            │   │ match only.                │
        └────────────────────────────┘   └────────────────────────────┘
```

Your `browser-harness` command stays as it is. The helpers live in your agent workspace, next to your own.

## Install

Install makes an exact backup of your agent workspace first and checks it. It changes nothing unless the backup is
in place. The install can also help you write helpers for your own app, built on `fast_helpers.py`, in your own
`agent_helpers.py`. Two files change, both in your browser-harness agent workspace:

```text
~/.config/browser-harness/          ($BH_AGENT_WORKSPACE, if you set it, replaces agent-workspace/)
├── agent-workspace/
│   ├── agent_helpers.py            your helpers, plus one load line added at the end
│   └── fast_helpers.py             new: the helpers from this repository
└── agent-workspace.bak/            new: the backup, an identical copy made before any change
```

Paste this into Claude Code:

```text
Install browser-harness-fast-extension into my browser-harness. Download
https://raw.githubusercontent.com/<owner>/browser-harness-fast-extension/main/install.sh, show it to me, then run it with
bash exactly as it is, without changing it. It backs up my agent workspace to agent-workspace.bak and checks the copy
before it changes anything. If it prints "stopped", tell me why and change nothing. Then prove it works: open
https://en.wikipedia.org with browser-harness, print snapshot(), click the search box with click_idx, and tell me
what you saw.

When the check passes, ask me: "Do you want helpers for the web app you test day to day?" If I say no, stop.
If yes:
1. Read the HOW TO USE block at the top of fast_helpers.py, then my agent_helpers.py, and list the helpers I already
   have. Reuse them; do not write a second version. A helper never stores a snapshot number: find the control
   by name or text with click_name() or click_text(), or take a snapshot inside the helper.
2. Ask me for the app's URL, how I log in, and two or three flows I test often.
3. Run each flow once with my browser-harness, using my helpers where they fit and snapshot(), click_idx(n)
   and wait_until(js) for the rest. Note the steps that repeat and the places where a click or wait failed.
4. Add helpers only for those steps, in agent_helpers.py with an <app>_ prefix, built on snapshot(),
   click_name() and wait_until(). If one of my helpers sleeps for a fixed time or clicks by coordinates, offer
   to switch it to wait_until() or click_name(), and change it only if I say yes. Never edit fast_helpers.py.
5. Run the flows again, and show me the time and tool calls before and after.
```

## Revert

Revert puts the backup back in place of the whole workspace. Anything you added to the workspace after the install
is lost, so copy it out first.

With Claude:

```text
Revert browser-harness-fast-extension. Download https://raw.githubusercontent.com/<owner>/browser-harness-fast-extension/main/revert.sh
and show it to me. Before you run it, show me what is in agent-workspace and agent-workspace.bak and wait for my yes.
Then run it with bash exactly as it is, and check that browser-harness still runs.
```

By hand:

```bash
WS="${BH_AGENT_WORKSPACE:-$HOME/.config/browser-harness/agent-workspace}"
test -d "$WS.bak" \
  && rm -rf "$WS" \
  && mv "$WS.bak" "$WS" \
  && echo "reverted: $WS is the backup again"
```

## Credit

The technique comes from [jev-ultrafast](https://github.com/browser-use/jev-ultrafast) by Browser Use. It uses an
indexed page snapshot in one call, frame-based waits with focus emulation, and a hit test before each click. The code
here is new and written for browser-harness. The browser-harness README is at
[browser-use/browser-harness](https://github.com/browser-use/browser-harness).
