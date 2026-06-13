# Opie — ETC Nomad voice control via Siri

Speak normal phrases to Siri → they become **ETC Eos OSC** messages → your **Nomad**
console reacts. No cloud, no subscriptions, no API credits — just a small relay on your
theatre Mac and a Shortcut on your phone, managed from a browser panel. It runs entirely
on the Mac's built-in Python — there's nothing else to install.

```
iPhone (Siri Shortcut)  --HTTP over Tailscale-->  Mac: Opie relay  --OSC/UDP-->  Nomad (Eos)
        internet                                   (dual-homed)    isolated lighting LAN
```

The phone is on the internet; the Nomad is on the isolated lighting network. The
dual-homed Mac is the one machine on both, and Apple Shortcuts can only speak HTTP — so
the relay bridges HTTP → OSC.

---

## Install

On the theatre **Mac**, open **Terminal** (⌘-Space, type "Terminal", Return) and paste
this one line:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/install.sh)"
```

That's the whole install. It downloads Opie, generates your security token, starts the
relay, sets it to run at every login, and adds an **Opie** app to your Applications. It
asks once for your Console (Nomad) IP — press Return to set it later in the app.

- **Update:** re-paste the install command (or use **Check for updates** in the app).
- **Uninstall:** paste
  `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Clobbyy/opie/main/uninstall.sh)"`

No "unidentified developer" prompt — `curl` downloads aren't quarantined by macOS, so
nothing here gets blocked by Gatekeeper.

---

## Set up your console & phone

**1. Enable OSC on the Nomad/Eos**
- `ECU > Settings > Network > Interface Protocols` → enable **"UDP Strings & OSC"** on the
  lighting-network interface.
- `Setup > System > Show Control > OSC` → **OSC RX = on**, **OSC UDP RX Port = 8000**.
- Note the Nomad's lighting-network IP — you'll enter it in the panel under **Setup →
  Console IP**.

**2. Connect your phone (Tailscale)**
- Install Tailscale on the **Mac** and **iPhone**, signed into the same account.
- *(On-site alternative: skip Tailscale and use the Mac's Wi-Fi/LAN IP.)*

**3. Build the iPhone Shortcut**
- Open the panel's **Test & phone setup** section for your exact URL + token, then follow
  [`shortcuts/SHORTCUT_SETUP.md`](shortcuts/SHORTCUT_SETUP.md).
- Then say: **"Hey Siri, Lighting Control" → "channel 5 at full."**

Full console details: [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

---

## The control panel

Open **Opie** (Applications or Spotlight) to launch the control panel in its own
window (it serves a localhost page on `http://localhost:8766` — reachable only from
this Mac). Top to bottom:

- **Status** — a live signal meter and a big Running/Stopped readout, the relay's
  listening URL, Start / Stop / Restart, and Autostart at login. If the running relay
  is behind the installed version, a notice prompts you to update.
- **Setup** — Console IP, ports, security token, safety policy, the Eos OSC user, and
  your word maps (spoken word → console macro, spoken word → console key). Save or
  Save & restart.
- **Test & phone setup** — send a phrase and read the console's reply, check the
  console is reachable, and copy your iPhone Shortcut URL + token.
- **Log** — live tail of the relay, for the current run.

The sun/moon button (top right) switches between dark and light; it opens dark, made
for the booth. To add a scene word (e.g. "blackout"): make a console macro, then map
the word to it in **Setup**.

---

## What you can say

Opie understands natural phrases and, as a fallback, **any command the console itself
understands** — so the full Eos vocabulary is reachable by voice:

- **Set levels** — "channel 5 at full", "channels 1 through 8 at 75", "group 3 at half",
  "submaster 2 to 80 percent", "address 513 at 100".
- **Current selection** — "full", "out", "home", "at 50", "75 percent".
- **Actions** — "sneak", "highlight", "mark", "park", "rem dim", "make manual", "assert"
  (alone = current selection, or "channel 5 sneak").
- **Parameters** — "gobo 3", "pan 50", "tilt -20", "zoom 75", "iris 20", "hue 180".
- **Color** — "make channel 7 red", "group 3 blue", "channel 9 color palette 2".
- **Playback** — "go", "stop", "go to cue 10", "fire cue 5", "macro 5", "preset 3".
- **Anything else** — prefix with "command …" to type straight onto the Eos command line
  (e.g. "command chan 1 thru 10 effect 3").

Full vocabulary table: [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

---

## Security

- Every request needs your shared token; a wrong or missing token is rejected.
- The **safety policy** (Setup) gates the risky commands:
  - **block_all** — output/playback only.
  - **record_update** *(default)* — Record/Update/Store allowed; Delete/Wipe/Patch blocked.
  - **allow_all** — everything.
- Keep the relay on Tailscale or your local network — **don't** port-forward it to the
  public internet.
- Your token is stored privately on the Mac and never shared. If it ever leaks, click
  **Generate → Save & Restart** to rotate it.

---

## Try it without a console

```bash
python3 -m opie.sniffer 8000     # prints the OSC the relay would send
# In the panel: set Console IP = 127.0.0.1, Start, then use the Test box —
#   "channel 5 at full"  ->  /eos/chan/5/full
```

Config lives at `~/Library/Application Support/Opie/config.json`; logs at
`~/Library/Logs/Opie/`.
