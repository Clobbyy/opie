# ETC Eos / Nomad OSC Reference (for this project)

This is the subset of the ETC Eos OSC implementation that the relay's parser
targets, plus the console settings you must enable. Sourced from ETC's official
docs (links at the bottom). Eos = the software family that **Nomad** runs.

## Enabling OSC on Nomad/Eos

1. **Network interface:** `ECU > Settings > Network > Interface Protocols` →
   enable **"UDP Strings & OSC"** on the network interface connected to the
   **isolated lighting network** (the one the Mac reaches).
2. **OSC on/ports:** `Setup > System > Show Control > OSC` →
   - `{OSC RX}` = **enabled**
   - `{OSC UDP RX Port}` = **8000**  ← the relay SENDS here
   - `{OSC TX}` / `{OSC UDP TX Port}` = 8001 (only needed if you later want
     feedback from the console; this project doesn't require it)
3. Note the Nomad computer's **lighting-network IP** — that's the **Console IP**
   in Opie Control (the `NOMAD_IP` config value). Make sure the Mac can `ping` it.

> Ports are arbitrary but must match between the relay and Eos. ETC recommends
> 8000/8001. TCP (3032/3037) is also possible but this project uses UDP.

## Value ranges

| Target | Level range |
|---|---|
| channel / group / address intensity | `0.0 – 100.0` (percent) |
| submaster / fader | `0.0 – 1.0` |
| DMX | `0 – 255` |
| RGB color | `0.0 – 1.0` each |
| Hue / Saturation | hue `0–360`, sat `0–100` |
| Pan / Tilt | `0.0 – 1.0` |

## Command set used by the parser

`X = Y` below means: OSC **address** `X` with a single **argument** `Y`.
Action-style addresses (e.g. `.../full`) are sent **with no argument**.

### Command line
- `/eos/cmd "<text>"` — type onto the command line. `#` in the string = **Enter**
  (execute). Supports `%1 %2` substitution with trailing args.
- `/eos/newcmd "<text>"` — same, but clears the command line first.

The relay uses the command line for **ranges, lists, relative levels**, **action
verbs** (Sneak, Mark, Rem_Dim, …), and as a **fallback** for any phrase that names
a known Eos keyword but doesn't match a dedicated rule — which is what makes the
*entire* Eos command set reachable by voice. The relay **blocks** any command-line
string containing destructive verbs (Delete, Wipe, Patch, …) per the
`destructive_policy`. On the wire it sends `/eos/user/<n>/newcmd` (see the next
section) so each command starts on a clean line and can't collide with anyone else.

### User scoping — playing nicely with other OSC senders
Eos runs un-scoped OSC input from **every** sender on the **same** command line and
selection (the console's OSC user). If two systems send at once — this relay plus
e.g. QLab network cues or a sound desk — their text interleaves and both get
corrupted commands. Almost every input address can instead be prefixed with
`/eos/user/<number>/` to run it as a specific user with its **own** command line.

The relay therefore sends everything scoped to `config["OSC_USER"]`:
- `0` *(default)* — Eos's invisible **background user** (the context background
  macros run in). Voice never appears on, or disturbs, anyone's command line.
- a positive number — that user's command line (visible if a display follows it).
- `-1` — legacy behaviour: un-scoped, shared with other OSC senders.

The only message the relay leaves un-scoped is `/eos/ping`, which has no `/user`
form.

### Channels
- `/eos/chan/<n> = <0–100>` — set intensity
- `/eos/chan/<n>/full` · `/out` · `/home` · `/min` · `/max` · `/level`
- `/eos/chan/<n>/+%` · `/-%`
- `/eos/chan/<n>/color/rgb = <r>,<g>,<b>` (0.0–1.0)
- `/eos/chan/<n>/param/<param> = <value>`
- `/eos/chan/<n>/dmx = <0–255>`

### Groups (same grammar as channels)
- `/eos/group/<n> = <0–100>`, `/eos/group/<n>/full|out|home|min|max`, color, etc.

### Addresses (absolute DMX)
- `/eos/addr/<n> = <0–100>`

### Current selection
- `/eos/at = <0–100>`, `/eos/at/full|out|home|min|max`, `/eos/at/+%|-%`

### Submasters (0.0–1.0)
- `/eos/sub/<n> = <0.0–1.0>`
- `/eos/sub/<n>/fire` ( `=1.0` bump on / `=0.0` off )
- `/eos/sub/<n>/full` · `/out`

### Faders
- `/eos/fader/<bank>/<index> = <0.0–1.0>`
- `/eos/fader/<bank>/<index>/fire`

### Cues / playback
- `/eos/cue/<n>/fire`
- `/eos/cue/<list>/<cue>/fire`
- GO key: `/eos/key/go_0`  (press = arg `1.0`, release = `0.0`)
- Stop/Back key: `/eos/key/stop_back_main_cuelist`

### Palettes / presets / macros
- `/eos/ip|cp|fp|bp/<n>/fire` — Intensity/Color/Focus/Beam palette
- `/eos/preset/<n>/fire`
- `/eos/macro/<n>/fire` ( `=1.0` press )

### Utility
- `/eos/ping "<anything>"` — connectivity test (the relay's "ping"/"test" verb)
- `/eos/key/<keyname>` — any console hardkey
- `/eos/user = <n>` — set the OSC user

## What you can say (spoken vocabulary)

The parser maps natural phrases to the addresses above. A non-exhaustive map of
what's recognized — anything not listed still works via the **command-line
fallback** (any phrase containing a known Eos word) or the explicit **`command …`**
prefix:

| You say | Eos result |
|---|---|
| `channel 5 at full` / `channel 5 sneak` | set / sneak channel 5 |
| `channels 1 thru 8 at 75` | `Chan 1 Thru 8 At 75` |
| `group 3 red` · `channel 7 color palette 2` | color / palette recall |
| `gobo 3` · `pan 50` · `iris 20` | parameter on the current selection |
| `full` · `out` · `home` · `at 50` · `75 percent` | level on the current selection |
| `sneak` · `highlight` · `mark` · `park` · `rem dim` · `make manual` | action on the current selection |
| `sneak channel 5` ( = `channel 5 sneak` ) | verb spoken before the target works too |
| `go` · `stop` · `go to cue 10` · `fire cue 5` | playback |
| `macro 5` · `preset 3` · `bump sub 4` | fire macro / preset / submaster |
| `blackout` (your macro-mapped word) | fires the mapped console macro |
| `command <anything>` | raw command-line passthrough |

Action verbs and bare parameters are typed onto the **relay's own** Eos command
line (see *User scoping* above), so they act on whatever channels were **last
selected by voice** — e.g. "channel 5 at 50" then "gobo 3" chains as expected.
With `OSC_USER: -1` they instead share the console's OSC user and act on its
selection — at the cost of interfering with other OSC senders.

## Notes / gotchas
- **Key names** (`go_0`, `stop_back_main_cuelist`) can vary by console
  configuration. They're overridable in `config.json → key_map` without editing
  code. If "go" doesn't work, confirm the exact key name in the Eos OSC docs.
- **"Blackout" is intentionally not a raw OSC command here.** Instead, create a
  **macro** on the console (e.g. Macro 901 = your blackout/restore look) and map
  the spoken word to it in `config.json → macro_map`. This keeps voice control
  reversible and under the programmer's control.
- **Colors are approximate RGB** starting points (see `parser._COLORS`); tune to
  your rig, or switch to color palettes (`/eos/cp/<n>/fire`) for exact looks.

## Sources
- [Eos OSC Dictionary](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/OSC_Dictionary.htm)
- [Using OSC with Eos — Eos Control](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/Using_OSC_with_Eos/OSC_Eos_Control.htm)
- [Eos OSC Setup](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/Using_OSC_with_Eos/Eos_OSC_Setup.htm)
- [Triggering Eos from QLab using OSC](https://support.etcconnect.com/ETC/Consoles/Eos_Family/Software_and_Programming/Triggering_Eos_from_QLab_using_OSC)
- [System > Show Control](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/07_Setup/01_System/System_Show_Control.htm)
