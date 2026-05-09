"""
access.py — User access control
Admin can add/remove users via /adduser and /removeuser
"""

import json
import os

ACCESS_FILE = "access.json"


def _load() -> dict:
    if os.path.exists(ACCESS_FILE):
        with open(ACCESS_FILE, "r") as f:
            return json.load(f)
    return {"allowed_users": []}


def _save(data: dict) -> None:
    with open(ACCESS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_allowed(user_id: int, admin_id: int) -> bool:
    """Admin is always allowed. Check others against allowed list."""
    if user_id == admin_id:
        return True
    data = _load()
    return user_id in data["allowed_users"]


def add_user(user_id: int) -> bool:
    """Add user. Returns False if already exists."""
    data = _load()
    if user_id in data["allowed_users"]:
        return False
    data["allowed_users"].append(user_id)
    _save(data)
    return True


def remove_user(user_id: int) -> bool:
    """Remove user. Returns False if not found."""
    data = _load()
    if user_id not in data["allowed_users"]:
        return False
    data["allowed_users"].remove(user_id)
    _save(data)
    return True


def list_users() -> list:
    """Return list of all allowed user IDs."""
    return _load()["allowed_users"]
    
