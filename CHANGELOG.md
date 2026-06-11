# Changelog

All notable changes to Opie are documented here. This project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **One-command install.** The entire setup is a single line pasted into Terminal —
  `/bin/bash -c "$(curl -fsSL …/install.sh)"` — plus a matching `uninstall.sh`. It
  downloads the code, generates the token, starts the relay, and adds an **Opie** app to
  `~/Applications`. No Apple Developer ID and no Gatekeeper prompt (`curl`/`git` downloads
  aren't quarantined), and everything runs on the Mac's built-in Python 3 — nothing else
  to install. Re-paste the command to update.
- **Browser control panel (`opie.panel`).** A localhost-only web app (standard library
  only) for setup, Start/Stop/Restart, autostart toggle, live logs, a test box, console
  reachability, phone-setup info, and update checks. Opening the **Opie** app brings the
  relay up automatically and opens the panel; Start/Restart report failures with the
  relay's actual error.
- **Automatic updates.** When Opie runs from a Git clone it keeps itself current — the
  relay fast-forwards and re-execs into the latest code (in the background, so it never
  delays startup), plus a **Check for updates** button and an **Auto-update** toggle. New
  config key `auto_update` (default `true`).
- **Full Eos command coverage by voice.** Any command the console understands is reachable
  as a spoken phrase, not just the built-in patterns:
  - Bare action verbs on the current selection — `sneak`, `highlight`, `lowlight`, `mark`,
    `block`, `assert`, `capture`, `park` / `unpark`, `rem dim`, `make manual`, …
  - Bare parameters — `gobo 3`, `pan 50`, `iris 20`, `zoom 75`, `hue 180`, …
  - Bare levels — `full`, `out`, `home`, `at 50`, `75 percent`.
  - Action verbs attached to a target, in either order — `channel 5 sneak` **and**
    `sneak channel 5`, `group 3 park`, `channels 1 thru 8 rem dim`.
  - A **command-line fallback**: any otherwise-unrecognized phrase that contains a known
    Eos keyword goes straight to the Eos command line, so new verbs work without code
    changes. (The `destructive_policy` still gates dangerous verbs.)

### Changed
- **Removed the Tkinter window (`opie-gui`)** entirely in favor of the browser panel —
  this drops the Tk 8.6 requirement (the macOS system Python's Tk 8.5 crash, and the
  python.org/Homebrew detour, are gone).
- The relay runs as a **detached, log-captured subprocess** managed by the panel, with a
  fallback when a launchd autostart job is broken — so Start works reliably and crashes
  are visible (`relay.out.log`). Hardened `service` so a missing/erroring `launchctl`
  degrades gracefully instead of raising.

### Fixed
- **"Go to cue" (and friends) now survive Siri's dictation quirks.** Dictation rarely
  produces the literal word "cue" — it writes `Q`, `que`, `queue`, or glues the number on
  (`Q10`), and sprinkles punctuation. All phrases are now normalized before matching:
  `Q/que/queue/Q10` → `cue`, `go 2 cue 5` → `go to cue 5`, number homophones after a
  target word (`cue to/for/won/ate` → `cue 2/4/1/8`), comma lists (`channels 1, 3 and 5`),
  `1-8`/`threw` → `thru`, `@` → `at`, `75%`, `snake` → `sneak`, `micro` → `macro`,
  `black out` → `blackout`, `sub master` → `submaster`, `high/low light`,
  `ram/rim dim` → `rem dim`, glued target numbers (`channel5`), and trailing
  punctuation/`please` are ignored.
- **Voice commands no longer interfere with other software cueing the console.** Eos runs
  un-scoped OSC from every sender on the *same* command line and selection, so the relay's
  traffic could interleave with — and corrupt — network cues sent by QLab, sound desks, etc.
  Everything the relay sends is now scoped to its own Eos user (`/eos/user/<n>/…`; new
  config key `OSC_USER`, default `0` = the console's invisible background user), and
  command-line strings use `/eos/newcmd` (clear-then-type) instead of `/eos/cmd` (append),
  so a half-typed leftover can never merge into the next command. Set `OSC_USER` to a
  positive number to run on a visible user, or `-1` for the old shared behaviour. Note:
  bare commands (`full`, `sneak`, `gobo 3`) now act on the selection last made *by voice*,
  not the operator's console selection.

## [0.1.0] — 2026-06-08

First packaged release.

### Added
- Installable Python package `opie` with console commands:
  - `opie` — run the HTTP→OSC relay
  - `opie-gui` — the **Opie Control** Tkinter panel
  - `opie-sniff` — loopback OSC sniffer for safe dry runs
- **Opie Control** desktop GUI: edit config, Start/Stop/Restart, toggle
  autostart at login (launchd), live log tail, send-a-command test box,
  console-reachability check, and iPhone Shortcut setup helper.
- `install.command` / `uninstall.command` double-click installers (venv + GUI).
- Config now lives in `~/Library/Application Support/Opie/config.json`
  (auto-created on first run with a freshly generated token); logs in
  `~/Library/Logs/Opie/`.
- GitHub Actions CI running the test suite.

### Changed
- Restructured the `relay/` scripts into an importable `opie` package with
  relative imports (removes the old `sys.path` hacks and the `parser` stdlib
  name clash).

### Security
- No secrets in the repo: the shipped `config.example.json` uses placeholders,
  and the live config (with your token) is kept outside the tree and gitignored.
