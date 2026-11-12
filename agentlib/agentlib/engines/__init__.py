"""Engine registry.

- get_engine("claude" | "cursor" | <registered>) -> Engine
- register_engine(name, factory): add an engine (the fake engine registers itself when agentlib.fake is imported)
- Engines import lazily, so the Agent SDK is only needed when a claude agent actually runs
"""
from __future__ import annotations

from typing import Callable

from ..errors import EngineUnavailable
from .base import Capabilities, Engine, EngineSession, TurnState

_FACTORIES: dict[str, Callable[[], Engine]] = {}
_CACHE: dict[str, Engine] = {}


def register_engine(name: str, factory: Callable[[], Engine]) -> None:
    _FACTORIES[name] = factory
    _CACHE.pop(name, None)


def _claude() -> Engine:
    from .claude import ClaudeEngine
    return ClaudeEngine()


def _cursor() -> Engine:
    from .cursor import CursorEngine
    return CursorEngine()


register_engine("claude", _claude)
register_engine("cursor", _cursor)


def get_engine(name: str) -> Engine:
    if name not in _CACHE:
        if name not in _FACTORIES:
            hint = " (import agentlib.fake first)" if name == "fake" else ""
            raise EngineUnavailable(f"unknown engine '{name}'{hint}; known: {sorted(_FACTORIES)}")
        _CACHE[name] = _FACTORIES[name]()
    return _CACHE[name]


__all__ = ["Capabilities", "Engine", "EngineSession", "TurnState", "get_engine", "register_engine"]
