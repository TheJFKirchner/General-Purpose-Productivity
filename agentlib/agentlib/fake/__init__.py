"""Fake engine for free tests. Importing this module registers engine "fake" (and its sign-in side, FakeSetup).

- Self-contained: the core library never imports it -> delete this folder and nothing else breaks
- Usage:  from agentlib import fake;  fake.script("helper", [[fake.say("hi")]]);  Agent("helper", engine="fake")
"""
from ..engines import register_engine, register_setup
from .engine import (DEFAULT_MODELS, PLAN_TOOL, FakeEngine, FakeSetup, ask, call, fail, kills, models, opened,
                     output, parallel, plan, process, rate_limit, reset, saved_rules, say, script, spend)

register_engine("fake", FakeEngine)
register_setup("fake", FakeSetup)

__all__ = ["DEFAULT_MODELS", "PLAN_TOOL", "FakeEngine", "FakeSetup", "ask", "call", "fail", "kills", "models",
           "opened", "output", "parallel", "plan", "process", "rate_limit", "reset", "saved_rules", "say", "script",
           "spend"]
