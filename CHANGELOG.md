# Changelog

All notable changes to Opie are documented here. This project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Full Eos command coverage by voice.** Any command the console understands is
  now reachable as a spoken phrase, not just the built-in patterns:
  - Bare action verbs on the current selection — `sneak`, `highlight`, `lowlight`,
    `mark`, `block`, `assert`, `capture`, `park` / `unpark`, `rem dim`,
    `make manual`, …
  - Bare parameters on the current selection — `gobo 3`, `pan 50`, `iris 20`,
    `zoom 75`, `hue 180`, …
  - Bare levels on the current selection — `full`, `out`, `home`, `at 50`,
    `75 percent`.
  - Action verbs attached to a target, in either order — `channel 5 sneak`
    **and** `sneak channel 5`, `group 3 park`, `channels 1 thru 8 rem dim`.
  - A **command-line fallback**: any otherwise-unrecognized phrase that contains
    a known Eos keyword is translated straight onto the Eos command line, so new
    verbs work without code changes. (The `destructive_policy` still gates
    dangerous verbs.)
- **Automatic updates.** When Opie runs from a Git clone it keeps itself current:
  the relay fast-forwards and re-execs into the latest code at startup, and the
  control panel checks on launch (plus a **Check for updates** button and an
  **Auto-update** toggle). No reinstalling to get repo changes. New config key
  `auto_update` (default `true`); pip installs and ZIP downloads degrade
  gracefully to "no auto-update".

### Fixed
- Installer no longer requires the internet or `pip`/`setuptools` — it runs the app
  straight from the source folder with a suitable Python (fixes the silent
  "python failed to open" install failure on offline machines).
- GUI no longer hard-crashes on the deprecated macOS system **Tk 8.5** (the
  `Tcl_Panic`/`TkpInit` abort). It now requires **Tk ≥ 8.6**, and:
  - the GUI shows a friendly native dialog (with a python.org link) instead of crashing;
  - the installer auto-selects a Tk-8.6 Python (python.org or Homebrew) and offers to
    install one if none is present.

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
