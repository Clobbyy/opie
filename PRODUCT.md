# PRODUCT.md — Opie

register: product

## What it is

Opie is a small macOS relay that turns spoken iPhone phrases into ETC Eos/Nomad
lighting-console commands. Siri Shortcut → HTTP (over Tailscale or LAN) → the Opie
relay on the theatre Mac → OSC/UDP → the console. No cloud, no subscriptions, runs
on the Mac's built-in Python. This document covers the **control panel**: a
localhost web UI (`opie/panel.py`, served at `http://127.0.0.1:8766`) hosted inside
a native Swift WKWebView window (`opie/resources/OpieApp.swift`).

The panel is where an operator sets up and babysits the relay: start/stop it, point
it at the console, set the security token, test a phrase, and watch the live log.

## Users

A lighting programmer / production electrician / board op. Technically fluent with
ETC Eos (channels, groups, submasters, cues, macros, OSC) and comfortable with IPs
and ports, but not necessarily a software developer. They install once, then return
to the panel only when something needs checking: confirming the relay is up before a
show, re-pointing it at a new console IP, rotating the token, or diagnosing why a
phrase didn't land.

## Where and when it's used

In a theatre, often from a dim tech booth or backstage during focus/tech, on a
MacBook sitting next to the lighting console. Sometimes at a normal desk during
setup. Glanceable status matters more than dwell time: the single most important
question the panel answers is "is the relay running and reachable right now?"
Dark-first, because the booth is dark and so is the work.

## Core jobs (in priority order)

1. **Confirm state at a glance** — is the relay running? Is the console reachable?
   Is the phone-facing URL live? Is the running relay on the same code revision as
   what's installed (drift after an update)?
2. **Control the relay** — Start / Stop / Restart, and Autostart at login. Start is
   the primary action; failures must surface the real reason (log tail), not a
   generic message.
3. **Set up the bridge** — console IP + OSC RX port, relay HTTP port, bind address,
   the shared token (generate/copy/rotate), the destructive-command safety policy,
   the Eos OSC user, and spoken-word → macro / key maps.
4. **Test & wire the phone** — send a phrase and see the console's reply; check the
   console pings; copy the exact iPhone Shortcut URL + token.
5. **Diagnose** — a live tail of the relay log, scoped to the current run.

## Tone

Operator-grade and exact. This is show infrastructure: it should feel like dependable
backstage gear, not a consumer app. Precise nouns (relay, console, OSC, token,
revision), real numbers (ports, IPs, the literal OSC string a phrase produces), no
marketing voice, no cute empty states. Calm under failure: when the relay won't
start, the panel states what happened and what to do.

## Anti-references

- Generic macOS System-Settings clone (what it looks like today): four identical
  grey cards, tiny status dot, no point of view.
- Rave / DJ-lighting neon-on-black cliché (cyan + magenta glow). Opie is theatre
  infrastructure, not a party visualizer.
- Dashboard-template SaaS: big vanity hero metrics, gradient text, decorative motion.

## Strategic principles

- **Status is the hero.** The running/reachable truth is the most valuable pixel.
- **Operational values are first-class.** IPs, ports, tokens, OSC strings, revisions
  are the content; render them precisely (monospace), make them copyable.
- **Failure is a designed state**, not an afterthought. Every action has an error path.
- **Trustworthy affordances.** Bold identity, standard controls. Nothing a board op
  has to relearn.
