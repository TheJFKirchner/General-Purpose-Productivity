"""Loads the library's editable text files from agentlib/prompts/*.md.

- Every model-facing sentence the library adds lives in a .md file there, not in code
- Placeholders are written {like_this} and filled with fill(); unknown placeholders are left as-is
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=None)
def load(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def fill(name: str, **values: str) -> str:
    text = load(name)
    for key, val in values.items():
        text = text.replace("{" + key + "}", str(val))
    return text
