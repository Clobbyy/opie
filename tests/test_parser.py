#!/usr/bin/env python3
"""
Offline tests for the NL->OSC parser and the OSC encoder. No hardware, no network.

Run:  python3 tests/test_parser.py
Exit code is non-zero if anything fails.
"""

import os
import sys

# Run from a clean clone with no install: put the repo root on the path so the
# `opie` package imports. (After `pip install`, the package is importable anyway.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opie import osclib   # noqa: E402
from opie import parser   # noqa: E402
from opie import relay    # noqa: E402

# (messages, policy, expected_safe_count) for the relay's destructive filter
POLICY_CASES = [
    ([("/eos/chan/5/full", [])], "record_update", 1),
    ([("/eos/cmd", ["Record Cue 5#"])], "record_update", 1),   # record allowed
    ([("/eos/cmd", ["Update Cue 5#"])], "record_update", 1),   # update allowed
    ([("/eos/cmd", ["Delete Cue 5#"])], "record_update", 0),   # delete blocked
    ([("/eos/cmd", ["Patch Chan 1#"])], "record_update", 0),   # patch blocked
    ([("/eos/cmd", ["Record Cue 5#"])], "block_all", 0),       # record blocked
    ([("/eos/cmd", ["Delete Cue 5#"])], "allow_all", 1),       # anything goes
    ([("/eos/key/delete", [1.0])], "record_update", 0),        # destructive key blocked
    ([("/eos/key/live", [1.0])], "record_update", 1),          # normal key ok
]

# (messages, OSC_USER, expected) for the user-scoping rewrite applied at send time
SCOPE_CASES = [
    # command line: scoped to the user AND upgraded to newcmd (clean line)
    ([("/eos/cmd", ["Chan 5 At 50#"])], 0,
     [("/eos/user/0/newcmd", ["Chan 5 At 50#"])]),
    ([("/eos/cmd", ["Go_To_Cue 10#"])], 99,
     [("/eos/user/99/newcmd", ["Go_To_Cue 10#"])]),
    # keys, implicit channel commands, subs, macros: scoped untouched otherwise
    ([("/eos/key/go_0", [1.0])], 0, [("/eos/user/0/key/go_0", [1.0])]),
    ([("/eos/chan/5/full", [])], 0, [("/eos/user/0/chan/5/full", [])]),
    ([("/eos/sub/4/fire", [1.0])], 0, [("/eos/user/0/sub/4/fire", [1.0])]),
    ([("/eos/macro/901/fire", [1.0])], 0, [("/eos/user/0/macro/901/fire", [1.0])]),
    # ping has no /user form — never rewritten
    ([("/eos/ping", ["voice-relay"])], 0, [("/eos/ping", ["voice-relay"])]),
    # OSC_USER = -1 -> legacy shared command line, nothing rewritten
    ([("/eos/cmd", ["Chan 5 At 50#"])], -1, [("/eos/cmd", ["Chan 5 At 50#"])]),
    ([("/eos/key/go_0", [1.0])], -1, [("/eos/key/go_0", [1.0])]),
    # junk config value falls back to the safe default (user 0)
    ([("/eos/chan/5/full", [])], "", [("/eos/user/0/chan/5/full", [])]),
]

CONFIG = {
    "macro_map": {"blackout": 901, "restore": 902, "house lights up": 903},
    "key_map": {},  # use built-in defaults (go_0 / stop_back_main_cuelist)
}

# (phrase, expected_messages)
OK_CASES = [
    ("channel 5 at full",            [("/eos/chan/5/full", [])]),
    ("channel 12 at 50 percent",     [("/eos/chan/12", [50.0])]),
    ("channel 12 50 percent",        [("/eos/chan/12", [50.0])]),
    ("channels 1 through 8 at 75",   [("/eos/cmd", ["Chan 1 Thru 8 At 75#"])]),
    ("group 3 at half",              [("/eos/group/3", [50.0])]),
    ("submaster 2 to 80 percent",    [("/eos/sub/2", [0.8])]),
    ("submaster 6 full",             [("/eos/sub/6/full", [])]),
    ("bump sub 4",                   [("/eos/sub/4/fire", [1.0]), ("/eos/sub/4/fire", [0.0])]),
    ("go",                           [("/eos/key/go_0", [1.0]), ("/eos/key/go_0", [0.0])]),
    ("stop",                         [("/eos/key/stop_back_main_cuelist", [1.0]),
                                      ("/eos/key/stop_back_main_cuelist", [0.0])]),
    ("fire cue 10",                  [("/eos/cue/10/fire", [])]),
    ("cue 4 in list 2",             [("/eos/cue/2/4/fire", [])]),
    # go-to-cue (canonical Go_To_Cue command line)
    ("go to cue 10",                 [("/eos/cmd", ["Go_To_Cue 10#"])]),
    ("goto cue 10.5",                [("/eos/cmd", ["Go_To_Cue 10.5#"])]),
    ("jump to cue 3",                [("/eos/cmd", ["Go_To_Cue 3#"])]),
    ("go to cue 10 in list 2",       [("/eos/cmd", ["Go_To_Cue 2/10#"])]),
    ("go to queue 4",                [("/eos/cmd", ["Go_To_Cue 4#"])]),  # Siri "queue"->"cue"
    # dictation variants: Q/que/queue, glued numbers, punctuation, homophones
    ("Go to Q10",                    [("/eos/cmd", ["Go_To_Cue 10#"])]),
    ("go to q 10",                   [("/eos/cmd", ["Go_To_Cue 10#"])]),
    ("Go to que 10.5.",              [("/eos/cmd", ["Go_To_Cue 10.5#"])]),
    ("go 2 cue 5",                   [("/eos/cmd", ["Go_To_Cue 5#"])]),
    ("go to cue to",                 [("/eos/cmd", ["Go_To_Cue 2#"])]),  # "cue two"
    ("go to cue 10, please",         [("/eos/cmd", ["Go_To_Cue 10#"])]),
    ("fire q 5 in cue list 2",       [("/eos/cue/2/5/fire", [])]),
    ("cue for",                      [("/eos/cue/4/fire", [])]),         # "cue four"
    ("Q1 go",                        [("/eos/cue/1/fire", [])]),
    ("channels 1, 3 and 5 at full",  [("/eos/cmd", ["Chan 1 + 3 + 5 At Full#"])]),
    ("channels 1-8 at 75",           [("/eos/cmd", ["Chan 1 Thru 8 At 75#"])]),
    ("channels 1 threw 8 at 75",     [("/eos/cmd", ["Chan 1 Thru 8 At 75#"])]),
    ("channel 5 @ 50",               [("/eos/chan/5", [50.0])]),
    ("channel5 at full",             [("/eos/chan/5/full", [])]),
    ("75%",                          [("/eos/at", [75.0])]),
    ("snake channel 5",              [("/eos/cmd", ["Chan 5 Sneak#"])]), # "sneak"
    ("black out",                    [("/eos/macro/901/fire", [1.0])]),
    ("sub master 4 at full",         [("/eos/sub/4/full", [])]),
    ("micro 5",                      [("/eos/macro/5/fire", [1.0])]),    # "macro"
    ("ram dim",                      [("/eos/cmd", ["Rem_Dim#"])]),      # "rem dim"
    ("channel too at full",          [("/eos/chan/2/full", [])]),        # "channel two"
    # colors
    ("make channel 7 red",           [("/eos/chan/7/color/rgb", [1.0, 0.0, 0.0])]),
    ("group 3 red",                  [("/eos/cmd", ["Group 3 Red 100 Green 0 Blue 0#"])]),
    ("group 3 blue",                 [("/eos/cmd", ["Group 3 Red 0 Green 0 Blue 100#"])]),
    # palettes
    ("group 5 color palette 2",      [("/eos/cmd", ["Group 5 Color_Palette 2#"])]),
    ("channel 7 color palette 3",    [("/eos/cmd", ["Chan 7 Color_Palette 3#"])]),
    ("group 2 cp 4",                 [("/eos/cmd", ["Group 2 Color_Palette 4#"])]),
    ("channel 9 focus palette 1",    [("/eos/cmd", ["Chan 9 Focus_Palette 1#"])]),
    ("color palette 2",              [("/eos/cmd", ["Color_Palette 2#"])]),
    ("cp 4",                         [("/eos/cmd", ["Color_Palette 4#"])]),
    ("groups 1 through 4 color palette 2", [("/eos/cmd", ["Group 1 Thru 4 Color_Palette 2#"])]),
    ("blackout",                     [("/eos/macro/901/fire", [1.0])]),
    ("house lights up",              [("/eos/macro/903/fire", [1.0])]),
    ("macro 5",                      [("/eos/macro/5/fire", [1.0])]),
    ("preset 3",                     [("/eos/preset/3/fire", [1.0])]),
    ("chan 5 out",                   [("/eos/chan/5/out", [])]),
    ("group 2 up 10",                [("/eos/cmd", ["Group 2 At +10#"])]),
    ("channel 9 down 20",            [("/eos/cmd", ["Chan 9 At -20#"])]),
    ("address 513 at 100",           [("/eos/addr/513", [100.0])]),
    ("channels 1 and 3 and 5 at full", [("/eos/cmd", ["Chan 1 + 3 + 5 At Full#"])]),
    # spoken number words
    ("channel five at full",         [("/eos/chan/5/full", [])]),
    ("channel twenty three at seventy five", [("/eos/chan/23", [75.0])]),
    ("group one hundred at full",    [("/eos/group/100/full", [])]),
    # moving-light parameters
    ("channel 5 pan 50",             [("/eos/chan/5/param/pan", [50.0])]),
    ("group 2 tilt -20",             [("/eos/group/2/param/tilt", [-20.0])]),
    ("channel 5 zoom 75",            [("/eos/chan/5/param/zoom", [75.0])]),
    ("channel 5 amber 80",           [("/eos/chan/5/param/amber", [80.0])]),
    # key presses
    ("press live",                   [("/eos/key/live", [1.0]), ("/eos/key/live", [0.0])]),
    ("press highlight",              [("/eos/key/highlight", [1.0]), ("/eos/key/highlight", [0.0])]),
    # raw command-line passthrough
    ("command channel 5 thru 10 at full", [("/eos/cmd", ["Chan 5 Thru 10 At Full#"])]),
    ("console go to cue 3",          [("/eos/cmd", ["Go_To_Cue 3#"])]),
    ("command record cue 5",         [("/eos/cmd", ["Record Cue 5#"])]),
    # bare action verbs on the current selection (no "command" prefix needed)
    ("sneak",                        [("/eos/cmd", ["Sneak#"])]),
    ("highlight",                    [("/eos/cmd", ["Highlight#"])]),
    ("mark",                         [("/eos/cmd", ["Mark#"])]),
    ("rem dim",                      [("/eos/cmd", ["Rem_Dim#"])]),
    ("make manual",                  [("/eos/cmd", ["Make_Manual#"])]),
    # bare parameters on the current selection
    ("gobo 3",                       [("/eos/cmd", ["Gobo 3#"])]),
    ("pan 50",                       [("/eos/cmd", ["Pan 50#"])]),
    ("iris 20",                      [("/eos/cmd", ["Iris 20#"])]),
    # bare levels on the current selection
    ("full",                         [("/eos/at/full", [])]),
    ("out",                          [("/eos/at/out", [])]),
    ("at 50 percent",                [("/eos/at", [50.0])]),
    ("75 percent",                   [("/eos/at", [75.0])]),
    # action verbs attached to a target (natural target-first order)
    ("channel 5 sneak",              [("/eos/cmd", ["Chan 5 Sneak#"])]),
    ("group 2 mark",                 [("/eos/cmd", ["Group 2 Mark#"])]),
    ("groups 1 thru 4 rem dim",      [("/eos/cmd", ["Group 1 Thru 4 Rem_Dim#"])]),
    ("channel 5 home",               [("/eos/chan/5/home", [])]),
    # verb spoken BEFORE the target ("sneak channel 5" == "channel 5 sneak")
    ("sneak channel 5",              [("/eos/cmd", ["Chan 5 Sneak#"])]),
    ("park channel 5",               [("/eos/cmd", ["Chan 5 Park#"])]),
    ("home channel 5",               [("/eos/chan/5/home", [])]),
    ("blue channel 7",               [("/eos/chan/7/color/rgb", [0.0, 0.0, 1.0])]),
    # general fallback: any phrase with an Eos keyword reaches the command line
    ("effect 3",                     [("/eos/cmd", ["Effect 3#"])]),
    ("snapshot 2",                   [("/eos/cmd", ["Snapshot 2#"])]),
]

# phrases that must NOT produce OSC (graceful failure with a spoken hint)
FAIL_CASES = [
    "channel at full",
    "channel 5",
    "do a barrel roll",
    "",
]


def _nums_close(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-4
    except (TypeError, ValueError):
        return a == b


def _msgs_equal(got, exp):
    if len(got) != len(exp):
        return False
    for (ga, gargs), (ea, eargs) in zip(got, exp):
        if ga != ea or len(gargs) != len(eargs):
            return False
        for gv, ev in zip(gargs, eargs):
            if isinstance(ev, str):
                if gv != ev:
                    return False
            elif not _nums_close(gv, ev):
                return False
    return True


def main():
    passed = failed = 0

    for phrase, expected in OK_CASES:
        res = parser.parse(phrase, CONFIG)
        if res.ok and _msgs_equal(res.messages, expected):
            passed += 1
        else:
            failed += 1
            print(f"FAIL  {phrase!r}")
            print(f"      expected ok=True {expected}")
            print(f"      got      ok={res.ok} {res.messages}  ({res.confirmation})")

    for phrase in FAIL_CASES:
        res = parser.parse(phrase, CONFIG)
        if not res.ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL  {phrase!r} should not have produced OSC, got {res.messages}")

    # destructive-policy filter (relay-side safety)
    for messages, policy, expected_safe in POLICY_CASES:
        safe, _ = relay.filter_messages(messages, policy)
        if len(safe) == expected_safe:
            passed += 1
        else:
            failed += 1
            print(f"FAIL  policy={policy} {messages} -> {len(safe)} safe, "
                  f"expected {expected_safe}")

    # user-scoping rewrite (keeps voice off the shared OSC command line)
    for messages, osc_user, expected in SCOPE_CASES:
        got = relay.scope_messages(messages, osc_user)
        if _msgs_equal(got, expected):
            passed += 1
        else:
            failed += 1
            print(f"FAIL  scope user={osc_user!r} {messages} -> {got}, "
                  f"expected {expected}")

    # OSC encoder round-trips
    enc_cases = [
        ("/eos/chan/5", [50.0]),
        ("/eos/cmd", ["Chan 1 Thru 8 At 75#"]),
        ("/eos/chan/5/full", []),
        ("/eos/chan/7/color/rgb", [1.0, 0.0, 0.0]),
    ]
    for addr, args in enc_cases:
        raw = osclib.encode(addr, args)
        if len(raw) % 4 != 0:
            failed += 1
            print(f"FAIL  encode({addr}) not 4-byte aligned ({len(raw)} bytes)")
            continue
        d_addr, d_args = osclib.decode(raw)
        if d_addr == addr and _msgs_equal([(d_addr, d_args)], [(addr, args)]):
            passed += 1
        else:
            failed += 1
            print(f"FAIL  round-trip {addr} {args} -> {d_addr} {d_args}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
