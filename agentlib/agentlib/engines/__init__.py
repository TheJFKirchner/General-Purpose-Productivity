"""Engine registry.

- get_engine("claude" | "cursor" | <registered>) -> Engine
- register_engine(name, factory): add an engine (the fake engine registers itself when agentlib.fake is imported)
- Engines import lazily, so the Agent SDK is only needed when a claude agent actually runs
- get_setup(name) -> EngineSetup (sign-in side, SDK-free); register_setup(name, factory). An engine with no
  registered setup gets the generic EngineSetup (nothing to set up)
"""
from __future__ import annotations

from typing import Callable

from ..errors import EngineUnavailable
from .base import Capabilities, Connection, Engine, EngineSession, EngineSetup, TurnState

_FACTORIES: dict[str, Callable[[], Engine]] = {}
_CACHE: dict[str, Engine] = {}
_SETUPS: dict[str, Callable[[], EngineSetup]] = {}


def register_engine(name: str, factory: Callable[[], Engine]) -> None:
    _FACTORIES[name] = factory
    _CACHE.pop(name, None)


def register_setup(name: str, factory: Callable[[], EngineSetup]) -> None:
    """Sign-in handling for an engine (its section of the local setup file). Must not import the engine SDK."""
    _SETUPS[name] = factory


def _claude() -> Engine:
    from .claude import ClaudeEngine
    return ClaudeEngine()


def _claude_setup() -> EngineSetup:
    from .claude_setup import ClaudeSetup
    return ClaudeSetup()


def _cursor() -> Engine:
    from .cursor import CursorEngine
    return CursorEngine()


register_engine("claude", _claude)
register_engine("cursor", _cursor)
register_setup("claude", _claude_setup)


def get_engine(name: str) -> Engine:
    if name not in _CACHE:
        if name not in _FACTORIES:
            hint = " (import agentlib.fake first)" if name == "fake" else ""
            raise EngineUnavailable(f"unknown engine '{name}'{hint}; known: {sorted(_FACTORIES)}")
        _CACHE[name] = _FACTORIES[name]()
    return _CACHE[name]


def get_setup(name: str) -> EngineSetup:
    if name in _SETUPS:
        return _SETUPS[name]()
    if name not in _FACTORIES:
        hint = " (import agentlib.fake first)" if name == "fake" else ""
        raise EngineUnavailable(f"unknown engine '{name}'{hint}; known: {sorted(_FACTORIES)}")
    return EngineSetup(name)


__all__ = ["Capabilities", "Connection", "Engine", "EngineSession", "EngineSetup", "TurnState", "get_engine",
           "get_setup", "register_engine", "register_setup"]
