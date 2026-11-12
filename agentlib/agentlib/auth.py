"""Sign-in.

- Default: agents sign in exactly like typing `claude` in a terminal (Claude Code login, or your gateway)
- use_login_only(): opt-in; removes API-key style variables from this process so the Claude Code
  login (your subscription) is what gets used. Call once at app start.
"""
from __future__ import annotations

import os

API_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")


def use_login_only() -> list[str]:
    """Returns the names of the variables it removed."""
    removed = [k for k in API_KEY_VARS if k in os.environ]
    for k in removed:
        os.environ.pop(k, None)
    return removed
