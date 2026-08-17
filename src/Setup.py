"""
Central configuration for Isaac Player Tracker.
Edit the values below (or override with environment variables / a config.json
next to this file) to match your setup.
"""

import os
import json

# ---- load optional config.json for easy editing without touching code ----

_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config.json")

def _load_overrides():
    if os.path.exists(_CFG_PATH):
        try:
            with open(_CFG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

_overrides = _load_overrides()

LOG_PATH = _overrides.get("log_path")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "isaac_players.db")
HOTKEY = _overrides.get("overlay_toggle_hotkey")
TAGS = _overrides.get("player_tags")

print(LOG_PATH,DB_PATH,HOTKEY,TAGS)