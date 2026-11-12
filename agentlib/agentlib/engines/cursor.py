"""Cursor engine: STUB. Declares what Cursor can do so the interface is shaped for it; cannot run yet.

- Plan (research doc §8): Cursor Python SDK (`cursor-sdk`, beta) -> Agent.create / send / on_delta, custom_tools
- Known gaps: no app-set system prompt (use AGENTS.md in cwd + message prefix), no live permission hook,
  no fork, sync API (wrap in asyncio.to_thread), its own model names
- Until this lands, Cursor-style agent files run on the claude engine (loaders/cursor.py)
- available=False -> Engine.check() raises EngineUnavailable in agent.session(), before open() is reached
- When building it: system_prompt / ends_turn are enforced by Engine.check(); if the engine emulates them
  (AGENTS.md + message prefix, a "stop now" tool result), set those flags True or every agent with
  instructions / ask_user will raise CapabilityError
"""
from __future__ import annotations

from ..errors import EngineUnavailable
from .base import Capabilities, Engine


class CursorEngine(Engine):
    name = "cursor"
    capabilities = Capabilities(
        available=False,
        system_prompt=False,
        custom_tools=True,
        mcp_servers=True,
        streaming=True,
        resume=True,
        fork=False,
        usage=True,
        ends_turn=False,        # unverified: may need a tool result telling the agent to stop
        permission_hook=False,
        project_setup=True,
    )

    def open(self, agent, *, resume, fork, cost_base):
        raise EngineUnavailable("the cursor engine is not built yet; run this agent with engine='claude'")
