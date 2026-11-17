"""The CLI chat's CLI-and-model choices (the picker under the CLI chat's box).

- Same table as the planner picker: app/agents/planner/choices.py HARNESSES (harness = "CLI" in the UI), the same
  availability from agentlib (Cursor listed, disabled). The configured pilot_model is always listed for the chosen CLI,
  so --pilot-model haiku shows up as a choice
- Settings (per user): pilot_harness (None = the launch engine's CLI) and pilot_model (None = the CLI agent file's
  model). --pilot-model / --pilot-harness override them for one launch; the fake demo (settings.engine "fake") forces
  the fake engine for everything
- A chat's CLI and model are fixed when its first message is sent (PilotChat.started); a chat nobody has written to is
  reloaded at once with a new choice (app/hub.py cli_choose). Independent of the planner's choice
- choice_event(settings): the cli_choice event (options, what the next new chat starts on)
"""
from __future__ import annotations

from .. import crew
from ..planner import choices as table

CLI_SETTINGS = ("pilot_harness", "pilot_model")


def cli_harness(settings) -> str:
    """The remembered CLI when it is known, else the launch engine's CLI."""
    h = getattr(settings, "pilot_harness", None)
    return h if table.harness(h) else table.launch_harness(settings.engine)


def cli_model(settings) -> str:
    """pilot_model, else the CLI agent file's model, else the CLI's first model."""
    m = getattr(settings, "pilot_model", None) or crew.builtin_model("pilot")
    if m:
        return str(m)
    h = table.harness(cli_harness(settings))
    return h["models"][0][0] if h else "sonnet"


def cli_engine(settings) -> str:
    """The agentlib engine a new CLI chat runs on (fake in the demo; else the chosen CLI's engine while available)."""
    return table.engine_for(cli_harness(settings), settings.engine)


def options(settings) -> list[dict]:
    return table.harness_options({cli_harness(settings): [cli_model(settings)]})


def find(oid: str, settings) -> dict | None:
    return next((o for o in options(settings) if o["id"] == oid), None)


def fields(harness_name: str, model: str) -> dict:
    """The chat's CLI and model as event fields (chat_started, chat_model, snapshot chats)."""
    return {"harness": harness_name, "model": model, "label": table.label(harness_name, model),
            "option_id": table.option_id(harness_name, model)}


def choice_event(settings, overridden=()) -> dict:
    """cli_choice: what the CLI chat's picker shows. choice = what the next new chat starts on (per user)."""
    h, m = cli_harness(settings), cli_model(settings)
    return {"type": "cli_choice", "options": options(settings),
            "choice": {"option_id": table.option_id(h, m), "harness": h, "model": m, "label": table.label(h, m)},
            "overridden": sorted(k for k in overridden if k in CLI_SETTINGS)}
