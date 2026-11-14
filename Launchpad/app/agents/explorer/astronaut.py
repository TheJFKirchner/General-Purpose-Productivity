"""The Explorer (role key astronaut): a read-only file finder (Read, Grep, Glob; haiku), run by the app as its own agentlib session.

- Returns ONLY links: structured output (ASTRONAUT_SCHEMA) -> capped + checked in code
- Writes no file itself; code adds its links to flight-log.md and its routing notes to operations-manual.md
- Links outside the project or to missing files are dropped
- One Explorer meter per session (cumulative usage); status working during a trip, idle between trips
"""
from __future__ import annotations

from agentlib import AgentError

from . import crew
from .meter import Meter
from .sessionfiles import one_line

MAX_LINKS = 8

ASTRONAUT_SCHEMA = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "file path relative to the working folder"},
                    "line": {"type": "integer", "description": "optional line number"},
                    "answer": {"type": "string", "description": "one or two sentences"},
                },
                "required": ["path", "answer"],
                "additionalProperties": False,
            },
        },
        "routing_notes": {"type": "string"},
    },
    "required": ["links"],
    "additionalProperties": False,
}


async def explore(ls, question: str) -> dict:
    """Run one Explorer for `ls` (a LaunchSession). -> {links:[{path, line, answer}], text, error?}."""
    hub, folder = ls.hub, ls.folder
    agent = crew.load("astronaut", engine=hub.settings.engine, project=folder.project,
                      output_schema=ASTRONAUT_SCHEMA, save_conversation=False)
    await hub.count_use(agent.name)             # one count per explore
    if ls.astronaut_meter is None:              # one Explorer per session: working on each trip, idle between
        ls.astronaut_meter = Meter(hub, session_id=ls.id, role="astronaut", name=crew.display("astronaut"))
    meter = ls.astronaut_meter
    calls_before, cost_before = meter.tool_calls, meter.cost_usd
    await meter.set_status("working")
    reply = None
    try:
        async with agent.session() as s:
            async for ev in s.stream(question):
                await meter.feed(ev)
                if getattr(ev, "type", "") == "done":
                    reply = ev.reply
    except AgentError as e:
        await meter.add_reply(e.reply)
        await meter.set_status("idle")
        return {"links": [], "text": f"The {meter.name} failed: {e.short}", "error": e.short}

    data = (reply.data if reply is not None and reply.status != "error" else None) or {}
    links = []
    for item in (data.get("links") or [])[: MAX_LINKS * 2]:
        path, answer = str(item.get("path", "")).strip(), one_line(item.get("answer", ""), 300)
        target = folder.resolve_in_project(path)
        if target is None or not target.is_file() or not answer:
            continue
        line = item.get("line") if isinstance(item.get("line"), int) and item.get("line") > 0 else None
        rel = folder.rel(target)
        links.append({"path": rel, "line": line, "answer": answer})
        folder.add_flight_log(rel, answer, line=line, source=meter.name)
        if len(links) >= MAX_LINKS:
            break
    folder.add_operations(agent=meter.name, role="astronaut", step=None, notes=str(data.get("routing_notes") or ""),
                          tool_calls=meter.tool_calls - calls_before, cost_usd=meter.cost_usd - cost_before)
    await meter.set_status("idle")
    if reply is not None and reply.status == "error":
        return {"links": [], "text": f"The {meter.name} stopped: {reply.error}", "error": reply.error}
    if not links:
        return {"links": [], "text": f"The {meter.name} found no matching files."}
    text = "\n".join(f"- {l['path']}{':' + str(l['line']) if l['line'] else ''} — {l['answer']}" for l in links)
    return {"links": links, "text": text + "\n(Added to the flight log.)"}
