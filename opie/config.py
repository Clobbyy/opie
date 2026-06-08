"""
Filesystem locations + config read/write for Opie.

The installed package stays read-only: all user data (config, logs, the launchd
agent) lives under the user's ~/Library, never inside the package. This module is
the single place that knows *where* those things go, so the relay and the GUI can't
disagree. Pure standard library.

The config *schema* and defaults live in relay.py (DEFAULT_CONFIG); this module only
owns paths and read/write/scaffold helpers.
"""

import json
import os
import secrets

APP_NAME = "Opie"
PLIST_LABEL = "com.opie.relay"


def app_support_dir() -> str:
    return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")


def logs_dir() -> str:
    return os.path.expanduser(f"~/Library/Logs/{APP_NAME}")


def default_config_path() -> str:
    """Where the live config lives. Overridable with the OPIE_CONFIG env var."""
    return os.environ.get("OPIE_CONFIG") or os.path.join(app_support_dir(), "config.json")


def default_log_path() -> str:
    return os.path.join(logs_dir(), "relay.log")


def example_config_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "resources", "config.example.json")


def generate_token() -> str:
    """A strong, URL-safe shared secret (the iPhone Shortcut sends the same value)."""
    return secrets.token_urlsafe(32)


def load(path: str = None) -> dict:
    path = path or default_config_path()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(cfg: dict, path: str = None) -> str:
    """Write config atomically, owner-only (it holds the token)."""
    path = path or default_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def ensure_exists(path: str = None):
    """
    Create a starter config (copied from the bundled example, with a freshly
    generated token and a real log path) if none exists yet.

    Returns (path, created: bool).
    """
    path = path or default_config_path()
    if os.path.exists(path):
        return path, False
    try:
        with open(example_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    tok = cfg.get("TOKEN", "")
    if (not tok) or str(tok).startswith("CHANGE_ME"):
        cfg["TOKEN"] = generate_token()
    if not cfg.get("LOG_FILE"):
        cfg["LOG_FILE"] = default_log_path()
    save(cfg, path)
    return path, True
