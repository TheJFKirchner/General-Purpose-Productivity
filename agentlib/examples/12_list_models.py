"""12 - List the models an engine offers, before any request (no tokens), e.g. to fill a model menu.

Run:  python examples/12_list_models.py          (fake engine, free)
      python examples/12_list_models.py --live   (Claude: starts and stops Claude Code, a few seconds; NO tokens)

Raw SDK equivalent: ClaudeSDKClient(options).connect() then get_server_info()["models"].
agentlib: await list_models(engine) / list_models_sync(engine) -> list[ModelInfo].

ModelInfo: id (pass to Agent(model=...)), name ("Haiku 5.5"), description ("Fastest for quick answers"),
aliases (["haiku"]; the default model also has "default"), is_default, effort_levels. One entry per id.
Engines without it (capabilities.list_models False) raise CapabilityError; failures raise AgentError.
"""
import sys

from agentlib import AgentError, list_models_sync

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    from agentlib import fake
    # Without fake.models(...) the fake engine offers two models ("fake-large", "fake-small").
    # Script your own:  fake.models(["m-1", {"id": "m-2", "name": "Two"}])   or a failure: fake.models(fail="...")

try:
    models = list_models_sync(ENGINE)         # in async code: await list_models(ENGINE)
except AgentError as e:
    print("could not list models:", e.short)  # e.g. Claude Code not installed / not signed in
    sys.exit(1)

for m in models:
    star = "*" if m.is_default else " "
    print(f"{star} {m.id:24} {m.name:14} {m.description}   aliases={m.aliases}")
