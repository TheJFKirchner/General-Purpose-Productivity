"""TEST ONLY: a scripted stand-in for Claude, used when SHE_FAKE=1 (or --fake).

It calls the assistant's real tools, so tests exercise the real checks, edits and page reloads
without spending tokens. Send a chat message like:

    FAKE: [{"select": "n11"}, {"style": ["n11", {"background": "#fef3c7"}]}, {"say": "Done."}]

Steps: {"outline": ["n0", 2]}, {"around": "n12"}, {"select": "n12"}, {"styles": "n12"}, {"find": "text"},
       {"markup": "n13"}, {"text": ["t21", "new {#1}", "optional old part"]}, {"style": ["n8", {"color": "red"}]},
       {"attr": ["n9", "class", "lead"]}, {"var": ["v1", "#dc2626"]}, {"rule": [".card h2", "color: teal"]},
       {"replace": ["n13", "<b>new</b> markup"]}, {"say": "text"}, {"usage": {...}},
       {"request": "what the user asked"} (digits in it may be typed; default: none)
"""
import json


async def run_fake(session, message: str):
    if not message.startswith("FAKE:"):
        return "(test mode) Send FAKE: [steps]; the real model is off.", None
    log, usage = [], None
    session.user_message = ""          # the script is not the user's words
    calls = {
        "outline": lambda a: session.tool_outline(*a) if isinstance(a, list) else session.tool_outline(a),
        "around": session.tool_around, "select": session.tool_select, "styles": session.tool_styles,
        "find": session.tool_find_text, "markup": session.tool_view_markup,
        "text": lambda a: session.tool_set_text(*a), "style": lambda a: session.tool_set_style(*a),
        "attr": lambda a: session.tool_set_attr(*a), "var": lambda a: session.tool_set_theme_var(*a),
        "rule": lambda a: session.tool_set_page_rule(*a), "replace": lambda a: session.tool_replace_markup(*a),
    }
    for step in json.loads(message[5:]):
        (kind, arg), = step.items()
        if kind == "request":
            session.user_message = arg
        elif kind == "say":
            log.append(arg)
        elif kind == "usage":
            usage = arg
        else:
            r = await calls[kind](arg)
            text = r["content"][0]["text"]
            log.append(f"{kind}{' error' if r.get('is_error') else ''}: {text if kind in ('styles', 'find') or r.get('is_error') else text.splitlines()[0]}")
    return " | ".join(log), usage
