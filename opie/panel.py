"""
Opie Control — a browser-based control panel. **No Tkinter, no Tk required.**

Earlier versions used a Tkinter window, which needed Tk 8.6+ that the Mac's
built-in python3 lacks (Apple ships the deprecated Tk 8.5). This panel does the
same job with a tiny localhost-only web server built entirely from the standard
library, so it runs on *any* python3 — nothing to install.

  python3 -m opie.panel      # start the panel and open your browser
  opie-panel                 # same, after a pip install

Security: it binds to 127.0.0.1 only, so just the local user (you) can reach it;
the panel is unauthenticated by design (it's your own machine), while the relay's
phone-facing endpoint still requires the token.
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import __version__
from . import config as opie_config
from . import service
from . import update as opie_update

PANEL_HOST = "127.0.0.1"
DEFAULT_PANEL_PORT = 8766
POLICIES = ["block_all", "record_update", "allow_all"]

# Config keys the panel lets you edit (everything else is preserved untouched).
_TEXT_KEYS = ("NOMAD_IP", "EOS_RX_PORT", "HTTP_PORT", "BIND_ADDR", "LOG_FILE", "TOKEN",
              "OSC_USER")
_INT_KEYS = ("EOS_RX_PORT", "HTTP_PORT", "OSC_USER")


class Controller:
    """All the side-effecting actions, mirroring what the Tk GUI did."""

    def __init__(self, config_path):
        self.config_path = config_path
        opie_config.ensure_exists(config_path)

    def _pidfile(self):
        return os.path.join(opie_config.app_support_dir(), "relay.pid")

    def _outlog(self):
        return os.path.join(opie_config.logs_dir(), "relay.out.log")

    # ---- config ----
    def load(self):
        return opie_config.load(self.config_path)

    def save(self, incoming):
        cfg = self.load()  # preserve unknown keys
        for k in _TEXT_KEYS:
            if k in incoming:
                cfg[k] = str(incoming[k]).strip()
        for k in _INT_KEYS:
            if k in incoming and str(incoming[k]).strip() != "":
                cfg[k] = int(incoming[k])
        if "destructive_policy" in incoming and incoming["destructive_policy"] in POLICIES:
            cfg["destructive_policy"] = incoming["destructive_policy"]
        if "auto_update" in incoming:
            cfg["auto_update"] = bool(incoming["auto_update"])
        for k in ("macro_map", "key_map"):
            if k in incoming:
                val = incoming[k]
                if isinstance(val, str):
                    val = json.loads(val or "{}")
                cfg[k] = val or {}
        opie_config.save(cfg, self.config_path)
        return cfg

    # ---- relay process ----
    # The relay runs as a DETACHED subprocess (its own session, so it survives the
    # panel closing) with stdout+stderr captured to relay.out.log, and its PID
    # recorded so we can stop it later. This doesn't depend on launchd, so a broken
    # launchd job can't block Start, and crashes are visible (relay.out.log).
    def _port(self):
        return int(self.load().get("HTTP_PORT", 8765))

    def _spawn(self):
        if self._health(self._port()):
            return  # already up — don't double-start
        try:
            os.makedirs(opie_config.logs_dir(), exist_ok=True)
        except OSError:
            pass
        env = dict(os.environ)
        root = opie_config.get_install_root()
        if root:
            env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        out = open(self._outlog(), "a")
        out.write(f"\n--- starting relay {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        out.flush()
        proc = subprocess.Popen(
            [sys.executable, "-m", "opie", "--config", self.config_path],
            stdout=out, stderr=subprocess.STDOUT,
            cwd=root or opie_config.app_support_dir(), env=env,
            start_new_session=True)  # detach so it outlives the panel
        try:
            with open(self._pidfile(), "w") as f:
                f.write(str(proc.pid))
        except OSError:
            pass

    @staticmethod
    def _relay_pids():
        """PIDs of EVERY running relay (`python -m opie`, not the panel),
        however it was started — pidfile, launchd, or an orphan left behind by
        an old install. A stale second relay shadow-binding the HTTP port is
        exactly the 'old relay still running in the background' bug."""
        try:
            r = subprocess.run(["pgrep", "-f", r"[Pp]ython[^ ]* -m opie($| )"],
                               capture_output=True, text=True)
            return [int(p) for p in r.stdout.split() if p.strip().isdigit()]
        except (OSError, subprocess.SubprocessError, ValueError):
            return []

    def _port_listeners(self, port=None):
        """PIDs of every process LISTENING on the relay port, on ANY interface.
        This is the ground truth the phone experiences — immune to the blind
        spots of HTTP probes (relay bound only to the Tailscale IP) and of
        process-name matching (a relay started by an old install)."""
        port = port or self._port()
        try:
            r = subprocess.run(
                ["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=5)
            return sorted({int(p) for p in r.stdout.split() if p.strip().isdigit()})
        except (OSError, subprocess.SubprocessError, ValueError):
            return []

    def _kill(self):
        # Union of every way we can find a relay: name pattern, pidfile, and —
        # decisively — whatever is actually holding the relay port.
        pids = set(self._relay_pids()) | set(self._port_listeners())
        try:
            with open(self._pidfile()) as f:
                pids.add(int(f.read().strip()))
        except (OSError, ValueError):
            pass
        pids.discard(os.getpid())
        for pid in pids:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.kill(pid, sig)
                except OSError:  # already gone (or not ours)
                    break
                time.sleep(0.4)
                if not self._pid_alive(pid):
                    break
        try:
            os.remove(self._pidfile())
        except OSError:
            pass

    @staticmethod
    def _pid_alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def wait_healthy(self, seconds=6.0):
        end = time.time() + seconds
        port = self._port()
        while time.time() < end:
            if self._health(port):
                return True
            time.sleep(0.4)
        return False

    def relay_log_tail(self, lines=40):
        try:
            with open(self._outlog(), "r", errors="replace") as f:
                rows = f.readlines()
        except OSError:
            return ""
        # Only report the current run: cut at the last "--- starting relay"
        # marker so a days-old startup line can't be shown as today's error.
        for i in range(len(rows) - 1, -1, -1):
            if rows[i].startswith("--- starting relay"):
                rows = rows[i:]
                break
        return "".join(rows[-lines:]).strip()

    def ensure_running(self):
        if not self._health(self._port()):
            self.control("start")

    def control(self, action):
        if action == "start":
            if service.is_loaded():
                service.restart()
                if not self.wait_healthy(5):
                    # launchd job is loaded but not coming up — drop it and run
                    # the relay directly so Start always works.
                    service.disable()
                    self._spawn()
            else:
                self._spawn()
        elif action == "stop":
            if service.is_loaded():
                service.disable()
            self._kill()
        elif action == "restart":
            if service.is_loaded():
                service.restart()
            else:
                self._kill(); time.sleep(0.3); self._spawn()
        elif action == "autostart_on":
            self._kill()
            service.enable(python_exe=sys.executable, config_path=self.config_path)
        elif action == "autostart_off":
            service.disable()
        else:
            raise ValueError(f"unknown action: {action}")

    # ---- status / info ----
    def _hosts(self, cfg=None):
        """Where the relay might be listening: loopback first (covers the
        0.0.0.0 and fallback cases), then the configured bind address (covers a
        relay bound ONLY to e.g. the Tailscale IP, which loopback can't see)."""
        hosts = ["127.0.0.1"]
        cfg = cfg or self.load()
        bind = str(cfg.get("BIND_ADDR", "")).strip()
        if bind and bind not in ("0.0.0.0", "::", "127.0.0.1", "localhost"):
            hosts.append(bind)
        return hosts

    def _health(self, port, timeout=0.6):
        for host in self._hosts():
            try:
                with urllib.request.urlopen(f"http://{host}:{port}/health",
                                            timeout=timeout) as r:
                    if (r.status == 200
                            and r.read().decode("utf-8", "replace").strip() == "ok"):
                        return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def relay_info(self, port=None):
        """What the RUNNING relay reports about itself via /version — {} if it's
        unreachable or predates the endpoint. The code on disk may be newer than
        what the relay loaded at startup; callers compare the two."""
        port = port or self._port()
        for host in self._hosts():
            try:
                with urllib.request.urlopen(f"http://{host}:{port}/version",
                                            timeout=0.6) as r:
                    if r.status == 200:
                        return json.loads(r.read().decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                continue
        return {}

    def status(self):
        cfg = self.load()
        port = int(cfg.get("HTTP_PORT", 8765))
        bind = str(cfg.get("BIND_ADDR", "")).strip()
        host = bind if bind and bind != "0.0.0.0" else socket.gethostname()
        return {
            # Running = someone holds the relay port (what the phone sees),
            # not merely "an HTTP probe got through" — a relay bound only to
            # the Tailscale IP must never be reported as stopped.
            "running": bool(self._port_listeners(port)) or self._health(port),
            "autostart": service.is_loaded(),
            "version": __version__,
            "revision": opie_update.current_revision() or "",
            "relay_revision": self.relay_info(port).get("revision", ""),
            "port": port,
            "nomad_ip": cfg.get("NOMAD_IP", ""),
            "eos_port": cfg.get("EOS_RX_PORT", 8000),
            "phone_url": f"http://{host}:{port}/command",
            "token": cfg.get("TOKEN", ""),
        }

    def test(self, phrase):
        cfg = self.load()
        port = int(cfg.get("HTTP_PORT", 8765))
        token = str(cfg.get("TOKEN", ""))
        last = ""
        for host in self._hosts(cfg):
            try:
                req = urllib.request.Request(
                    f"http://{host}:{port}/command", data=phrase.encode("utf-8"),
                    headers={"X-Token": token, "Content-Type": "text/plain"})
                with urllib.request.urlopen(req, timeout=3) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                last = str(e)
        return 0, f"{last}  (is the relay running?)"

    def ping(self, ip):
        try:
            r = subprocess.run(["ping", "-c", "1", "-t", "1", ip],
                               capture_output=True, timeout=4)
            return r.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def logs(self, pos):
        # The captured console log (relay.out.log) holds both normal logging and
        # any startup crash, so it's the most useful thing to show.
        path = self._outlog()
        try:
            size = os.path.getsize(path)
            if size < pos:
                pos = 0
            with open(path, "r", errors="replace") as f:
                f.seek(pos)
                data = f.read()
                return data, f.tell()
        except OSError:
            return "", pos


def make_handler(ctrl):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass  # quiet

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            if not isinstance(body, (bytes, bytearray)):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj))

        def _body(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                return {}

        def do_GET(self):
            p = urlparse(self.path)
            if p.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif p.path == "/api/state":
                cfg = ctrl.load()
                editable = {k: cfg.get(k, "") for k in _TEXT_KEYS}
                editable["OSC_USER"] = cfg.get("OSC_USER", 0)
                editable["destructive_policy"] = cfg.get("destructive_policy", "record_update")
                editable["auto_update"] = bool(cfg.get("auto_update", True))
                editable["macro_map"] = cfg.get("macro_map", {})
                editable["key_map"] = cfg.get("key_map", {})
                self._json({"config": editable, "status": ctrl.status(),
                            "policies": POLICIES})
            elif p.path == "/api/logs":
                pos = int((parse_qs(p.query).get("pos", ["0"])[0]) or 0)
                text, newpos = ctrl.logs(pos)
                self._json({"text": text, "pos": newpos})
            elif p.path == "/api/ping":
                ip = parse_qs(p.query).get("ip", [""])[0]
                self._json({"ok": ctrl.ping(ip), "ip": ip})
            elif p.path == "/api/token":
                self._json({"token": opie_config.generate_token()})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            p = urlparse(self.path)
            data = self._body()
            try:
                if p.path == "/api/config":
                    ctrl.save(data)
                    if data.get("restart"):
                        ctrl.control("restart")
                    self._json({"ok": True})
                elif p.path == "/api/control":
                    action = data.get("action", "")
                    ctrl.control(action)
                    resp = {"ok": True}
                    if action in ("start", "restart"):
                        resp["running"] = ctrl.wait_healthy(6)
                        if not resp["running"]:
                            resp["error"] = (ctrl.relay_log_tail()
                                             or "The relay did not start. Check that "
                                                "python3 works and the port is free.")
                    elif action == "stop":
                        # Verify by ground truth: NOTHING may still be listening
                        # on the relay port, on any interface. A survivor here is
                        # exactly "GUI says stopped but the phone still works".
                        time.sleep(0.6)
                        leftover = ctrl._port_listeners()
                        resp["running"] = bool(leftover) or ctrl._health(ctrl._port())
                        if resp["running"]:
                            resp["error"] = ("Stop failed: process "
                                             f"{leftover or '(unknown)'} still holds "
                                             "the relay port. Stop it manually or "
                                             "reboot, then tell us how this happened.")
                        elif service.is_loaded():
                            # The agent survived disable(): launchd's KeepAlive
                            # WILL resurrect the relay in a few seconds even
                            # though the port is quiet right now.
                            resp["running"] = True
                            resp["error"] = ("Stop failed: the autostart agent "
                                             "could not be unloaded, so the relay "
                                             "will restart itself. Run "
                                             "'launchctl bootout gui/$UID/com.opie.relay' "
                                             "in Terminal and report this.")
                    self._json(resp)
                elif p.path == "/api/test":
                    code, body = ctrl.test(str(data.get("phrase", "")))
                    self._json({"code": code, "body": body})
                elif p.path == "/api/update":
                    status, msg = opie_update.check_and_update()
                    if status == opie_update.UPDATED:
                        ctrl.control("restart")
                    elif status == opie_update.CURRENT:
                        # The code on disk can already be newer than what the
                        # running relay loaded at startup ("updating from the
                        # GUI didn't work" = this case) — restart to apply it.
                        src = opie_update.current_revision() or ""
                        run = ctrl.relay_info().get("revision", "")
                        if src and run and src != run:
                            ctrl.control("restart")
                            status = opie_update.UPDATED
                            msg = (f"Restarted the relay onto {src} "
                                   f"(it was still running {run}).")
                    self._json({"status": status, "message": msg})
                else:
                    self._json({"error": "not found"}, 404)
            except (ValueError, json.JSONDecodeError) as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 500)

    return Handler


def _open(url):
    try:
        if not webbrowser.open(url):
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser(description="Opie browser control panel")
    ap.add_argument("--config", default=opie_config.default_config_path())
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("OPIE_PANEL_PORT", DEFAULT_PANEL_PORT)))
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    ctrl = Controller(args.config)
    try:
        service.ensure_app_launcher()  # keep the clickable Opie.app current
    except Exception:  # noqa: BLE001
        pass
    url = f"http://{PANEL_HOST}:{args.port}/"
    try:
        server = ThreadingHTTPServer((PANEL_HOST, args.port), make_handler(ctrl))
    except OSError:
        # Panel already running on this port — just bring its tab up.
        print(f"Opie Control is already running at {url}")
        if not args.no_browser:
            _open(url)
        return 0

    # Opening Opie should make it work: bring the relay up if it isn't already.
    threading.Thread(target=ctrl.ensure_running, daemon=True).start()

    print(f"Opie Control: {url}  (Ctrl-C to quit)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: _open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()
    return 0


# --------------------------------------------------------------------------- #
# The single-page UI (vanilla HTML/CSS/JS, no external assets — works offline). #
# --------------------------------------------------------------------------- #
PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Opie Control</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 0; background: #f5f5f7; color: #1d1d1f; }
  @media (prefers-color-scheme: dark) { body { background:#1c1c1e; color:#f2f2f7; }
    .card{background:#2c2c2e!important;} input,select,textarea{background:#1c1c1e;color:#f2f2f7;border-color:#48484a!important;}
    button{background:#48484a;color:#f2f2f7;border-color:#646469;} button:hover{background:#545458;} }
  header { display:flex; align-items:center; gap:10px; padding:14px 20px;
           background:#fff; border-bottom:1px solid #d2d2d7; position:sticky; top:0; }
  @media (prefers-color-scheme: dark){ header{background:#2c2c2e;border-color:#3a3a3c;} }
  .dot { width:12px;height:12px;border-radius:50%;background:#8e8e93; flex:0 0 auto; }
  .dot.on { background:#34c759; }
  h1 { font-size:16px; margin:0; font-weight:600; }
  .muted { color:#8e8e93; }
  main { max-width:760px; margin:18px auto; padding:0 16px; }
  .card { background:#fff; border:1px solid #d2d2d7; border-radius:12px;
          padding:16px 18px; margin-bottom:16px; }
  .card h2 { font-size:13px; text-transform:uppercase; letter-spacing:.04em;
             color:#8e8e93; margin:0 0 12px; }
  label { display:block; font-weight:500; margin:10px 0 4px; }
  input, select, textarea { width:100%; padding:7px 9px; border:1px solid #c7c7cc;
            border-radius:8px; font:inherit; }
  textarea { font-family: ui-monospace, Menlo, monospace; min-height:84px; }
  .row { display:flex; gap:12px; flex-wrap:wrap; }
  .row > div { flex:1; min-width:140px; }
  button { font:inherit; font-weight:600; padding:8px 16px; border-radius:8px;
           border:1px solid #b0b0b6; background:#e7e7ec; color:#1d1d1f;
           cursor:pointer; -webkit-appearance:none; appearance:none; }
  button:hover { background:#d8d8df; }
  button:active { transform: translateY(1px); }
  button.primary { background:#0071e3; color:#fff; border-color:#0071e3; }
  button.primary:hover { background:#0064c8; }
  button:disabled { opacity:.4; cursor:not-allowed; }
  .bar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .grow { flex:1; }
  pre#log { background:#0b0b0c; color:#e6e6e6; padding:12px; border-radius:8px;
            height:260px; overflow:auto; white-space:pre-wrap; font:12px ui-monospace,Menlo,monospace; }
  .note { font-size:13px; }
  code { background:#0001; padding:1px 5px; border-radius:5px; }
  @media (prefers-color-scheme: dark){ code{background:#fff2;} }
  .ok { color:#34c759; } .err { color:#ff3b30; }
  .pill { font-size:12px; padding:2px 8px; border-radius:999px; background:#0001; }
</style></head>
<body>
<header>
  <span id="dot" class="dot"></span>
  <h1 id="status">Connecting…</h1>
  <span class="grow"></span>
  <span id="ver" class="muted"></span>
</header>
<main>

  <div class="card">
    <h2>Relay</h2>
    <div class="bar">
      <button class="primary" onclick="ctl('start')">Start</button>
      <button onclick="ctl('stop')">Stop</button>
      <button onclick="ctl('restart')">Restart</button>
      <span class="grow"></span>
      <label style="margin:0"><input type="checkbox" id="autostart" style="width:auto"
        onchange="ctl(this.checked?'autostart_on':'autostart_off')"> Autostart at login</label>
    </div>
    <p id="url" class="muted note" style="margin:10px 0 0"></p>
    <pre id="relayerr" class="err" style="display:none; white-space:pre-wrap; margin:10px 0 0; font:12px ui-monospace,Menlo,monospace"></pre>
  </div>

  <div class="card">
    <h2>Setup</h2>
    <div class="row">
      <div><label>Console IP (Nomad/Eos)</label><input id="NOMAD_IP"></div>
      <div><label>Console OSC RX port</label><input id="EOS_RX_PORT"></div>
    </div>
    <div class="row">
      <div><label>Relay HTTP port</label><input id="HTTP_PORT"></div>
      <div><label>Bind address</label><input id="BIND_ADDR"></div>
    </div>
    <label>Log file (blank = default)</label><input id="LOG_FILE">
    <div class="row">
      <div><label>Destructive policy</label><select id="destructive_policy"></select></div>
      <div><label>Eos OSC user <span class="muted">(0 = background)</span></label><input id="OSC_USER"></div>
      <div><label>&nbsp;</label><label style="font-weight:500"><input type="checkbox" id="auto_update" style="width:auto"> Auto-update</label></div>
    </div>
    <p class="note muted" style="margin:4px 0 0">Voice commands run as their own Eos user so they
      never collide with cues other software (QLab, sound desks, …) sends to the console.
      <code>0</code> = the invisible background user · a positive number = that user's command line ·
      <code>-1</code> = share the console's OSC user (old behaviour).</p>
    <label>Shared token <span class="muted">(the iPhone Shortcut sends this)</span></label>
    <div class="bar">
      <input id="TOKEN" class="grow">
      <button onclick="genToken()">Generate</button>
      <button onclick="copy(document.getElementById('TOKEN').value)">Copy</button>
    </div>
    <div class="row" style="margin-top:8px">
      <div><label>Macro map <span class="muted">(word → macro #)</span></label><textarea id="macro_map"></textarea></div>
      <div><label>Key map <span class="muted">(word → key name)</span></label><textarea id="key_map"></textarea></div>
    </div>
    <div class="bar" style="margin-top:12px">
      <button class="primary" onclick="save(false)">Save</button>
      <button onclick="save(true)">Save &amp; Restart</button>
      <span id="saved" class="ok"></span>
    </div>
  </div>

  <div class="card">
    <h2>Test &amp; phone setup</h2>
    <div class="bar">
      <input id="phrase" class="grow" value="channel 5 at full" onkeydown="if(event.key==='Enter')sendTest()">
      <button onclick="sendTest()">Send</button>
    </div>
    <p id="testres" class="note"></p>
    <div class="bar" style="margin-top:6px">
      <button onclick="pingConsole()">Check console reachable</button>
      <button onclick="checkUpdate()">Check for updates</button>
      <span id="misc" class="note muted"></span>
    </div>
    <p class="note" style="margin-top:12px">
      <b>iPhone Shortcut</b> — one “Get Contents of URL” action:<br>
      URL <code id="purl"></code> · Method <code>POST</code> ·
      Header <code>X-Token</code> = <code id="ptok"></code> · Body = the dictated phrase.
      <button style="margin-left:6px" onclick="copy(document.getElementById('ptok').textContent)">Copy token</button>
    </p>
  </div>

  <div class="card">
    <h2>Logs</h2>
    <div class="bar" style="margin-bottom:8px">
      <button onclick="paused=!paused;this.textContent=paused?'Resume':'Pause'">Pause</button>
      <button onclick="document.getElementById('log').textContent=''">Clear</button>
    </div>
    <pre id="log"></pre>
  </div>

</main>
<script>
let logpos=0, paused=false, loaded=false;
const $=id=>document.getElementById(id);
async function api(path,opts){ const r=await fetch(path,opts); return r.json(); }
function copy(t){ navigator.clipboard.writeText(t).catch(()=>{}); }

const PANEL_DOWN='The Opie panel app is not running (the relay may be fine). Open the Opie app, then try again.';
async function refresh(){
  let d;
  try{ d=await api('/api/state'); }
  catch(e){
    $('dot').className='dot';
    $('status').textContent='Panel closed — open the Opie app to reconnect';
    return;
  }
  const s=d.status;
  $('dot').className='dot'+(s.running?' on':'');
  $('status').textContent=(s.running?'Running':'Stopped')+(s.autostart?' · autostart on':'');
  let ver='Opie '+s.version+(s.revision?(' · '+s.revision):'');
  if(s.running && s.relay_revision && s.revision && s.relay_revision!==s.revision)
    ver+=' · relay still on '+s.relay_revision+' — click “Check for updates” to apply';
  $('ver').textContent=ver;
  $('url').textContent='Relay: http://localhost:'+s.port+'  →  OSC '+(s.nomad_ip||'?')+':'+s.eos_port;
  $('purl').textContent=s.phone_url; $('ptok').textContent=s.token;
  $('autostart').checked=s.autostart;
  if(!loaded){ // fill the form once so we don't clobber edits
    const c=d.config;
    for(const k of ['NOMAD_IP','EOS_RX_PORT','HTTP_PORT','BIND_ADDR','LOG_FILE','TOKEN','OSC_USER']) $(k).value=c[k]??'';
    const sel=$('destructive_policy'); sel.innerHTML='';
    for(const p of d.policies){ const o=document.createElement('option'); o.value=o.textContent=p; if(p===c.destructive_policy)o.selected=true; sel.appendChild(o); }
    $('auto_update').checked=!!c.auto_update;
    $('macro_map').value=JSON.stringify(c.macro_map||{},null,2);
    $('key_map').value=JSON.stringify(c.key_map||{},null,2);
    loaded=true;
  }
}
async function save(restart){
  let macro,key;
  try{ macro=JSON.parse($('macro_map').value||'{}'); key=JSON.parse($('key_map').value||'{}'); }
  catch(e){ $('saved').className='err'; $('saved').textContent='Macro/Key map must be valid JSON'; return; }
  const cfg={ destructive_policy:$('destructive_policy').value, auto_update:$('auto_update').checked,
              macro_map:macro, key_map:key, restart:restart };
  for(const k of ['NOMAD_IP','EOS_RX_PORT','HTTP_PORT','BIND_ADDR','LOG_FILE','TOKEN','OSC_USER']) cfg[k]=$(k).value;
  let r;
  try{ r=await api('/api/config',{method:'POST',body:JSON.stringify(cfg)}); }
  catch(e){ $('saved').className='err'; $('saved').textContent='NOT saved — '+PANEL_DOWN; return; }
  if(!r.ok){ $('saved').className='err'; $('saved').textContent=r.error||'Save failed'; return; }
  $('saved').className='ok'; $('saved').textContent=restart?'Saved & restarting…':'Saved.';
  setTimeout(()=>$('saved').textContent='',2500);
}
async function ctl(action){
  const err=$('relayerr'); err.style.display='none'; err.textContent='';
  let r;
  try{ r=await api('/api/control',{method:'POST',body:JSON.stringify({action})}); }
  catch(e){ err.textContent=PANEL_DOWN; err.style.display='block'; refresh(); return; }
  if(r && r.error){
    err.textContent=(action==='stop'?'':'Relay did not start:\\n\\n')+r.error;
    err.style.display='block';
  } else if((action==='start'||action==='restart') && r && r.running===false){
    err.textContent='Relay did not start (no further detail in the logs).';
    err.style.display='block';
  }
  refresh();
}
async function genToken(){
  try{ const r=await api('/api/token'); $('TOKEN').value=r.token; }
  catch(e){ $('saved').className='err'; $('saved').textContent=PANEL_DOWN; }
}
async function sendTest(){
  $('testres').textContent='sending…'; $('testres').className='note';
  let r; try{ r=await api('/api/test',{method:'POST',body:JSON.stringify({phrase:$('phrase').value})}); }
  catch(e){ $('testres').className='note err'; $('testres').textContent='✗ '+PANEL_DOWN; return; }
  const ok=r.code===200; $('testres').className='note '+(ok?'ok':'err');
  $('testres').textContent=(ok?'✓ ':'✗ '+(r.code||'')+' ')+r.body;
}
async function pingConsole(){ $('misc').textContent='pinging…';
  let r; try{ r=await api('/api/ping?ip='+encodeURIComponent($('NOMAD_IP').value)); }
  catch(e){ $('misc').textContent='✗ '+PANEL_DOWN; return; }
  $('misc').textContent=r.ok?('✓ '+r.ip+' is reachable'):('✗ '+r.ip+' did not respond'); }
async function checkUpdate(){ $('misc').textContent='checking…';
  let r; try{ r=await api('/api/update',{method:'POST',body:'{}'}); }
  catch(e){ $('misc').textContent='✗ '+PANEL_DOWN; return; }
  $('misc').textContent=r.message; if(r.status==='updated') setTimeout(refresh,800); }
async function pollLogs(){ if(!paused){ try{ const r=await api('/api/logs?pos='+logpos);
  if(r.text){ const el=$('log'); el.textContent+=r.text; el.scrollTop=el.scrollHeight; } logpos=r.pos; }catch(e){} } }

refresh(); setInterval(refresh,2500); setInterval(pollLogs,1000);
</script>
</body></html>"""


if __name__ == "__main__":
    sys.exit(main())
