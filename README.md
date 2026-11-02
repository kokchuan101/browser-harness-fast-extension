# fast-browser-harness

fast-browser-harness makes [browser-harness](https://github.com/browser-use/browser-harness) agents read pages
faster. One file, `fast_all.py`, adds helpers that read a page in one browser call and click by number. On three
public pages, one look took 5 to 19 ms and one call. The accessibility-tree route took 0.3 to 10 seconds and 178 to
1,672 calls. The model only has to answer with a number, so a small model such as Claude Haiku can do it.

```text
Before: browser-harness              After: with fast_all.py

┌──────────────────────────────┐     ┌──────────────────────────────┐
│ Read the full page tree      │     │ Read the page as a numbered  │  from jev-ultrafast
└───────────────┬──────────────┘     │ list (1 call)                │
┌───────────────▼──────────────┐     └───────────────┬──────────────┘
│ Get the position of each     │     ┌───────────────▼──────────────┐
│ control (1 call each)        │     │ Haiku selects a number       │  replaces a paid model
└───────────────┬──────────────┘     └───────────────┬──────────────┘
┌───────────────▼──────────────┐     ┌───────────────▼──────────────┐
│ The model selects from       │     │ Make sure that the control   │  from jev-ultrafast
│ a long list                  │     │ is clear. Then click it.     │
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
| Choose | The model picks from a long list | Your model answers with a number | Replaces jev-ultrafast's paid model |
| Act | `click_at_xy(x, y)` | `click_idx(n)`: checks the control first | jev-ultrafast |
| Wait | Nothing built in: the agent sleeps or polls | `settle()`: two animation frames | jev-ultrafast |
| Miss | The agent retries by hand | `click_name()`: one exact match or no click | New |
| Last resort | | The accessibility tree, as before | browser-harness |

Your `browser-harness` command stays as it is. The helpers live in your agent workspace, next to your own.

## Install

Install backs up everything it will touch first, checks that each copy is identical, and changes nothing until the
backups are in place. It adds two things to your agent workspace and one section to your browser-harness skill:

```text
~/.config/browser-harness/
├── agent-workspace/                  ($BH_AGENT_WORKSPACE, if you set it)
│   ├── agent_helpers.py              + one load line at the end
│   └── fast_all.py                   new: the helpers
└── agent-workspace.bak/              backup: identical copy made before any change

~/.claude/skills/browser-harness/     (and ~/.codex/skills/browser-harness/, if you use Codex)
├── SKILL.md                          + a "Fast page reading" section: read with the map, let Haiku choose
└── SKILL.md.bak                      backup: identical copy made before any change
```

Paste this into Claude Code:

```text
Install fast-browser-harness into my browser-harness. Download
https://raw.githubusercontent.com/<owner>/fast-browser-harness/main/install.sh, show it to me, then run it with
bash exactly as it is, without changing it. It backs up my agent workspace and my browser-harness skill file and
checks each copy before it changes anything. If it prints "stopped", tell me why and change nothing. Then prove it
works: open https://en.wikipedia.org with browser-harness, print snapshot(), click the search box with click_idx,
and tell me what you saw.
```

If a backup from an earlier install is still there, the script stops. Revert first, or move the old backup away.
A browser-harness skill that came as a Claude Code plugin is not edited.

## Revert

Revert puts every backup back: the agent workspace and the skill file. Anything you added to them after the install
is lost, so copy it out first. Paste this into Claude Code:

```text
Revert fast-browser-harness. Download https://raw.githubusercontent.com/<owner>/fast-browser-harness/main/revert.sh
and show it to me. Before you run it, show me which backups it will restore and wait for my yes. Then run it with
bash exactly as it is, and check that browser-harness still runs.
```

## Credit

The technique comes from [jev-ultrafast](https://github.com/browser-use/jev-ultrafast) by Browser Use. It uses an
indexed page snapshot in one call, frame-based waits with focus emulation, and a hit test before each click. The code
here is new and written for browser-harness. The browser-harness README is at
[browser-use/browser-harness](https://github.com/browser-use/browser-harness).
