"""Which models an engine offers, without sending any request (no tokens).

- await list_models(engine="claude") / list_models_sync(...) -> list[ModelInfo]
- Claude: read from Claude Code's start-up handshake (follows the user's sign-in and Claude Code version);
  starts and stops a `claude` process, so it takes a few seconds
- Engines without it (capabilities.list_models False) raise CapabilityError; stubs raise EngineUnavailable
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field


@dataclass
class ModelInfo:
    id: str                                   # full model id, pass as Agent(model=...)
    name: str = ""                            # human name, e.g. "Haiku 5.5"
    description: str = ""                     # what it is for, e.g. "Fastest for quick answers"
    aliases: list[str] = field(default_factory=list)       # other names the engine accepts ("haiku", "default")
    is_default: bool = False                  # the engine's default model (what model=None gives)
    effort_levels: list[str] = field(default_factory=list)  # accepted Agent(effort=...) values; [] = unknown/none

    def to_dict(self) -> dict:
        return asdict(self)


async def list_models(engine: str = "claude", *, env: dict[str, str] | None = None,
                      timeout_s: float | None = 60) -> list[ModelInfo]:
    """Models the engine offers, deduplicated by id, in the engine's order. No tokens are spent.
    env: extra environment for the engine process (e.g. a gateway). Raises AgentError if the engine fails."""
    from .engines import get_engine
    eng = get_engine(engine)
    eng.check_list_models()
    return await eng.list_models(env=dict(env or {}), timeout_s=timeout_s)


def list_models_sync(engine: str = "claude", **kw) -> list[ModelInfo]:
    """list_models() for code with no running event loop (uses asyncio.run)."""
    return asyncio.run(list_models(engine, **kw))
