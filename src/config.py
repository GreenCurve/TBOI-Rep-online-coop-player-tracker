"""
Central configuration for Isaac Player Tracker.
Edit the values below (or override with environment variables / a config.json
next to this file) to match your setup.
"""

import os
import json

# ---- defaults --------------------------------------------------------------

DEFAULT_LOG_PATH = (
    r"C:\Users\Egor\Documents\My Games\Binding of Isaac Repentance+\log.txt"
)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isaac_players.db")

DEFAULT_HOTKEY = "f9"          # global hotkey to show/hide the overlay
DEFAULT_TAGS = ["new player", "ok player", "bad player"]

# ---- load optional config.json for easy editing without touching code ----

_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def _load_overrides():
    if os.path.exists(_CFG_PATH):
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

_overrides = _load_overrides()

LOG_PATH = _overrides.get("log_path", DEFAULT_LOG_PATH)
DB_PATH = _overrides.get("db_path", DEFAULT_DB_PATH)
HOTKEY = _overrides.get("hotkey", DEFAULT_HOTKEY)
