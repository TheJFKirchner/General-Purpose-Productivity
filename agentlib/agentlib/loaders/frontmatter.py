"""Split a markdown file into (front matter dict, body). Same format Claude Code and Cursor use."""
from __future__ import annotations

from pathlib import Path

import yaml

from ..errors import AgentFileError


def parse(text: str, source: str = "<text>") -> tuple[dict, str]:
    text = text.lstrip("﻿")
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("\n")
    try:
        end = next(i for i, line in enumerate(parts[1:], 1) if line.strip() == "---")
    except StopIteration:
        raise AgentFileError(f"{source}: front matter opened with '---' but never closed") from None
    try:
        meta = yaml.safe_load("\n".join(parts[1:end])) or {}
    except yaml.YAMLError as e:
        raise AgentFileError(f"{source}: bad YAML front matter: {e}") from e
    if not isinstance(meta, dict):
        raise AgentFileError(f"{source}: front matter must be key: value pairs")
    return meta, "\n".join(parts[end + 1:]).strip()


def read(path: Path) -> tuple[dict, str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise AgentFileError(f"cannot read {path}: {e}") from e
    return parse(text, str(path))


def as_list(value) -> list[str] | None:
    """Claude Code writes lists as 'Read, Grep' or as YAML lists; None stays None."""
    if value is None:
        return None
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]
