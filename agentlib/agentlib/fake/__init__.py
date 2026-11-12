"""Fake engine for free tests. Importing this module registers engine "fake".

- Self-contained: the core library never imports it -> delete this folder and nothing else breaks
- Usage:  from agentlib import fake;  fake.script("helper", [[fake.say("hi")]]);  Agent("helper", engine="fake")
"""
from ..engines import register_engine
from .engine import FakeEngine, ask, call, fail, rate_limit, reset, say, script

register_engine("fake", FakeEngine)

__all__ = ["FakeEngine", "ask", "call", "fail", "rate_limit", "reset", "say", "script"]
