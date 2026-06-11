#!/usr/bin/env python3
"""
ETC Nomad voice-control relay.

Runs on the theatre's dual-homed Mac. Receives an HTTP POST from the iPhone
(Siri Shortcut, over Tailscale), translates the spoken phrase into ETC Eos OSC,
and sends the OSC over UDP to the Nomad on the isolated lighting network.

  iPhone --HTTP--> [ this relay ] --OSC/UDP--> Nomad (Eos)

Pure standard library. No pip installs. No API calls. Configure via the control
panel ("opie-panel") or by editing the JSON config (default:
~/Library/Application Support/Opie/config.json).

Run:
    opie                         # console entry point
    python3 -m opie              # same thing
    python3 -m opie --config /path/to/config.json

Endpoints:
    POST /command   body = the spoken phrase (text/plain) or JSON {"text": "..."}
                    auth  = header  X-Token: <token>   (or ?token= / JSON "token")
                    -> 200 text confirmation (spoken back by the Shortcut)
                       401 if the token is wrong
    GET  /health    -> 200 "ok"
    GET  /          -> short help text
"""

import argparse
import errno
import hmac
import json
import logging
import os
import socket
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import __version__
from . import config as opie_config
from . import osclib
from . import parser as nlparser
from . import service as opie_service
from . import update as opie_update

DEFAULT_CONFIG = {
    "NOMAD_IP": "127.0.0.1",      # Eos/Nomad lighting-network IP (use 127.0.0.1 for loopback test)
    "EOS_RX_PORT": 8000,          # Eos "OSC UDP RX Port"
    "HTTP_PORT": 8765,            # port this relay listens on for the phone
    "BIND_ADDR": "0.0.0.0",       # set to the Mac's Tailscale 100.x IP to bind tighter
    "TOKEN": "CHANGE_ME",         # shared secret; the Shortcut must send the same value
    "LOG_FILE": "",               # optional path; empty = stdout only
    "macro_map": {                # named safety/scene verbs -> Eos macro numbers you create
        "blackout": 901,
        "restore": 902
    },
    "key_map": {},                # override console key names if needed
    # How much destructive power voice has:
    #   "block_all"     - output/playback only; no Record/Update/Delete/...
    #   "record_update" - allow Record/Update/Store; block Delete/Wipe/Patch (default)
    #   "allow_all"     - true full control, including Delete/Wipe/Patch
    "destructive_policy": "record_update",
    # Which Eos user voice commands execute as. Un-scoped OSC runs on the
    # console's ONE shared OSC command line, where it interleaves with (and can
    # corrupt) cues sent by other software (QLab network cues, sound desks, ...).
    #   0  - Eos's invisible "background" user (recommended, default)
    #   N  - run on user N's own command line (visible if a display follows it)
    #   -1 - legacy: share the console's default OSC user
    "OSC_USER": 0,
    # Keep Opie current automatically by fast-forwarding the Git clone it runs
    # from (no effect on pip installs or downloaded ZIPs). See opie/update.py.
    "auto_update": True,
}

# Always blocked unless policy == "allow_all".
HARD_DESTRUCTIVE = ("delete", "del ", "wipe", "patch", "copy to", "move to", "explode")
# Blocked only when policy == "block_all" (allowed for record_update / allow_all).
RECORD_VERBS = ("record", "update", "store", "merge")

log = logging.getLogger("etc-relay")


def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        log.warning("config file not found (%s) — using defaults", path)
    return cfg


def _blocked_word(text, policy):
    """Return the offending verb if `text` is disallowed under `policy`, else None."""
    if policy == "allow_all":
        return None
    low = text.lower()
    for w in HARD_DESTRUCTIVE:
        if w in low:
            return w.strip()
    if policy == "block_all":
        for w in RECORD_VERBS:
            if w in low:
                return w.strip()
    return None


def filter_messages(messages, policy):
    """
    Full OSC is allowed (any /eos/* address). The destructive policy is enforced
    on the two paths that can do real damage: command-line strings (/eos/cmd) and
    console key presses (/eos/key/<name>).
    Returns (safe_messages, [rejection_reasons]).
    """
    safe = []
    rejected = []
    for address, args in messages:
        if not address.startswith("/eos/"):
            rejected.append(f"non-eos address: {address}")
            continue
        if address == "/eos/cmd":
            bad = next((_blocked_word(a, policy) for a in args
                        if isinstance(a, str) and _blocked_word(a, policy)), None)
            if bad:
                rejected.append(f"blocked verb: {bad}")
            else:
                safe.append((address, args))
            continue
        if address.startswith("/eos/key/"):
            keyname = address[len("/eos/key/"):].replace("_", " ")
            bad = _blocked_word(keyname, policy)
            if bad:
                rejected.append(f"blocked key: {bad}")
            else:
                safe.append((address, args))
            continue
        safe.append((address, args))
    return safe, rejected


def scope_messages(messages, osc_user):
    """
    Rewrite outgoing addresses to execute as a dedicated Eos user
    (/eos/... -> /eos/user/<n>/...) instead of on the console's shared OSC
    command line, and upgrade /eos/cmd to /eos/newcmd (clears the line before
    typing) so a leftover half-typed command can never merge with the next one.

    Eos runs un-scoped OSC from every UDP sender on the same command line and
    selection, so voice traffic would interleave with — and corrupt — cues sent
    by other software. User 0 is Eos's background user (the context background
    macros run in). osc_user < 0 keeps the legacy shared behaviour. /eos/ping
    is left untouched: it's one of the few inputs without a /user form.
    """
    try:
        user = int(osc_user)
    except (TypeError, ValueError):
        user = 0
    if user < 0:
        return list(messages)
    scoped = []
    for address, args in messages:
        if address == "/eos/cmd":
            address = "/eos/newcmd"
        if (address.startswith("/eos/")
                and not address.startswith("/eos/ping")
                and not address.startswith("/eos/user/")):
            address = f"/eos/user/{user}/" + address[len("/eos/"):]
        scoped.append((address, args))
    return scoped


class Relay:
    def __init__(self, config):
        self.config = config
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dest = (config["NOMAD_IP"], int(config["EOS_RX_PORT"]))
        self.osc_user = config.get("OSC_USER", DEFAULT_CONFIG["OSC_USER"])

    def send(self, messages):
        for address, args in scope_messages(messages, self.osc_user):
            raw = osclib.encode(address, args)
            self.sock.sendto(raw, self.dest)
            log.info("OSC -> %s:%d  %s", self.dest[0], self.dest[1],
                     osclib.format_message(address, args))


def make_handler(relay, run_info=None):
    cfg = relay.config
    token = str(cfg.get("TOKEN", ""))
    run_info = run_info or {}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):
            log.info("%s - %s", self.client_address[0], fmt % a)

        def _reply(self, code, text):
            body = (text or "").encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_token(self, qs, body_token):
            supplied = (self.headers.get("X-Token")
                        or (qs.get("token", [None])[0])
                        or body_token
                        or "")
            return hmac.compare_digest(str(supplied), token)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                self._reply(200, "ok")
            elif path == "/version":
                # What THIS process is running (captured at startup) — the code
                # on disk may already be newer; the panel compares the two.
                self._reply(200, json.dumps(run_info))
            elif path == "/":
                self._reply(200, "ETC Nomad voice relay is running. POST a phrase "
                                 "to /command with header X-Token.")
            else:
                self._reply(404, "not found")

        def do_POST(self):
            parsed = urlparse(self.path)
            # Always read the body first, even for a wrong path: otherwise the
            # leftover bytes on a keep-alive connection get parsed as the next
            # request line (the confusing "Bad request version" error).
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b""
            # Be lenient: accept commands on "/command" or "/".
            if parsed.path not in ("/command", "/"):
                self._reply(404, "not found")
                return
            ctype = (self.headers.get("Content-Type") or "").lower()

            phrase = ""
            body_token = None
            if "application/json" in ctype:
                try:
                    data = json.loads(raw.decode("utf-8") or "{}")
                    phrase = data.get("text", "") or data.get("command", "")
                    body_token = data.get("token")
                except (ValueError, AttributeError):
                    self._reply(400, "bad JSON")
                    return
            else:
                phrase = raw.decode("utf-8", errors="replace")

            qs = parse_qs(parsed.query)
            if not self._check_token(qs, body_token):
                log.warning("rejected request from %s (bad token)", self.client_address[0])
                self._reply(401, "Unauthorized.")
                return

            result = nlparser.parse(phrase, cfg)
            if not result.ok:
                log.info("unparsed phrase %r -> %s", phrase, result.confirmation)
                self._reply(200, result.confirmation)  # 200 so Siri speaks the hint
                return

            safe, rejected = filter_messages(result.messages,
                                             cfg.get("destructive_policy", "record_update"))
            if rejected:
                log.warning("blocked OSC for %r: %s", phrase, rejected)
            if not safe:
                self._reply(200, "That command was blocked for safety.")
                return

            try:
                relay.send(safe)
            except OSError as e:
                log.error("UDP send failed: %s", e)
                self._reply(502, "Could not reach the console.")
                return

            self._reply(200, result.confirmation)

    return Handler


def main():
    ap = argparse.ArgumentParser(description="ETC Nomad voice-control relay")
    ap.add_argument("--config", default=opie_config.default_config_path())
    args = ap.parse_args()

    # First run: scaffold a config (with a freshly generated token) so there is
    # always something to load.
    opie_config.ensure_exists(args.config)
    cfg = load_config(args.config)

    # Always log to a file (default: ~/Library/Logs/Opie/relay.log) so the GUI's
    # live-log pane has one source of truth, plus stdout for terminal/launchd capture.
    log_file = cfg.get("LOG_FILE") or opie_config.default_log_path()
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    except OSError as e:
        print(f"warning: could not open log file {log_file}: {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers)

    if cfg.get("TOKEN") in ("", "CHANGE_ME"):
        log.warning("TOKEN is still the default — set a real secret in config.json")

    relay = Relay(cfg)
    port = int(cfg["HTTP_PORT"])
    bind = cfg["BIND_ADDR"]
    run_info = {"version": __version__,
                "revision": opie_update.current_revision() or ""}
    handler = make_handler(relay, run_info)

    def _other_relay_serving(host):
        """True if a relay already answers /health on host:port."""
        host = host if host and host not in ("0.0.0.0", "::") else "127.0.0.1"
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/health",
                                        timeout=1.5) as r:
                return (r.status == 200
                        and r.read().decode("utf-8", "replace").strip() == "ok")
        except Exception:  # noqa: BLE001
            return False

    try:
        server = ThreadingHTTPServer((bind, port), handler)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            # The port is taken. If the holder is a relay, do NOT shadow-bind
            # 0.0.0.0 next to it (SO_REUSEADDR allows it on macOS, and then the
            # phone and the panel each talk to a DIFFERENT relay) — there must
            # be exactly one instance, so leave the running one alone.
            if _other_relay_serving(bind):
                log.warning("another relay already serves port %d — exiting so "
                            "only one instance runs", port)
                return
            raise
        # e.g. the BIND_ADDR hostname can't be resolved, or its IP isn't
        # assigned yet (Tailscale not up at boot) -> listen on all interfaces.
        log.warning("could not bind to %r (%s) — falling back to 0.0.0.0", bind, e)
        bind = "0.0.0.0"
        try:
            server = ThreadingHTTPServer((bind, port), handler)
        except OSError as e2:
            if e2.errno == errno.EADDRINUSE and _other_relay_serving(bind):
                log.warning("another relay already serves port %d — exiting so "
                            "only one instance runs", port)
                return
            raise
    log.info("relay listening on http://%s:%d  ->  OSC %s:%d  (Eos user %s, %s)",
             bind, port, cfg["NOMAD_IP"], int(cfg["EOS_RX_PORT"]), relay.osc_user,
             run_info["revision"] or "unknown rev")

    # Auto-update runs in the BACKGROUND so a slow `git fetch` never delays (or
    # blocks) the relay from coming up. If a newer commit is found it fast-forwards
    # and re-execs into it (a brief blip), otherwise it's a no-op. Best-effort.
    def _bg_update():
        # Keep the clickable Opie.app current FIRST (before a possible execv):
        # an outdated launcher otherwise survives code updates and breaks the
        # control panel when the entry point changes.
        try:
            opie_service.ensure_app_launcher()
        except Exception as e:  # noqa: BLE001
            log.warning("could not refresh Opie.app launcher: %s", e)
        try:
            opie_update.self_update_and_reexec(cfg)  # may execv (replaces process)
        except Exception as e:  # noqa: BLE001
            log.warning("auto-update check failed: %s", e)
    threading.Thread(target=_bg_update, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
