"""
launchd control for the Opie relay (macOS). Powers the GUI's "autostart at login"
toggle and start/stop/restart. Pure standard library.

A per-user LaunchAgent (~/Library/LaunchAgents/com.opie.relay.plist) runs the relay
at login and keeps it alive. The plist is rendered from a bundled template so it
points at the right Python (the venv), the user's config, and a log file.
"""

import os
import subprocess
import sys

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
           workdir=None) -> str:
    """Fill the plist template with concrete paths."""
    python_exe = python_exe or sys.executable
    config_path = config_path or opie_config.default_config_path()
    logs = opie_config.logs_dir()
    stdout_log = stdout_log or os.path.join(logs, "relay.out.log")
    stderr_log = stderr_log or os.path.join(logs, "relay.err.log")
    workdir = workdir or opie_config.app_support_dir()
    with open(_template_path(), "r", encoding="utf-8") as f:
        tmpl = f.read()
    subs = {
        "LABEL": LABEL,
        "PYTHON": python_exe,
        "CONFIG": config_path,
        "STDOUT": stdout_log,
        "STDERR": stderr_log,
        "WORKDIR": workdir,
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
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def load():
    return _launchctl("load", "-w", plist_path())


def unload():
    return _launchctl("unload", "-w", plist_path())


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
