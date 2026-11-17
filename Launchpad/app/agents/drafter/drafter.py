"""The agent drafter (helper, not a crew card): turns a sentence or two into the "new agent" form's fields.

- One cheap one-shot call (app/agents/drafter/agent.md: haiku, no tools, structured output DRAFT_SCHEMA); nothing
  is saved: the fields come back to the Crew tab's form and the user edits them before saving
- Fields are normalised in code (app/agents/folder_agents.py normalise); a name that is taken gets a -2, -3 ... suffix
- Define path (undefined roles): agent_draft {role} adds the role's samples, skills and the Role Reviewer's case
  (proposed name, purpose, description, instructions beyond the skill) as context; the output fields are unchanged
- draft_with_usage(): the fields plus the call's own tokens and cost (sent with agent_drafted)
"""
from __future__ import annotations

from pathlib import Path

from agentlib import AgentError

from ... import costs
from ...meter import Meter
from .. import crew
from ..folder_agents import ADDABLE_PURPOSES, MODELS, AgentFormError, normalise

MAX_DRAFT_TEXT = 2000
MAX_CONTEXT = 6000            # a role review's case passed as context (define path)

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "lowercase-with-dashes"},
        "description": {"type": "string", "description": "one sentence"},
        "purpose": {"type": "string", "enum": list(ADDABLE_PURPOSES)},
        "model": {"type": "string", "enum": list(MODELS)},
        "tools": {"type": "array", "items": {"type": "string", "enum": list(crew.TOOL_CHOICES)}},
        "instructions": {"type": "string", "description": "3-8 short bullet lines"},
    },
    "required": ["name", "description", "purpose", "model", "tools", "instructions"],
    "additionalProperties": False,
}


def draft_message(text: str, context: str = "") -> str:
    """The drafter's one message; context = a role review's case (define path), placed before the user's words."""
    ctx = (f"Review context (an undefined role the user decided to define):\n{context.strip()[:MAX_CONTEXT]}\n"
           if str(context or "").strip() else "")
    return (f"Allowed tools: {', '.join(crew.TOOL_CHOICES)}.\n{ctx}"
            f"The user wants an agent that does this:\n{text}")


async def draft(hub, folder: Path, text: str, context: str = "") -> dict:
    """One cheap one-shot call -> clean form fields (the user edits them before saving). AgentFormError if it fails."""
    return (await draft_with_usage(hub, folder, text, context))[0]


async def draft_with_usage(hub, folder: Path, text: str, context: str = "") -> tuple[dict, dict]:
    """draft() plus the call's own tokens and cost (costs.meter_usage), sent with agent_drafted."""
    text = str(text or "").strip()
    if not text:
        raise AgentFormError("say in a sentence or two what the agent should do")
    text = text[:MAX_DRAFT_TEXT]
    agent = crew.load("drafter", engine=hub.settings.engine, project=folder, output_schema=DRAFT_SCHEMA,
                      save_conversation=False)
    meter = Meter(hub, session_id=None, role="drafter", name=crew.display("drafter"))
    await meter.set_status("working")
    reply = None
    try:
        async with agent.session() as s:
            async for ev in s.stream(draft_message(text, context)):
                await meter.feed(ev)
                if getattr(ev, "type", "") == "done":
                    reply = ev.reply
    except AgentError as e:
        await meter.add_reply(e.reply)
        raise AgentFormError(f"the drafter failed: {e.short}") from None
    finally:
        await meter.set_status("done")
    if reply is None or reply.status == "error" or not isinstance(reply.data, dict):
        raise AgentFormError(f"the drafter gave no usable form ({getattr(reply, 'error', None) or 'no reply'})")
    fields, _ = normalise(reply.data, strict=False)
    if fields["name"] and (fields["name"] in crew.builtin_names()
                           or (folder / ".claude" / "agents" / f"{fields['name']}.md").exists()):
        fields["name"] = _free_name(folder, fields["name"])
    return fields, costs.meter_usage(meter)


def _free_name(folder: Path, name: str) -> str:
    taken = crew.builtin_names()
    for k in range(2, 100):
        cand = f"{name}-{k}"
        if cand not in taken and not (folder / ".claude" / "agents" / f"{cand}.md").exists():
            return cand
    return name
