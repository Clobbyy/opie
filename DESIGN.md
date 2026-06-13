# DESIGN.md — Opie control panel

Dark-first "booth console" system for the Opie panel. Bold, cohesive identity built
from the app icon (indigo→violet, three faders) — but trustworthy, standard
affordances and motion that only ever conveys state. Implemented as a single
self-contained HTML page (`PAGE` in `opie/panel.py`); no external assets, works
offline, no build step.

## Color (OKLCH)

Color strategy: **Committed** on the brand axis (an indigo→violet accent carries
identity) over a **tinted near-black** neutral ramp. Never `#000`/`#fff`; every
neutral is tinted toward the indigo brand hue (h≈275).

Dark theme (default):

| Token | OKLCH | Role |
|---|---|---|
| `--bg` | `oklch(0.17 0.012 275)` | app background (warm near-black, indigo-tinted) |
| `--surface` | `oklch(0.21 0.014 275)` | panels / sections |
| `--surface-2` | `oklch(0.25 0.016 275)` | insets, inputs, raised chips |
| `--line` | `oklch(0.32 0.02 275)` | hairline borders (full borders only) |
| `--text` | `oklch(0.96 0.006 275)` | primary text |
| `--text-dim` | `oklch(0.72 0.014 275)` | secondary text |
| `--text-faint` | `oklch(0.55 0.014 275)` | tertiary / captions |
| `--accent` | `oklch(0.62 0.20 285)` | indigo, primary actions / focus |
| `--accent-2` | `oklch(0.66 0.20 305)` | violet, gradient partner (the icon) |
| `--ok` | `oklch(0.74 0.17 150)` | running / reachable / success |
| `--warn` | `oklch(0.80 0.15 85)` | revision drift / caution |
| `--err` | `oklch(0.65 0.21 25)` | stopped / error |

Light theme (`prefers-color-scheme: light` + manual override): same hues, ramp
inverted — `--bg` ~`oklch(0.97 0.006 275)`, surfaces white-ish indigo-tint, accent
darkened to `oklch(0.52 0.20 285)` for AA contrast on light.

Accent is for primary actions, focus rings, current state, and the live signal only.
Never decorative fills on inactive controls. The indigo→violet gradient appears only
on the brand mark and the primary-action button, never on text (`background-clip:
text` is banned).

## Typography

- **UI sans:** `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`.
  Native feel; legitimate for a Mac tool.
- **Operational mono:** `ui-monospace, "SF Mono", Menlo, monospace` for every machine
  value — IPs, ports, tokens, OSC strings, revisions, the log. These are the content.
- Fixed rem scale, ratio ~1.2: `12 / 13 / 15 / 18 / 22 / 28`. Section labels are
  small caps (12px, uppercase, +0.06em tracking, `--text-faint`). Weight does the
  heavy lifting: 600 for headings/labels/buttons, 400–500 body.

## Layout

- Single column, max-width ~720px, centered, generous breathing room. The panel is a
  stack of distinct regions, **not** a grid of identical cards (that monotony is the
  current design's main flaw and an explicit anti-reference).
- **Status hero** at the top: a full-width signal strip — large running/stopped state
  with a live pulse, the relay URL, console reachability, version + revision-drift
  warning. This is the most important region; it gets the most weight.
- Below it, lighter "settings"-style grouped rows (label left / control right or
  stacked) for Setup, a focused Test/phone region, and a terminal-style Log.
- Vary vertical rhythm between regions; don't pad everything identically.
- Responsive is structural: rows collapse to single column under ~560px.

## Components & states

Every interactive element ships: default, hover, focus-visible (accent ring), active,
disabled, plus loading/error where it acts. Standard controls only — system-styled
text inputs, selects, checkboxes (as toggles), buttons. No reinvented form controls.

- **Primary button** (Start, Save): indigo→violet gradient, white text.
- **Secondary button:** `--surface-2` fill, hairline border.
- **Status dot / signal:** an animated equalizer-style "signal" (a nod to the three
  faders in the icon) when running; flat/dim when stopped.
- **Inline feedback** (saved, test result, ping) appears next to its action, color-
  coded with `--ok`/`--err`, auto-clearing.
- **Error region** for relay-start failures: monospace, the real log tail.

## Motion

State only, 150–250ms, ease-out (`cubic-bezier(0.22,1,0.36,1)`). No bounce/elastic,
never animate layout props.

- Running signal: a continuous, low-amplitude bar equalizer (transform/opacity only).
- Status transitions (stopped↔running) cross-fade color + dot.
- A test phrase firing: brief pulse along the signal to show flow.
- Buttons: 1px active translate, fast hover. Log auto-scrolls on new lines.

## Copy

Operator-grade, exact, terse. No em dashes (use commas/colons/periods/parens). Real
nouns and numbers. Errors say what happened and the next action.
