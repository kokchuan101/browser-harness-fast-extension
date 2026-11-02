# fast-browser-harness

fast-browser-harness makes [browser-harness](https://github.com/browser-use/browser-harness) agents read pages
faster. One file, `fast_all.py`, adds helpers that read a page in one browser call and click by number. On three
public pages, one look took 5 to 19 ms and one call. The accessibility-tree route took 0.3 to 10 seconds and 178 to
1,672 calls. The LLM only has to answer with a number, so a small LLM such as Claude Haiku can do it.

```text
Before: browser-harness              After: with fast_all.py

┌──────────────────────────────┐     ┌──────────────────────────────┐
│ Read the full page tree      │     │ Read the page as a numbered  │  from jev-ultrafast
│                              │     │ list (1 call)                │
└───────────────┬──────────────┘     └───────────────┬──────────────┘
┌───────────────▼──────────────┐     ┌───────────────▼──────────────┐
│ The LLM selects from         │     │ The LLM selects an element   │
│ a long list                  │     │ by index (Haiku or a         │
│                              │     │ stronger LLM)                │
└───────────────┬──────────────┘     └───────────────┬──────────────┘
┌───────────────▼──────────────┐     ┌───────────────▼──────────────┐
│ Get the position of each     │     │ Make sure that the control   │  from jev-ultrafast
│ control (1 call each)        │     │ is clear. Then click it.     │
└───────────────┬──────────────┘     └───────────────┬──────────────┘
┌───────────────▼──────────────┐     ┌───────────────▼──────────────┐
│ Click at the position        │     │ Wait until the page draws    │  from jev-ultrafast
└───────────────┬──────────────┘     └──────────────────────────────┘
┌───────────────▼──────────────┐
│ Wait a fixed time            │
└──────────────────────────────┘

178 to 1,672 calls, 0.3 to 10 s      1 call, 5 to 19 ms
```

## What it changes

| Step | browser-harness alone | With `fast_all.py` | From |
|---|---|---|---|
| Read | Accessibility tree, then one position lookup per control | `snapshot()`: one call, a numbered list | jev-ultrafast |
| Choose | The LLM selects from a long list | The LLM selects an element by index. Haiku is enough. Use a stronger LLM if it fails | Replaces jev-ultrafast's paid Jev |
| Act | `click_at_xy(x, y)` | `click_idx(n)`: checks the control first | jev-ultrafast |
| Wait | Nothing built in: the agent sleeps or polls | `settle()`: two animation frames | jev-ultrafast |
| Miss | The agent retries by hand | `click_name()`: one exact match or no click | New |
| Last resort | | The accessibility tree, as before | browser-harness |
| Coverage | Full accessibility data, also shadow DOM and iframes | Common HTML and ARIA controls; the accessibility tree for the rest | Trade-off |

Your `browser-harness` command stays as it is. The helpers live in your agent workspace, next to your own.

## Install

Install makes an exact backup of your agent workspace first and checks it. It changes nothing unless the backup is
in place. Two files change, both in your browser-harness agent workspace:

```text
~/.config/browser-harness/          ($BH_AGENT_WORKSPACE, if you set it, replaces agent-workspace/)
├── agent-workspace/
│   ├── agent_helpers.py            your helpers, plus one load line added at the end
│   └── fast_all.py                 new: the helpers from this repository
└── agent-workspace.bak/            new: the backup, an identical copy made before any change
```

Paste this into Claude Code:

```text
Install fast-browser-harness into my browser-harness. Download
https://raw.githubusercontent.com/<owner>/fast-browser-harness/main/install.sh, show it to me, then run it with
bash exactly as it is, without changing it. It backs up my agent workspace to agent-workspace.bak and checks the copy
before it changes anything. If it prints "stopped", tell me why and change nothing. Then prove it works: open
https://en.wikipedia.org with browser-harness, print snapshot(), click the search box with click_idx, and tell me
what you saw.
```

## Revert

Revert puts the backup back in place of the whole workspace. Anything you added to the workspace after the install
is lost, so copy it out first.

With Claude:

```text
Revert fast-browser-harness. Download https://raw.githubusercontent.com/<owner>/fast-browser-harness/main/revert.sh
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
