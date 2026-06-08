# ETC Nomad Voice Control via Siri

Speak normal phrases to Siri → they become **ETC Eos OSC** messages → your
**Nomad** console reacts. No API credits, no subscriptions, no cloud — just a
tiny Python relay on the theatre Mac and an Apple Shortcut on your phone.

```
iPhone (Siri Shortcut)  --HTTP over Tailscale-->  Mac relay.py  --OSC/UDP-->  Nomad (Eos)
        internet                                  (dual-homed)   isolated lighting LAN
```

**Why the Mac relay exists:** the phone is only on the internet; the Nomad is
only on the isolated lighting network. The dual-homed Mac is the one machine on
both, and Apple Shortcuts can only speak HTTP (not OSC/UDP) — so the relay bridges
HTTP → OSC. See [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

## What's here
```
relay/
  relay.py        HTTP -> OSC relay (run this on the Mac)
  parser.py       natural-language -> OSC translator (rule-based, no AI)
  osclib.py       minimal OSC encoder/decoder (stdlib only)
  osc_sniffer.py  loopback test tool — prints OSC without a console
  config.json     your settings (Nomad IP, token, macro map)
  com.etcvoice.relay.plist   launchd autostart
tests/test_parser.py         offline tests (no hardware)
docs/OSC_REFERENCE.md        the Eos OSC commands + console setup
shortcuts/SHORTCUT_SETUP.md  build the iPhone Shortcut
```

## Requirements
- The theatre **Mac**, with a NIC on the **internet** and a NIC/route to the
  **isolated lighting network** (it must be able to `ping` the Nomad).
- **Python 3** on the Mac (`python3 --version`; if missing, `xcode-select --install`).
- **Tailscale** (free) on the Mac and the iPhone — or both on the same Wi-Fi.
- **Nomad/Eos** with OSC enabled (below).

---

## Setup

### 1. Enable OSC on Nomad/Eos
- `ECU > Settings > Network > Interface Protocols` → enable **"UDP Strings & OSC"**
  on the lighting-network interface.
- `Setup > System > Show Control > OSC` → **OSC RX = on**, **OSC UDP RX Port = 8000**.
- Note the Nomad's **lighting-network IP**. Full details: [`docs/OSC_REFERENCE.md`](docs/OSC_REFERENCE.md).

### 2. Remote access (Tailscale)
- Install Tailscale on the **Mac** and **iPhone**, sign both into the **same account**.
- Note the Mac's **MagicDNS name** (e.g. `theatre-mac`) or `100.x.y.z` IP — the
  phone will reach the relay there from anywhere (cellular or any Wi-Fi).
- *(Same-Wi-Fi alternative: skip Tailscale and use the Mac's LAN IP; on-site only.)*

### 3. Configure the relay
Copy the template (this file is git-ignored because it holds your secret):
```bash
cp relay/config.example.json relay/config.json
```
Then edit [`relay/config.json`](relay/config.json):
- `NOMAD_IP` → the Nomad's lighting-network IP (for a dry run, leave `127.0.0.1`).
- `TOKEN` → a long random secret (the Shortcut sends the same value):
  `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- `macro_map` → map spoken words to **macros you've created on the console**
  (e.g. `"blackout": 901`). Reversible looks belong here.
- `BIND_ADDR` → `0.0.0.0` is fine behind Tailscale/NAT; or set the Mac's `100.x`
  Tailscale IP to bind tighter.

### 4. Test offline (no console, no risk)
```bash
cd /Users/techbooth/Opie
python3 tests/test_parser.py          # parser/encoder unit tests

# loopback: see the exact OSC that would be sent
python3 -u relay/osc_sniffer.py 8000  &   # terminal A
python3 -u relay/relay.py             &   # terminal B  (config NOMAD_IP=127.0.0.1)
curl -s -X POST http://127.0.0.1:8765/command \
     -H "X-Token: YOUR_TOKEN" --data "channel 5 at full"   # terminal C
#   -> prints "Channel 5 full"; sniffer prints "/eos/chan/5/full"
```

### 5. Go live
- Set `NOMAD_IP` to the real console and restart the relay.
- Sanity check from the Mac: `curl http://localhost:8765/health` → `ok`.
- From the phone (Safari): `http://<mac-tailscale-name>:8765/health` → `ok`.
- **Test on a spare channel first**, then exercise groups/subs/cues.

### 6. Autostart the relay (optional)
```bash
cp "relay/com.etcvoice.relay.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.etcvoice.relay.plist
# after editing config.json:
launchctl kickstart -k gui/$(id -u)/com.etcvoice.relay
```

### 7. Build the iPhone Shortcut
Follow [`shortcuts/SHORTCUT_SETUP.md`](shortcuts/SHORTCUT_SETUP.md). Then:
**"Hey Siri, Lighting Control" → "channel 5 at full."**

---

## Security
- Every request needs the shared `X-Token`; wrong/missing → `401`.
- Full OSC is supported (any `/eos/*` command, the `command …` passthrough, and
  `press <key>`). The **`destructive_policy`** setting gates the dangerous paths
  (`/eos/cmd` strings and key presses):
  - `"block_all"` — output/playback only.
  - `"record_update"` *(default)* — Record/Update/Store allowed; Delete/Wipe/Patch blocked.
  - `"allow_all"` — everything.
  Blocked commands send no OSC and reply "blocked for safety."
- Keep it on Tailscale; **don't** port-forward the relay to the public internet.
- Bind to the Tailscale IP (`BIND_ADDR`) if you want to refuse non-tailnet clients.

## Extending it
- Add scene words: create a console macro, add it to `macro_map`.
- Tune colors: edit `_COLORS` in `relay/parser.py` (or switch to color palettes).
- New phrasings: add a rule in `parser.parse()` and a case in `tests/test_parser.py`.
- A touch/voice **web app** can be added later on this same relay with no rework.

## Notes
- This folder lives inside the home git repo, so this project is **not** version
  controlled on its own. To version it, `git init` a dedicated repo here.
- No external dependencies — everything is Python standard library.
