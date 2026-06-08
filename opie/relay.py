#!/usr/bin/env python3
"""
ETC Nomad voice-control relay.

Runs on the theatre's dual-homed Mac. Receives an HTTP POST from the iPhone
(Siri Shortcut, over Tailscale), translates the spoken phrase into ETC Eos OSC,
and sends the OSC over UDP to the Nomad on the isolated lighting network.

  iPhone --HTTP--> [ this relay ] --OSC/UDP--> Nomad (Eos)

Pure standard library. No pip installs. No API calls. Configure via the GUI
("opie-gui") or by editing the JSON config (default:
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
import hmac
import json
import logging
import os
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import config as opie_config
from . import osclib
from . import parser as nlparser
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


class Relay:
    def __init__(self, config):
        self.config = config
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dest = (config["NOMAD_IP"], int(config["EOS_RX_PORT"]))

    def send(self, messages):
        for address, args in messages:
            raw = osclib.encode(address, args)
            self.sock.sendto(raw, self.dest)
            log.info("OSC -> %s:%d  %s", self.dest[0], self.dest[1],
                     osclib.format_message(address, args))


def make_handler(relay):
    cfg = relay.config
    token = str(cfg.get("TOKEN", ""))

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

    # Self-update: if running from a Git clone and a newer commit is available,
    # fast-forward and re-exec into it before we start serving. Best-effort and
    # bounded; offline/no-git/not-a-clone just continues on the current code.
    status = opie_update.self_update_and_reexec(cfg)  # may not return (re-execs)
    if status == opie_update.ERROR:
        log.warning("auto-update check could not complete; running current version")
    elif status == opie_update.CURRENT and opie_update.is_git_clone():
        log.info("auto-update: already on the latest version (%s)",
                 opie_update.current_revision() or "unknown")

    relay = Relay(cfg)
    port = int(cfg["HTTP_PORT"])
    bind = cfg["BIND_ADDR"]
    try:
        server = ThreadingHTTPServer((bind, port), make_handler(relay))
    except OSError as e:
        # e.g. the BIND_ADDR hostname can't be resolved yet (Tailscale/MagicDNS
        # not up at boot) -> don't die, listen on all interfaces instead.
        log.warning("could not bind to %r (%s) — falling back to 0.0.0.0", bind, e)
        bind = "0.0.0.0"
        server = ThreadingHTTPServer((bind, port), make_handler(relay))
    log.info("relay listening on http://%s:%d  ->  OSC %s:%d",
             bind, port, cfg["NOMAD_IP"], int(cfg["EOS_RX_PORT"]))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
