"""
config.py — Settings management
Stores per-user settings in settings.json
"""

import json
import os

# ── FILE ─────────────────────────────────────────────────────────────────────
SETTINGS_FILE = "settings.json"

# ── DEFAULTS ─────────────────────────────────────────────────────────────────
DEFAULT_CHANNEL_NAME   = "@YourChannel"
DEFAULT_WATERMARK_TEXT = "Join @YourChannel for more movies"

# ── PYROGRAM CREDENTIALS ─────────────────────────────────────────────────────
# Get from https://my.telegram.org → API Development Tools → Create App
# Pyrogram uses MTProto directly — supports up to 2 GB, no local server needed.
API_ID   = os.getenv("TELEGRAM_API_ID",   "YOUR_API_ID")    # e.g. "12345678"
API_HASH = os.getenv("TELEGRAM_API_HASH", "YOUR_API_HASH")  # e.g. "abcdef1234567890"

# ── WATERMARK VISUAL SETTINGS ─────────────────────────────────────────────────
WATERMARK_FONT_SIZE   = 28
WATERMARK_FONT_COLOR  = "white"
WATERMARK_BOX_COLOR   = "black@0.4"
WATERMARK_BOX_ENABLED = True
WATERMARK_POSITION    = "bottom_center"   # bottom_center | bottom_left | top_center | center
WATERMARK_START_SEC   = 0
WATERMARK_END_SEC     = 10

# ─────────────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user_settings(user_id: int) -> dict:
    """Return settings for a user, falling back to defaults."""
    all_settings = _load()
    uid = str(user_id)
    if uid not in all_settings:
        return {
            "channel_name":   DEFAULT_CHANNEL_NAME,
            "watermark_text": DEFAULT_WATERMARK_TEXT,
        }
    return all_settings[uid]


def set_user_settings(user_id: int, **kwargs) -> dict:
    """Update one or more settings for a user and return updated dict."""
    all_settings = _load()
    uid = str(user_id)
    if uid not in all_settings:
        all_settings[uid] = {
            "channel_name":   DEFAULT_CHANNEL_NAME,
            "watermark_text": DEFAULT_WATERMARK_TEXT,
        }
    all_settings[uid].update(kwargs)
    _save(all_settings)
    return all_settings[uid]


def reset_user_settings(user_id: int) -> dict:
    """Reset user settings to defaults."""
    all_settings = _load()
    uid = str(user_id)
    if uid in all_settings:
        del all_settings[uid]
        _save(all_settings)
    return {
        "channel_name":   DEFAULT_CHANNEL_NAME,
        "watermark_text": DEFAULT_WATERMARK_TEXT,
    }
    
