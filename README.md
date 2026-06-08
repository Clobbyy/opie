# Opie — ETC Nomad voice control via Siri

Speak normal phrases to Siri → they become **ETC Eos OSC** messages → your **Nomad**
console reacts. No API credits, no subscriptions, no cloud — just a tiny Python relay
on the theatre Mac and an Apple Shortcut on your phone, managed from a small desktop app.

```
iPhone (Siri Shortcut)  --HTTP over Tailscale-->  Mac: Opie relay  --OSC/UDP-->  Nomad (Eos)
        internet                                   (dual-homed)    isolated lighting LAN
```

**Why the Mac relay exists:** the phone is only on the internet; the Nomad is only on the
isolated lighting network. The dual-homed Mac is the one machine on both, and Apple
Shortcuts can only speak HTTP (not OSC/UDP) — so the relay bridges HTTP → OSC.
See [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

---

## Install (easy path)

1. Get this repo onto the theatre **Mac**. Two ways:
   - **Clone with Git** *(recommended — enables automatic updates):*
     ```bash
     git clone https://github.com/Clobbyy/opie.git ~/Opie
     ```
   - **Or download the ZIP** from GitHub and unzip it somewhere permanent.
2. Open the folder and double-click **`install.command`**.
   - First time from a download, macOS may say *"unidentified developer."* Right-click the
     file → **Open** → **Open**. (It just runs the visible shell script in this folder.)
3. The **Opie Control** window opens. That's it.

The installer runs offline — **no pip, no virtualenv.** It uses the Mac's built-in
Python 3 to run the app straight from this folder, creates your config (with a freshly
generated security token) under `~/Library/Application Support/Opie/`, and drops an
**`Opie Control.command`** launcher in this folder to re-open it any time.

> **Keep this folder where it is** after installing — the app runs from here. (Put it
> somewhere permanent first, e.g. your Applications or home folder.)

### Updates are automatic

If you cloned with Git, Opie **keeps itself current** — no reinstalling to get changes:

- The relay fast-forwards to the latest code each time it starts (e.g. at login when
  autostart is on).
- The control panel checks on launch; there's also a **Check for updates** button and an
  **Auto-update** toggle in the window. When an update lands it restarts the relay onto the
  new code automatically.

Downloaded-ZIP and `pip` installs don't auto-update (the window just says so) — re-run
`install.command` after pulling, or `pip install -U`, to update those. To remove everything
later, double-click **`uninstall.command`**.

> Requires **Python 3** on the Mac. The control panel needs **Tk ≥ 8.6**, but Apple's
> built-in `/usr/bin/python3` ships the deprecated **Tk 8.5**, which crashes on recent
> macOS. So the installer looks for a good Python and, if it doesn't find one, offers to
> install one (via Homebrew's `python-tk`) or points you to
> [python.org](https://www.python.org/downloads/macos/) (its Python includes Tk 8.6).
> The relay itself runs headless on any Python 3 — only the window needs the newer Tk.

### Install for developers (pip, from the private repo)

```bash
pip install "git+ssh://git@github.com/Clobbyy/opie.git"     # SSH (recommended)
# or, with an HTTPS token:
pip install "git+https://github.com/Clobbyy/opie.git"
```

Gives you the `opie`, `opie-gui`, and `opie-sniff` commands. (This path needs internet.)

---

## The Opie Control app

One window, four sections:

- **Setup** — Console IP, ports, bind address, destructive policy, and the shared token
  (with **Generate** / **Copy**). Edit the **macro map** (spoken word → console macro #)
  and **key map** (spoken word → console key). **Save** or **Save & Restart**.
- **Control bar** — **Start / Stop / Restart**, plus **Autostart at login** (installs a
  launchd agent so the relay runs whenever the Mac boots) and **Auto-update** (keep the
  Git clone current). A status dot shows running/stopped and the listening URL.
- **Logs** — live tail of the relay log, with Pause / Clear / Reveal in Finder.
- **Test & Help** — send a phrase straight to the relay and hear the spoken reply, check
  whether the console IP is reachable, and grab the **iPhone Shortcut** URL + token.

---

## What you can say

Opie understands natural phrases and, as a fallback, **any command the console
itself understands** — so the full Eos vocabulary is reachable by voice:

- **Set levels** — "channel 5 at full", "channels 1 through 8 at 75",
  "group 3 at half", "submaster 2 to 80 percent", "address 513 at 100".
- **Current selection** — "full", "out", "home", "at 50", "75 percent".
- **Actions** — "sneak", "highlight", "mark", "park", "unpark", "rem dim",
  "make manual", "assert", "capture" (alone = current selection; or
  "channel 5 sneak" / "sneak channel 5").
- **Parameters** — "gobo 3", "pan 50", "tilt -20", "zoom 75", "iris 20", "hue 180".
- **Color** — "make channel 7 red", "group 3 blue", "channel 9 color palette 2".
- **Playback** — "go", "stop", "go to cue 10", "fire cue 5", "macro 5", "preset 3".
- **Your scene words** — map a spoken word to a console macro (e.g. "blackout").
- **Anything else** — prefix with "command …" to type it straight onto the Eos
  command line (e.g. "command chan 1 thru 10 effect 3").

See [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md) for the full vocabulary table.

## Console + phone setup

### 1. Enable OSC on Nomad/Eos
- `ECU > Settings > Network > Interface Protocols` → enable **"UDP Strings & OSC"** on the
  lighting-network interface.
- `Setup > System > Show Control > OSC` → **OSC RX = on**, **OSC UDP RX Port = 8000**.
- Note the Nomad's **lighting-network IP** and put it in **Setup → Console IP**.
  Full details: [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

### 2. Remote access (Tailscale)
- Install Tailscale on the **Mac** and **iPhone**, signed into the **same account**.
- In **Setup → Bind address** you can put the Mac's `100.x` Tailscale IP to refuse
  non-tailnet clients (or leave `0.0.0.0`).
- *(Same-Wi-Fi alternative: skip Tailscale and use the Mac's LAN IP; on-site only.)*

### 3. Build the iPhone Shortcut
Use **Test & Help → Phone setup info** for the exact URL + token, then follow
[`shortcuts/SHORTCUT_SETUP.md`](shortcuts/SHORTCUT_SETUP.md). Then:
**"Hey Siri, Lighting Control" → "channel 5 at full."**

---

## Test offline (no console, no risk)

```bash
python3 -m opie.sniffer 8000     # terminal A: prints the OSC the relay would send
# In the GUI set Console IP = 127.0.0.1, Start, then use the Test box:
#   "channel 5 at full"  ->  sniffer prints  /eos/chan/5/full
```

Run the unit tests (no hardware):

```bash
python3 tests/test_parser.py
```

> If you pip-installed, the same commands are available as `opie-sniff`, `opie`, etc.

---

## Command line (optional)

From the project folder (the offline / no-pip way):

```bash
python3 -m opie                    # run the relay (reads the default config)
python3 -m opie --config /p.json   # custom config
python3 -m opie.gui                # the control panel
python3 -m opie.sniffer [port]     # loopback OSC sniffer
```

After a `pip install`, the same things are the commands `opie`, `opie-gui`, `opie-sniff`.

Config lives at `~/Library/Application Support/Opie/config.json`; logs at
`~/Library/Logs/Opie/`. Override the config path with the `OPIE_CONFIG` env var.

---

## Security
- Every request needs the shared `X-Token`; wrong/missing → `401`.
- Full OSC is supported (any `/eos/*` command, the `command …` passthrough, and
  `press <key>`). The **`destructive_policy`** setting gates the dangerous paths
  (`/eos/cmd` strings and key presses):
  - `block_all` — output/playback only.
  - `record_update` *(default)* — Record/Update/Store allowed; Delete/Wipe/Patch blocked.
  - `allow_all` — everything.
  Blocked commands send no OSC and reply "blocked for safety."
- Keep it on Tailscale; **don't** port-forward the relay to the public internet.
- The config file (which holds your token) is stored owner-only and never committed.
  If your token has ever been shared, click **Generate** → **Save & Restart** to rotate it.

## Extending it
- Add scene words: create a console macro, add it to the **macro map** in Setup.
- Tune colors: edit `_COLORS` in [`opie/parser.py`](opie/parser.py).
- New phrasings: add a rule in `parser.parse()` and a case in `tests/test_parser.py`.

## Selling / distribution notes
- This repo is **private**; the included [`LICENSE`](LICENSE) is a proprietary template
  (have a lawyer adapt it before you sell).
- Easiest model today: grant a buyer access to the private repo (or send a zip) and have
  them run `install.command`.
- A future signed `.app` bundle would remove the Gatekeeper prompt for non-technical
  buyers — that needs an Apple Developer ID and notarization.

## Project layout
```
opie/                 the package
  relay.py            HTTP -> OSC relay              (entry point: opie)
  parser.py           natural-language -> OSC translator (rule-based, no AI)
  osclib.py           minimal OSC encoder/decoder (stdlib only)
  gui.py              Opie Control panel             (entry point: opie-gui)
  config.py           config + path resolution (token generation, log path)
  service.py          launchd autostart control
  sniffer.py          loopback OSC sniffer           (entry point: opie-sniff)
  resources/          config.example.json, launchd plist template
tests/test_parser.py  offline tests (no hardware)
docs/OSC_REFERENCE.md the Eos OSC commands + console setup
shortcuts/SHORTCUT_SETUP.md  build the iPhone Shortcut
install.command / uninstall.command   double-click installers
```

No external dependencies — everything is Python standard library.
