# Siri Shortcut Setup — "Lighting Control"

This builds the iPhone side. It captures what you say, sends it to the Mac relay
over Tailscale, and speaks the confirmation back. Hands-free: **"Hey Siri,
Lighting Control."**

You need two values from the Mac:
- **Relay address:** `http://<mac-tailscale-name>:8765` (your Mac's MagicDNS name,
  e.g. `http://theatre-mac:8765`, or its `100.x.y.z` Tailscale IP). See README.
- **Token:** your shared secret. The easiest way to get both values is the GUI:
  **Opie Control → Test & Help → Phone setup info** shows the exact URL and token
  with copy buttons. (The token is also in your config at
  `~/Library/Application Support/Opie/config.json`, kept out of git on purpose.)

---

## A. Primary shortcut — "Lighting Control" (hands-free voice)

Open the **Shortcuts** app → **+** (new shortcut) → name it exactly **Lighting
Control** (this is the Siri trigger phrase). Add these actions in order:

1. **Dictate Text**
   - Tap to expand → set **Language** to your language; **Stop Listening: After
     Pause** (or *On Tap* if you prefer to tap to finish).

2. **Text**
   - Type the relay command URL: `http://<mac-tailscale-name>:8765/command`
   - (Using a *Text* action keeps the URL tidy; you'll reference it next.)

3. **Get Contents of URL**
   - **URL:** select the *Text* from step 2.
   - Tap **Show More**:
     - **Method:** `POST`
     - **Headers:** add one →
       - Key: `X-Token`   Value: `YOUR_TOKEN` (from Phone setup info / your config)
       - (optional) Key: `Content-Type`  Value: `text/plain`
     - **Request Body:** `File` →  set it to **Text**, then select the
       **Dictated Text** variable from step 1 as the body content.
       *(Choosing the "Text" body type and dropping in the Dictated Text sends
       the raw phrase as the POST body, which is what the relay expects.)*

4. **Speak Text**
   - Text: select **Contents of URL** (the relay's reply).
   - This reads back e.g. "Channel 5 full" or a hint if it didn't understand.
   - *(Alternative: use **Show Notification** or **Show Result** instead of
     Speak Text if you don't want it spoken aloud.)*

Tap **Done**.

### Use it
- Say **"Hey Siri, Lighting Control"** → Siri listens → say
  *"channel 5 at full"* → it confirms aloud.
- Or, to chain it in one breath, some iOS versions let you say
  *"Hey Siri, Lighting Control, channel 5 at full"* and pass the trailing text;
  if that's unreliable on your device, the two-step flow above always works.

---

## B. Optional one-tap / one-phrase macro shortcuts

For instant looks you don't want to dictate (e.g. **Blackout**), duplicate the
idea but skip dictation:

1. **Text** → `http://<mac-tailscale-name>:8765/command`
2. **Get Contents of URL** → `POST`, header
   `X-Token: YOUR_TOKEN`, **Request Body:
   Text** = the literal phrase, e.g. `blackout` (must match a key in your
   **macro map**) or any phrase like `channels 1 thru 200 at full`.
3. **Speak Text** ← Contents of URL (optional).

Name each one for its Siri phrase: **"Blackout"**, **"House Lights Up"**,
**"Restore"**, etc. Then **"Hey Siri, Blackout"** fires instantly.

You can also add these to the Home Screen (share-sheet → Add to Home Screen) or
a Control Center / Lock Screen widget for one-tap access.

---

## Phrases the relay understands (examples)

| Say… | Does |
|---|---|
| "channel 5 at full" | Ch 5 → 100% |
| "channel 12 at 50 percent" | Ch 12 → 50% |
| "channels 1 through 8 at 75" | Ch 1–8 → 75% |
| "channels 1 and 3 and 5 at full" | those channels → full |
| "group 3 at half" | Group 3 → 50% |
| "channel 9 out" / "channel 9 off" | Ch 9 → 0% |
| "channel 4 up 10" / "group 2 down 20" | relative ± |
| "make channel 7 red" / "group 3 blue" | set color (channel or group) |
| "group 5 color palette 2" | recall Color Palette 2 onto group 5 |
| "channel 9 focus palette 1" | recall a Focus/Beam/Intensity palette too |
| "color palette 2" / "cp 4" | recall a palette onto the current selection |
| "channel 5 pan 50" / "group 2 tilt -20" | moving-light parameters |
| "channel 5 zoom 75" / "iris 80" / "edge 40" | zoom/iris/edge/frost/gobo/hue/saturation |
| "press live" / "press blind" / "press highlight" | press any console key |
| "command &lt;anything&gt;" / "console &lt;anything&gt;" | speak a raw Eos command line (full control) |
| "submaster 2 to 80 percent" | Sub 2 → 0.80 |
| "bump sub 4" | momentary bump |
| "go" / "stop" / "back" | playback transport |
| "go to cue 10" / "jump to cue 3" | jump to a cue (Go To Cue, with timing) |
| "go to cue 10 in list 2" | jump to a cue on a specific list |
| "fire cue 10" / "cue 4 in list 2" | assert a cue immediately |
| "macro 5" / "preset 3" | fire macro / recall preset |
| "blackout" / "house lights up" | fire your mapped console macro |
| "ping" / "test" | confirm the relay is connected |

Numbers can be spoken as words too ("channel twenty three at seventy five").

> **Color only shows if intensity is up.** Setting a color/palette changes the
> *hue*, not the level — if the group is at 0% you won't see anything. Bring it
> up first (e.g. "group 3 at full" then "group 3 blue").

Use **"through"/"thru"** for ranges (not "to", which means "set to a level").

---

## Full control: the "command" passthrough

For anything the structured phrases don't cover, prefix with **"command"** (or
"console") and just speak the Eos command line — it's translated token-for-token
and sent to the console. This reaches **every** command Eos has.

| Say… | Sends to command line |
|---|---|
| "command channel 5 thru 10 at full" | `Chan 5 Thru 10 At Full` |
| "command group 2 color palette 4" | `Group 2 Color_Palette 4` |
| "command record cue 5" | `Record Cue 5` |
| "command go to cue 3 time 5" | `Go_To_Cue 3 Time 5` |
| "command sub 1 at 75" | `Sub 1 At 75` |

Tips: say **"thru"** for ranges, **"and"** for `+`, **"minus"** for `-`,
multi-word buttons just work ("go to cue" → `Go_To_Cue`, "color palette" →
`Color_Palette`). You don't need to say "enter" — it's added automatically.

### Destructive commands
Controlled by `destructive_policy` in `config.json`:
- `"record_update"` *(your current setting)* — Record/Update/Store allowed;
  **Delete/Wipe/Patch blocked** (a misheard phrase can't erase your show).
- `"block_all"` — output/playback only; no Record either.
- `"allow_all"` — everything, including Delete/Wipe/Patch.

Blocked commands make the relay reply "That command was blocked for safety." and
**no OSC is sent**.

---

## Troubleshooting
- **Nothing happens / network error:** confirm Tailscale is connected on both
  devices and `http://<mac-tailscale-name>:8765/health` returns `ok` in Safari.
- **"Unauthorized":** the `X-Token` header doesn't match `config.json → TOKEN`.
- **It speaks a hint instead of acting:** rephrase per the table above.
- **Console doesn't react but the phone says success:** check `NOMAD_IP`/port in
  `config.json`, that OSC RX is enabled in Eos, and that "UDP Strings & OSC" is on
  for the lighting NIC. Watch `relay/relay.out.log` for the `OSC -> …` lines.
