"""Fake engine for free tests. Importing this module registers engine "fake" (and its sign-in side, FakeSetup).

- Self-contained: the core library never imports it -> delete this folder and nothing else breaks
- Usage:  from agentlib import fake;  fake.script("helper", [[fake.say("hi")]]);  Agent("helper", engine="fake")
"""
from ..engines import register_engine, register_setup
from .engine import (DEFAULT_MODELS, FakeEngine, FakeSetup, ask, call, fail, models, output, rate_limit, reset, say,
                     script, spend)

register_engine("fake", FakeEngine)
register_setup("fake", FakeSetup)

__all__ = ["DEFAULT_MODELS", "FakeEngine", "FakeSetup", "ask", "call", "fail", "models", "output", "rate_limit",
           "reset", "say", "script", "spend"]
