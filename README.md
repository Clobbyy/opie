# Opie — ETC Nomad voice control via Siri

Speak normal phrases to Siri → they become **ETC Eos OSC** messages → your **Nomad**
console reacts. No API credits, no subscriptions, no cloud — just a tiny Python relay
on the theatre Mac and an Apple Shortcut on your phone, managed from a browser control
panel. Everything runs on the Mac's built-in Python 3 — nothing else to install.

```
iPhone (Siri Shortcut)  --HTTP over Tailscale-->  Mac: Opie relay  --OSC/UDP-->  Nomad (Eos)
        internet                                   (dual-homed)    isolated lighting LAN
```

**Why the Mac relay exists:** the phone is only on the internet; the Nomad is only on the
isolated lighting network. The dual-homed Mac is the one machine on both, and Apple
Shortcuts can only speak HTTP (not OSC/UDP) — so the relay bridges HTTP → OSC.
See [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

---

## Install

On the theatre **Mac**, open **Terminal** (press ⌘-Space, type "Terminal", Return) and
paste this one line:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/install.sh)"
```

That's the whole install. It downloads Opie, generates your security token, starts the
relay, sets it to run at every login, and adds an **Opie** app to your Applications. It
asks once for your Console (Nomad) IP — press Return to set it later in the app instead.

- **No Apple Developer ID, no "unidentified developer" prompt.** macOS only flags files
  that carry the *quarantine* tag (set by browsers/Mail) — `curl`/`git` downloads don't, so
  nothing here is ever blocked.
- **Nothing else to install.** Both the relay *and* the control panel use only Python's
  standard library, so the Mac's built-in `python3` is all you need — no Tk, no python.org,
  no Homebrew. The panel opens in your **browser** (it's a tiny localhost-only web app).
- **Auto-updates.** The relay fast-forwards to the latest code each time it starts; the app
  also has a **Check for updates** button. Re-paste the command any time to update by hand.

**Update:** re-paste the install command.
**Uninstall:** paste
`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/uninstall.sh)"`.

> The install command works for anyone because the repo is **public**. If you fork it
> private, the command needs the code hosted somewhere fetchable without a login (see
> *Selling / distribution notes* below). Developers can also `pip install` the repo to get
> the `opie`, `opie-panel`, and `opie-sniff` commands.

---

## The Opie Control panel

Open **Opie** (Applications/Spotlight) and it opens a control panel in your browser
(`http://localhost:8766` — localhost only, so just you can reach it). It's pure
standard library, so it needs **no Tk** and runs on the Mac's built-in Python. One page,
four sections:

- **Relay** — **Start / Stop / Restart** and **Autostart at login** (installs a launchd
  agent so the relay runs whenever the Mac boots). A status dot shows running/stopped and
  the listening URL.
- **Setup** — Console IP, ports, bind address, destructive policy, **Auto-update**, and the
  shared token (with **Generate** / **Copy**). Edit the **macro map** (spoken word → console
  macro #) and **key map** (spoken word → console key). **Save** or **Save & Restart**.
- **Test & phone setup** — send a phrase straight to the relay and see the spoken reply,
  check whether the console is reachable, check for updates, and copy the **iPhone Shortcut**
  URL + token.
- **Logs** — live tail of the relay log, with Pause / Clear.

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
Use the panel's **Test & phone setup** section for the exact URL + token, then follow
[`shortcuts/SHORTCUT_SETUP.md`](shortcuts/SHORTCUT_SETUP.md). Then:
**"Hey Siri, Lighting Control" → "channel 5 at full."**

---

## Test offline (no console, no risk)

```bash
python3 -m opie.sniffer 8000     # terminal A: prints the OSC the relay would send
# In the panel set Console IP = 127.0.0.1, Start, then use the Test box:
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
python3 -m opie.panel              # the browser control panel
python3 -m opie.sniffer [port]     # loopback OSC sniffer
```

After a `pip install`, the same things are the commands `opie`, `opie-panel`, `opie-sniff`.

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
- The included [`LICENSE`](LICENSE) is a proprietary template (have a lawyer adapt it
  before you sell). The one-line installer needs the code **publicly fetchable**, so the
  simplest setup is a **public repo** — you can still sell it with a license key; only the
  source becomes visible.
- **To keep the code private** while keeping the one-paste install, host `install.sh` plus a
  tarball of the code at a public URL you control (e.g. a Vercel deployment) and point the
  `curl` command there — buyers never sign in or hit Gatekeeper, and you can gate or rotate
  the URL. (Ask and this can be scaffolded.)
- No Apple Developer ID is required either way: `curl`/`git` downloads aren't quarantined, so
  the installer never trips Gatekeeper. A signed `.pkg` would only matter if you later want a
  browser-download install.

## Project layout
```
opie/                 the package
  relay.py            HTTP -> OSC relay              (entry point: opie)
  parser.py           natural-language -> OSC translator (rule-based, no AI)
  osclib.py           minimal OSC encoder/decoder (stdlib only)
  panel.py            browser control panel (stdlib)         (entry point: opie-panel)
  config.py           config + path resolution (token generation, log path)
  service.py          launchd autostart control
  update.py           self-update (git pull) on relay start
  sniffer.py          loopback OSC sniffer           (entry point: opie-sniff)
  resources/          config.example.json, launchd plist template
install.sh            the one-line installer (curl | bash)
uninstall.sh          the one-line uninstaller
tests/test_parser.py  offline tests (no hardware)
docs/OSC_REFERENCE.md the Eos OSC commands + console setup
shortcuts/SHORTCUT_SETUP.md  build the iPhone Shortcut
.github/workflows/    CI (runs the test suite)
```

No external dependencies — everything is Python standard library.
