"""
launchd control for the Opie relay (macOS). Powers the GUI's "autostart at login"
toggle and start/stop/restart. Pure standard library.

A per-user LaunchAgent (~/Library/LaunchAgents/com.opie.relay.plist) runs the relay
at login and keeps it alive. The plist is rendered from a bundled template so it
points at the right Python (the venv), the user's config, and a log file.
"""

import os
import shlex
import subprocess
import sys

from . import __version__
from . import config as opie_config

LABEL = opie_config.PLIST_LABEL  # "com.opie.relay"


def plist_path() -> str:
    return os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")


def _template_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "resources", "com.opie.relay.plist.tmpl")


def _uid() -> int:
    return os.getuid()


def render(python_exe=None, config_path=None, stdout_log=None, stderr_log=None,
           workdir=None, pythonpath=None) -> str:
    """Fill the plist template with concrete paths.

    When Opie runs from source (no pip install), `pythonpath` points launchd at
    the source tree so `python3 -m opie` resolves. Defaults to the recorded
    install root; None (pip install) omits the env block entirely.
    """
    python_exe = python_exe or sys.executable
    config_path = config_path or opie_config.default_config_path()
    logs = opie_config.logs_dir()
    stdout_log = stdout_log or os.path.join(logs, "relay.out.log")
    stderr_log = stderr_log or os.path.join(logs, "relay.err.log")
    workdir = workdir or opie_config.app_support_dir()
    if pythonpath is None:
        pythonpath = opie_config.get_install_root()
    env_block = ""
    if pythonpath:
        env_block = ("    <key>EnvironmentVariables</key>\n"
                     "    <dict>\n"
                     "        <key>PYTHONPATH</key>\n"
                     f"        <string>{pythonpath}</string>\n"
                     "    </dict>\n")
    with open(_template_path(), "r", encoding="utf-8") as f:
        tmpl = f.read()
    subs = {
        "LABEL": LABEL,
        "PYTHON": python_exe,
        "CONFIG": config_path,
        "STDOUT": stdout_log,
        "STDERR": stderr_log,
        "WORKDIR": workdir,
        "ENV_BLOCK": env_block,
    }
    for k, v in subs.items():
        tmpl = tmpl.replace("{{" + k + "}}", v)
    return tmpl


def install(**kw) -> str:
    """Write (or overwrite) the LaunchAgent plist. Returns its path."""
    path = plist_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.makedirs(opie_config.logs_dir(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render(**kw))
    return path


def _launchctl(*args):
    try:
        return subprocess.run(["launchctl", *args], capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        # launchctl missing or unusable (non-macOS, locked-down env): act like a
        # clean failure so callers (is_loaded/enable/disable) degrade instead of
        # raising. The relay still runs fine as a plain subprocess.
        return subprocess.CompletedProcess(args, 1, "", "launchctl unavailable")


def load():
    return _launchctl("load", "-w", plist_path())


def unload():
    # `unload` needs the plist file on disk; if it's gone while the job is
    # still loaded, fall back to bootout by label (works from the live job) —
    # otherwise Stop silently fails and KeepAlive resurrects the relay.
    r = _launchctl("unload", "-w", plist_path())
    if is_loaded():
        r = _launchctl("bootout", f"gui/{_uid()}/{LABEL}")
    return r


def restart():
    """Restart the running agent in place (picks up config edits)."""
    return _launchctl("kickstart", "-k", f"gui/{_uid()}/{LABEL}")


def is_installed() -> bool:
    return os.path.exists(plist_path())


def is_loaded() -> bool:
    r = _launchctl("list")
    if r.returncode != 0:
        return False
    for line in r.stdout.splitlines():
        # columns: PID  Status  Label  (tab-separated); last field is the label
        if line.rsplit("\t", 1)[-1].strip() == LABEL:
            return True
    return False


def enable(**kw):
    """Autostart ON: install the plist and load it (starts now + at every login)."""
    install(**kw)
    return load()


def disable():
    """Autostart OFF: unload the agent and remove its plist."""
    res = unload()
    p = plist_path()
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass
    return res


# --------------------------------------------------------------------------- #
# The clickable ~/Applications/Opie.app                                        #
# --------------------------------------------------------------------------- #

def app_path() -> str:
    return os.path.expanduser("~/Applications/Opie.app")


_APP_LAUNCHER = """#!/bin/bash
# Opie.app — opens the browser control panel (Tk not required).
# Regenerated automatically by Opie itself (opie/service.py) so a code update
# can never strand an outdated launcher (an old one kept pointing at the
# removed Tk GUI, which made the panel silently unlaunchable).
PY=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 2>/dev/null)"; do
  [ -n "$c" ] && [ -x "$c" ] && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  osascript >/dev/null 2>&1 \\
    -e 'display dialog "Opie needs Python 3, which comes with Apple'"'"'s Command Line Tools.\\n\\nOpen Terminal and run:  xcode-select --install" with title "Opie" buttons {"OK"} default button "OK" with icon caution'
  exit 1
fi
{PYTHONPATH_LINE}nohup "$PY" -m opie.panel >/dev/null 2>&1 &
exit 0
"""

_APP_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Opie</string>
  <key>CFBundleDisplayName</key><string>Opie</string>
  <key>CFBundleIdentifier</key><string>com.opie.control</string>
  <key>CFBundleExecutable</key><string>Opie</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>{VERSION}</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
"""


def _write_if_changed(path, content, mode=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == content:
                return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if mode is not None:
        os.chmod(path, mode)
    return True


def ensure_app_launcher():
    """
    (Re)write ~/Applications/Opie.app so the launcher always matches the code
    that's actually installed. install.sh creates the .app once; this keeps it
    current across auto-updates. Only acts on macOS and only when the .app
    already exists or Opie runs from a recorded install root (the one-line
    installer); pip users who never had the app don't get one foisted on them.
    """
    if sys.platform != "darwin":
        return None
    root = opie_config.get_install_root()
    app = app_path()
    if not root and not os.path.isdir(app):
        return None
    macos_dir = os.path.join(app, "Contents", "MacOS")
    os.makedirs(macos_dir, exist_ok=True)
    py_line = f"export PYTHONPATH={shlex.quote(root)}\n" if root else ""
    _write_if_changed(os.path.join(macos_dir, "Opie"),
                      _APP_LAUNCHER.replace("{PYTHONPATH_LINE}", py_line),
                      mode=0o755)
    _write_if_changed(os.path.join(app, "Contents", "Info.plist"),
                      _APP_PLIST.replace("{VERSION}", __version__))
    return app
