"""
Opie Control — a small Tkinter desktop panel for the voice relay.

  * Setup    edit NOMAD_IP / token / ports / policy / macro & key maps
  * Control  start / stop / restart the relay; toggle autostart at login
  * Logs     live tail of the relay log
  * Test     fire a command at the local relay, check console reachability

Pure standard library (Tkinter ships with macOS Python). No third-party deps.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import tkinter as tk
from tkinter import ttk, messagebox

from . import config as opie_config
from . import service

POLICIES = ["block_all", "record_update", "allow_all"]

# Plain-language fields shown as single-line entries: (config key, label, width)
TEXT_FIELDS = [
    ("NOMAD_IP", "Console IP (Nomad/Eos)", 24),
    ("EOS_RX_PORT", "Console OSC RX port", 10),
    ("HTTP_PORT", "Relay HTTP port", 10),
    ("BIND_ADDR", "Bind address", 32),
    ("LOG_FILE", "Log file (blank = default)", 40),
]


class OpieGUI:
    def __init__(self, root):
        self.root = root
        self.config_path = opie_config.default_config_path()
        opie_config.ensure_exists(self.config_path)
        self.cfg = opie_config.load(self.config_path)

        self.proc = None            # manual (non-autostart) relay subprocess
        self._log_pos = 0
        self._log_paused = False
        self.vars = {}

        self._build_ui()
        self._apply_cfg_to_form()
        self._status_tick()
        self._poll_logs()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        self.root.minsize(640, 560)
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        # --- status header ---
        head = ttk.Frame(outer)
        head.pack(fill="x", pady=(0, 8))
        self.dot = tk.Canvas(head, width=14, height=14, highlightthickness=0)
        self.dot.pack(side="left")
        self._dot_id = self.dot.create_oval(2, 2, 12, 12, fill="#999", outline="")
        self.status_lbl = ttk.Label(head, text="checking…", font=("", 13, "bold"))
        self.status_lbl.pack(side="left", padx=8)
        self.url_lbl = ttk.Label(head, text="", foreground="#555")
        self.url_lbl.pack(side="right")

        # --- notebook ---
        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        self._build_setup_tab(nb)
        self._build_logs_tab(nb)
        self._build_test_tab(nb)

        # --- control bar ---
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        self.start_btn = ttk.Button(bar, text="Start", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop)
        self.stop_btn.pack(side="left", padx=4)
        self.restart_btn = ttk.Button(bar, text="Restart", command=self.restart)
        self.restart_btn.pack(side="left", padx=4)
        self.autostart_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Autostart at login",
                        variable=self.autostart_var,
                        command=self.toggle_autostart).pack(side="right")

    def _build_setup_tab(self, nb):
        tab = ttk.Frame(nb, padding=12)
        nb.add(tab, text="Setup")

        grid = ttk.Frame(tab)
        grid.pack(fill="x")
        for i, (key, label, width) in enumerate(TEXT_FIELDS):
            ttk.Label(grid, text=label).grid(row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(grid, textvariable=var, width=width).grid(
                row=i, column=1, sticky="w", padx=8, pady=3)

        # destructive policy
        r = len(TEXT_FIELDS)
        ttk.Label(grid, text="Destructive policy").grid(row=r, column=0, sticky="w", pady=3)
        self.vars["destructive_policy"] = tk.StringVar()
        ttk.Combobox(grid, textvariable=self.vars["destructive_policy"],
                     values=POLICIES, state="readonly", width=18).grid(
            row=r, column=1, sticky="w", padx=8, pady=3)

        # token row with generate / copy
        r += 1
        ttk.Label(grid, text="Shared token").grid(row=r, column=0, sticky="w", pady=3)
        tokrow = ttk.Frame(grid)
        tokrow.grid(row=r, column=1, sticky="w", padx=8, pady=3)
        self.vars["TOKEN"] = tk.StringVar()
        ttk.Entry(tokrow, textvariable=self.vars["TOKEN"], width=40).pack(side="left")
        ttk.Button(tokrow, text="Generate", command=self._generate_token).pack(side="left", padx=4)
        ttk.Button(tokrow, text="Copy", command=self._copy_token).pack(side="left")

        # macro_map / key_map as small JSON editors
        maps = ttk.Frame(tab)
        maps.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(maps, text="Macro map  (spoken word → console macro #)").grid(
            row=0, column=0, sticky="w")
        ttk.Label(maps, text="Key map  (spoken word → console key name)").grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        self.macro_text = tk.Text(maps, width=30, height=7, font=("Menlo", 11))
        self.macro_text.grid(row=1, column=0, sticky="nsew")
        self.key_text = tk.Text(maps, width=30, height=7, font=("Menlo", 11))
        self.key_text.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        maps.columnconfigure(0, weight=1)
        maps.columnconfigure(1, weight=1)
        maps.rowconfigure(1, weight=1)

        # save buttons
        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Save", command=lambda: self.save()).pack(side="left")
        ttk.Button(btns, text="Save & Restart",
                   command=lambda: self.save(restart=True)).pack(side="left", padx=6)
        ttk.Button(btns, text="Reveal config folder",
                   command=self._open_config_folder).pack(side="right")
        self.save_note = ttk.Label(btns, text="", foreground="#2a7")
        self.save_note.pack(side="right", padx=8)

    def _build_logs_tab(self, nb):
        tab = ttk.Frame(nb, padding=8)
        nb.add(tab, text="Logs")
        top = ttk.Frame(tab)
        top.pack(fill="x")
        self.pause_btn = ttk.Button(top, text="Pause", command=self._toggle_pause)
        self.pause_btn.pack(side="left")
        ttk.Button(top, text="Clear view", command=self._clear_log_view).pack(side="left", padx=4)
        ttk.Button(top, text="Reveal in Finder", command=self._reveal_log).pack(side="right")
        self.log_text = tk.Text(tab, wrap="none", height=20, font=("Menlo", 11),
                                state="disabled", background="#111", foreground="#ddd")
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))
        sb = ttk.Scrollbar(tab, command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

    def _build_test_tab(self, nb):
        tab = ttk.Frame(nb, padding=12)
        nb.add(tab, text="Test & Help")

        ttk.Label(tab, text="Send a command to the running relay:").pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        self.test_var = tk.StringVar(value="channel 5 at full")
        ent = ttk.Entry(row, textvariable=self.test_var, width=40)
        ent.pack(side="left")
        ent.bind("<Return>", lambda e: self.send_test())
        ttk.Button(row, text="Send", command=self.send_test).pack(side="left", padx=6)
        self.test_result = ttk.Label(tab, text="", foreground="#357")
        self.test_result.pack(anchor="w", pady=(2, 10))

        checks = ttk.Frame(tab)
        checks.pack(fill="x")
        ttk.Button(checks, text="Health check", command=self.health_check_popup).pack(side="left")
        ttk.Button(checks, text="Check console reachable",
                   command=self.check_console).pack(side="left", padx=6)
        ttk.Button(checks, text="Phone setup info",
                   command=self.phone_setup).pack(side="left")

        help_txt = (
            "Tips\n"
            "•  Set the console IP + token, then Save & Restart.\n"
            "•  Turn on Autostart at login so the relay runs whenever the Mac boots.\n"
            "•  Try phrases: 'channel 5 at full', 'group 3 at 50 percent', 'go', "
            "'blackout'.\n"
            "•  For a no-console dry run, set Console IP to 127.0.0.1 and run "
            "'opie-sniff 8000' in a terminal to watch the OSC."
        )
        ttk.Label(tab, text=help_txt, justify="left", foreground="#444").pack(
            anchor="w", pady=(16, 0))

    # ------------------------------------------------------------- helpers --

    def _apply_cfg_to_form(self):
        for key, _, _ in TEXT_FIELDS:
            self.vars[key].set(str(self.cfg.get(key, "")))
        self.vars["destructive_policy"].set(
            self.cfg.get("destructive_policy", "record_update"))
        self.vars["TOKEN"].set(self.cfg.get("TOKEN", ""))
        self.macro_text.delete("1.0", "end")
        self.macro_text.insert("1.0", json.dumps(self.cfg.get("macro_map", {}), indent=2))
        self.key_text.delete("1.0", "end")
        self.key_text.insert("1.0", json.dumps(self.cfg.get("key_map", {}), indent=2))

    def _collect(self):
        cfg = dict(self.cfg)  # preserve any unknown keys
        cfg["NOMAD_IP"] = self.vars["NOMAD_IP"].get().strip()
        cfg["BIND_ADDR"] = self.vars["BIND_ADDR"].get().strip()
        cfg["TOKEN"] = self.vars["TOKEN"].get().strip()
        cfg["LOG_FILE"] = self.vars["LOG_FILE"].get().strip()
        cfg["destructive_policy"] = self.vars["destructive_policy"].get().strip()
        for key in ("EOS_RX_PORT", "HTTP_PORT"):
            raw = self.vars[key].get().strip()
            try:
                cfg[key] = int(raw)
            except ValueError:
                raise ValueError(f"{key} must be a whole number (got {raw!r}).")
        cfg["macro_map"] = json.loads(self.macro_text.get("1.0", "end").strip() or "{}")
        cfg["key_map"] = json.loads(self.key_text.get("1.0", "end").strip() or "{}")
        return cfg

    def _port(self):
        try:
            return int(self.vars["HTTP_PORT"].get().strip())
        except (ValueError, KeyError):
            return int(self.cfg.get("HTTP_PORT", 8765))

    def _token(self):
        return self.vars["TOKEN"].get().strip() or self.cfg.get("TOKEN", "")

    def _log_file(self):
        return (self.vars["LOG_FILE"].get().strip()
                or self.cfg.get("LOG_FILE")
                or opie_config.default_log_path())

    def _flash(self, msg):
        self.save_note.config(text=msg)
        self.root.after(2500, lambda: self.save_note.config(text=""))

    # --------------------------------------------------------------- save --

    def save(self, restart=False):
        try:
            cfg = self._collect()
        except ValueError as e:
            messagebox.showerror("Invalid setting", str(e))
            return False
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON",
                                 f"macro map / key map must be valid JSON.\n\n{e}")
            return False
        old_log = self.cfg.get("LOG_FILE")
        opie_config.save(cfg, self.config_path)
        self.cfg = cfg
        if cfg.get("LOG_FILE") != old_log:
            self._log_pos = 0
        if restart:
            self._apply_restart()
            self._flash("Saved & restarting…")
        else:
            self._flash("Saved.")
        self._refresh_now()
        return True

    def _apply_restart(self):
        if service.is_loaded():
            service.restart()
        elif self.proc and self.proc.poll() is None:
            self._kill_proc()
            self._spawn()

    # ------------------------------------------------------------ control --

    def _spawn(self):
        if self.proc and self.proc.poll() is None:
            return
        log = self._log_file()
        try:
            os.makedirs(os.path.dirname(log), exist_ok=True)
        except OSError:
            pass
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "opie", "--config", self.config_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=opie_config.app_support_dir())

    def _kill_proc(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def start(self):
        if not self.save():
            return
        if service.is_loaded():
            service.restart()
        else:
            self._spawn()
        self.root.after(800, self._refresh_now)

    def stop(self):
        # Managed-by-launchd stop = turn autostart off (KeepAlive can't be paused).
        if service.is_loaded():
            service.disable()
            self.autostart_var.set(False)
        self._kill_proc()
        self.root.after(500, self._refresh_now)

    def restart(self):
        if service.is_loaded():
            service.restart()
        else:
            self._kill_proc()
            self._spawn()
        self.root.after(800, self._refresh_now)

    def toggle_autostart(self):
        on = self.autostart_var.get()
        try:
            if on:
                if not self.save():
                    self.autostart_var.set(False)
                    return
                self._kill_proc()  # free the port for the launchd-managed copy
                service.enable(python_exe=sys.executable, config_path=self.config_path)
            else:
                service.disable()
        except Exception as e:  # noqa: BLE001 - surface any launchctl error
            messagebox.showerror("Autostart", str(e))
        self.root.after(900, self._refresh_now)

    # ------------------------------------------------------------- status --

    def _status_tick(self):
        self._refresh_now()
        self.root.after(2500, self._status_tick)

    def _refresh_now(self):
        threading.Thread(target=self._status_worker, daemon=True).start()

    def _status_worker(self):
        running = self._health_ok()
        loaded = service.is_loaded()
        self.root.after(0, lambda: self._apply_status(running, loaded))

    def _health_ok(self, timeout=0.8):
        try:
            url = f"http://127.0.0.1:{self._port()}/health"
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.status == 200 and r.read().decode("utf-8", "replace").strip() == "ok"
        except Exception:
            return False

    def _apply_status(self, running, loaded):
        self.dot.itemconfig(self._dot_id, fill="#2ecc71" if running else "#888")
        text = "Running" if running else "Stopped"
        if loaded:
            text += "  ·  autostart on"
        self.status_lbl.config(text=text)
        self.url_lbl.config(text=f"http://127.0.0.1:{self._port()}   →   "
                                 f"{self.vars['NOMAD_IP'].get().strip()}:"
                                 f"{self.vars['EOS_RX_PORT'].get().strip()}")
        # keep the checkbox in sync with reality (set() does not fire the command)
        self.autostart_var.set(loaded)
        # when launchd owns the process, manual start/stop are disabled
        self.start_btn.config(state="disabled" if loaded else "normal")
        self.stop_btn.config(state="normal")
        self.restart_btn.config(state="normal")

    # --------------------------------------------------------------- logs --

    def _poll_logs(self):
        if not self._log_paused:
            path = self._log_file()
            try:
                size = os.path.getsize(path)
                if size < self._log_pos:        # rotated / truncated
                    self._log_pos = 0
                with open(path, "r", errors="replace") as f:
                    f.seek(self._log_pos)
                    new = f.read()
                    self._log_pos = f.tell()
                if new:
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", new)
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
            except FileNotFoundError:
                pass
            except OSError:
                pass
        self.root.after(800, self._poll_logs)

    def _toggle_pause(self):
        self._log_paused = not self._log_paused
        self.pause_btn.config(text="Resume" if self._log_paused else "Pause")

    def _clear_log_view(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _reveal_log(self):
        path = self._log_file()
        if os.path.exists(path):
            subprocess.run(["open", "-R", path])
        else:
            subprocess.run(["open", os.path.dirname(path)])

    # ------------------------------------------------------- test & help --

    def send_test(self):
        phrase = self.test_var.get().strip()
        if not phrase:
            return
        port, token = self._port(), self._token()
        self.test_result.config(text="sending…", foreground="#357")

        def work():
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/command",
                    data=phrase.encode("utf-8"),
                    headers={"X-Token": token, "Content-Type": "text/plain"})
                with urllib.request.urlopen(req, timeout=3) as r:
                    code, body = r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                code, body = e.code, e.read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                code, body = None, f"{e}  (is the relay running?)"
            self.root.after(0, lambda: self._show_test(code, body))

        threading.Thread(target=work, daemon=True).start()

    def _show_test(self, code, body):
        if code == 200:
            self.test_result.config(text=f"✓  {body}", foreground="#2a7")
        else:
            self.test_result.config(text=f"✗  {code or ''} {body}".strip(),
                                    foreground="#c0392b")

    def health_check_popup(self):
        ok = self._health_ok(timeout=1.5)
        if ok:
            messagebox.showinfo("Health", "Relay is up — /health returned ok.")
        else:
            messagebox.showwarning("Health",
                                   "No response on /health. Start the relay first.")

    def check_console(self):
        ip = self.vars["NOMAD_IP"].get().strip()

        def work():
            try:
                r = subprocess.run(["ping", "-c", "1", "-t", "1", ip],
                                   capture_output=True, text=True, timeout=4)
                ok = r.returncode == 0
            except Exception:  # noqa: BLE001
                ok = False
            msg = (f"{ip} is reachable ✓" if ok else
                   f"{ip} did not respond ✗\n\nCheck the lighting-network cable / "
                   f"Wi-Fi and that the Console IP is correct.")
            self.root.after(0, lambda: messagebox.showinfo("Console reachability", msg))

        threading.Thread(target=work, daemon=True).start()

    def phone_setup(self):
        bind = self.vars["BIND_ADDR"].get().strip()
        host = bind if bind and bind != "0.0.0.0" else socket.gethostname()
        url = f"http://{host}:{self._port()}/command"
        token = self._token()
        win = tk.Toplevel(self.root)
        win.title("iPhone Shortcut setup")
        win.geometry("520x300")
        frm = ttk.Frame(win, padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Build a Siri Shortcut with one 'Get Contents of URL' action:",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 8))
        for label, value in (("URL", url), ("Method", "POST"),
                             ("Header  X-Token", token),
                             ("Request body (text)", "the dictated phrase")):
            row = ttk.Frame(frm)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label + ":", width=18).pack(side="left")
            v = tk.StringVar(value=value)
            ttk.Entry(row, textvariable=v, width=40).pack(side="left", fill="x", expand=True)

        def copy(text):
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(12, 0))
        ttk.Button(btns, text="Copy URL", command=lambda: copy(url)).pack(side="left")
        ttk.Button(btns, text="Copy token", command=lambda: copy(token)).pack(side="left", padx=6)
        ttk.Label(frm, text="(Full walkthrough: shortcuts/SHORTCUT_SETUP.md in the repo.)",
                  foreground="#777").pack(anchor="w", pady=(10, 0))

    def _generate_token(self):
        self.vars["TOKEN"].set(opie_config.generate_token())
        self._flash("New token generated — Save to apply.")

    def _copy_token(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._token())
        self._flash("Token copied.")

    def _open_config_folder(self):
        subprocess.run(["open", os.path.dirname(self.config_path)])


def main():
    root = tk.Tk()
    root.title("Opie Control")
    try:
        OpieGUI(root)
    except tk.TclError as e:
        print(f"Could not start the GUI: {e}", file=sys.stderr)
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
