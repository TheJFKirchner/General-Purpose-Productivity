"""The editor's assistant: one Claude agent (Haiku by default) that changes looks and wording.

It never sees the page's data. Everything it gets comes from htmldoc's redacted views (outline,
path, find_text, view_markup) and from the open page's computed colors and fonts. No screenshots.

Lockdown (same as the dashboard agent): no built-in tools, only the tools below, permission_mode
"dontAsk", no settings/CLAUDE.md/skills/memory/connectors, a turn and time limit per request.
Each tool's edit goes through htmldoc's checks (exact ids, typed-number rule, CSS value rules,
no edits inside hidden parts, small data-free elements only for markup).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from htmldoc import EditError

REQUEST_TIMEOUT_S = 90
MAX_TURNS = 10
MAX_FAILED_EDITS = 4
STATE = Path.home() / ".smart-html-editor"

# Cost estimate - ASSUMPTIONS, not a bill. Claude Haiku 5.5 list prices in USD per million tokens
# (prompts up to 100K tokens). Override with SHE_PRICE_IN / SHE_PRICE_OUT.
PRICING = {"input_per_mtok": float(os.environ.get("SHE_PRICE_IN", 0.10)),
           "output_per_mtok": float(os.environ.get("SHE_PRICE_OUT", 0.50)),
           "cache_write_x": 1.25, "cache_read_x": 0.10}

TOOL_NAMES = ["outline", "around", "select", "styles", "find_text", "view_markup", "set_text", "set_style",
              "set_attr", "set_theme_var", "set_page_rule", "replace_markup"]

SYSTEM_PROMPT = """You edit one HTML page while the user looks at it in the Smart HTML Editor. You change its looks and wording only.

Privacy: you never see the page's data, and you never ask for it. Scripts, embedded files, charts, data attributes and data-table cells are summarized, and numbers in text appear as tokens {#1}, {#2}, ... Keep a token to keep its number; drop it to remove the number. Never type a number the user didn't type in their message (typed digits are checked). There are no screenshots.

Ids: n12 = an element, t45 = a piece of text, v3 = a theme variable. Use only ids you have been shown.

Each message gives you the selected element (what the user clicked) with its outline and path, the colors and fonts the page shows for it and its parents, the theme variables and the page rules.

Work outward from the selection:
1. Try the selected element first.
2. If what the user means isn't there, step out or look around before you edit: the color or background often comes from a parent or a CSS rule (use styles), the words may be in a sibling or the heading above (use around or outline), and content drawn by a script can only be restyled through the element that holds it. Select the element that really holds the thing, then edit there.
3. Say where you made the change in a few words ("on the card around it", "on every card heading").

Which tool:
| Request | Tool |
|---|---|
| Change words | set_text (keeps the tags and numbers; use old_text for part of a long text) |
| This element's color, background, font, size, spacing, border, alignment, or hide it | set_style |
| A class, link, tooltip, alt text | set_attr |
| Theme colors or fonts used across the page | set_theme_var if the page has theme variables; otherwise set_page_rule |
| The same look for many elements (every heading, every card, all tables) | set_page_rule (one CSS rule placed last in the page, so it wins at equal specificity; add !important only if styles shows it didn't take) |
| Bold or italic a word, add a subtitle or a bullet, reorder small bits of text | view_markup, then replace_markup (small, data-free elements only) |

After a style change you can check it with styles. If a tool refuses, read why: fix the call, or pick a better element and try again.

Refuse in one sentence, saying it's a Claude Code job and why: changing data, numbers, chart contents or scripts; adding or removing tables, charts or data; anything inside a hidden part.

Keep replies to one or two short sentences. Changes show on the page at once; the user can Undo, Save or Discard."""


def estimate_cost(usage: dict | None) -> dict | None:
    if not usage:
        return None
    p = PRICING
    fresh = usage.get("input_tokens", 0) or 0
    written = usage.get("cache_creation_input_tokens", 0) or 0
    read = usage.get("cache_read_input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    usd = (fresh + written * p["cache_write_x"] + read * p["cache_read_x"]) * p["input_per_mtok"] / 1e6 + out * p["output_per_mtok"] / 1e6
    return {"cents": round(usd * 100, 4), "input_tokens": fresh + written + read, "output_tokens": out}


def styles_text(info: dict | None) -> str:
    """The page's report on an element and its parents, as short lines."""
    if not info or not info.get("chain"):
        return "  (unknown: the page is not open or didn't answer)"
    lines = []
    for el in info["chain"]:
        parts = [f"text {el.get('color')}", f"background {el.get('background')}"]
        if el.get("backgroundImage"):
            parts.append(f"background image/gradient {el['backgroundImage']}")
        parts.append(f"font {el.get('font')}")
        for k in ("border", "padding", "radius", "shadow", "display"):
            if el.get(k):
                parts.append(f"{k} {el[k]}")
        line = f"  {el.get('node') or '(no id: drawn by a script)'} {el.get('tag', '')}: " + " · ".join(parts)
        if el.get("rules"):
            line += "\n    rules: " + " | ".join(el["rules"][:8])
        if el.get("inline"):
            line += f"\n    style attribute: {el['inline']}"
        lines.append(line)
    if info.get("generated"):
        lines.insert(0, "  The click landed on content drawn by the page's script; the first element with an id holds it.")
    return "\n".join(lines)


def _text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def _err(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}], "is_error": True}


class Assistant:
    def __init__(self, ws, settings: dict):
        self.ws = ws
        self.settings = settings
        self.client = None
        self.chat_cents = 0.0
        self.failed = 0
        self.user_message = ""
        self.edits = 0

    async def close(self):
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

    # ------------------------------------------------------------ one request
    def context(self, message: str) -> str:
        ws, d = self.ws, self.ws.doc
        sel = ws.selected if ws.selected in d.nodes and ws.selected != "n0" else None
        out = [f"Page: {d.page_summary()}"]
        if sel:
            nd = d.node(sel)
            out += [f"Selected: {d.label(nd)}", f"Path: {d.path(nd)}", "Outline of the selection:",
                    d.outline(sel, depth=2, max_lines=60, reveal=sel)]
            out += ["Looks on the page (selected element first, then its parents):", styles_text(ws.click)]
        else:
            out += ["Selected: nothing (the whole page). Page outline:", d.outline("n0", depth=3, max_lines=60)]
        out += ["Theme variables:", d.theme_text(), "Page rules added in the editor:", d.page_rules_text(),
                f"Request: {message}"]
        return "\n".join(out)

    async def ask(self, message: str) -> dict:
        self.failed = 0
        self.edits = 0
        self.user_message = message
        with self.ws.lock:
            text = self.context(message)
        if self.settings.get("fake"):
            from fake_model import run_fake
            reply, usage = await run_fake(self, message)
        else:
            reply, usage = await run_claude(self, text)
        cost = estimate_cost(usage)
        if cost:
            self.chat_cents += cost["cents"]
        return {"reply": reply, "cost": cost, "chat_cents": round(self.chat_cents, 4), "edits": self.edits}

    # ------------------------------------------------------------ tools (shared by the real model and the test model)
    def _read(self, fn) -> dict:
        try:
            with self.ws.lock:
                return _text(fn())
        except EditError as e:
            return _err(str(e))

    def _edit(self, fn) -> dict:
        if self.failed >= MAX_FAILED_EDITS:
            return _err("Edit limit reached for this request. Stop and tell the user what you couldn't do.")
        try:
            with self.ws.lock:
                result = fn()
                if result != "No change.":
                    self.edits += 1
                    self.ws.page_changed()
            return _text(result)
        except EditError as e:
            self.failed += 1
            return _err(f"Refused: {e}")

    @property
    def _reveal(self):
        return self.ws.selected

    async def tool_outline(self, node: str, depth: int = 2) -> dict:
        return self._read(lambda: self.ws.doc.outline(node, depth=max(1, min(int(depth), 6)), reveal=self._reveal))

    async def tool_around(self, node: str) -> dict:
        return self._read(lambda: self.ws.doc.around(node, reveal=self._reveal))

    async def tool_select(self, node: str) -> dict:
        def go():
            d = self.ws.doc
            nd = d.node(node)
            self.ws.selected = nd.id
            self.ws.select_seq += 1
            return f"Selected {d.label(nd)} (the user sees it highlighted).\nPath: {d.path(nd)}\n" + d.outline(nd.id, depth=2, max_lines=40)
        result = self._read(go)
        if not result.get("is_error"):
            info = await self.ws.request_styles(node)
            if info:
                self.ws.click = info
            result["content"][0]["text"] += "\nLooks on the page:\n" + styles_text(info)
        return result

    async def tool_styles(self, node: str) -> dict:
        try:
            with self.ws.lock:
                self.ws.doc.node(node)
        except EditError as e:
            return _err(str(e))
        return _text(styles_text(await self.ws.request_styles(node)))

    async def tool_find_text(self, query: str) -> dict:
        return self._read(lambda: self.ws.doc.find_text(query))

    async def tool_view_markup(self, node: str) -> dict:
        return self._read(lambda: self.ws.doc.view_markup(node))

    async def tool_set_text(self, text_id: str, new_text: str, old_text: str | None = None) -> dict:
        return self._edit(lambda: self.ws.doc.set_text(text_id, new_text, old_text, allowed_digits=self.user_message))

    async def tool_set_style(self, node: str, styles: dict) -> dict:
        return self._edit(lambda: self.ws.doc.set_style(node, styles))

    async def tool_set_attr(self, node: str, name: str, value: str | None) -> dict:
        return self._edit(lambda: self.ws.doc.set_attr(node, name, value, allowed_digits=self.user_message))

    async def tool_set_theme_var(self, var: str, value: str) -> dict:
        return self._edit(lambda: self.ws.doc.set_theme_var(var, value))

    async def tool_set_page_rule(self, selector: str, declarations: str) -> dict:
        return self._edit(lambda: self.ws.doc.set_page_rule(selector, declarations))

    async def tool_replace_markup(self, node: str, html: str) -> dict:
        return self._edit(lambda: self.ws.doc.replace_markup(node, html, allowed_digits=self.user_message))

    # ------------------------------------------------------------ Claude Agent SDK
    def options(self):
        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, tool
        s = self
        node = {"type": "string", "description": "element id like n12"}

        def schema(props: dict, required: list) -> dict:
            return {"type": "object", "additionalProperties": False, "required": required, "properties": props}

        @tool("outline", "Data-free outline of an element (n0 = whole page): ids, tags, classes, texts with numbers as tokens.",
              schema({"node": node, "depth": {"type": "integer", "minimum": 1, "maximum": 6}}, ["node"]))
        async def outline(a):
            return await s.tool_outline(a["node"], a.get("depth", 2))

        @tool("around", "Path to an element, plus its parent and siblings (step out / look around).", schema({"node": node}, ["node"]))
        async def around(a):
            return await s.tool_around(a["node"])

        @tool("select", "Move the selection to another element (the user sees it highlighted); returns its outline and looks.",
              schema({"node": node}, ["node"]))
        async def select(a):
            return await s.tool_select(a["node"])

        @tool("styles", "Colors, fonts and the CSS rules that apply, for an element and its parents, as the open page shows them.",
              schema({"node": node}, ["node"]))
        async def styles(a):
            return await s.tool_styles(a["node"])

        @tool("find_text", "Find visible text on the page (numbers as tokens; data-table cells are not searched).",
              schema({"query": {"type": "string"}}, ["query"]))
        async def find_text(a):
            return await s.tool_find_text(a["query"])

        @tool("view_markup", "Inner HTML of a small, data-free element, with numbers as tokens.", schema({"node": node}, ["node"]))
        async def view_markup(a):
            return await s.tool_view_markup(a["node"])

        @tool("set_text", "Replace one text (t-id). Whole text, or only old_text within it. Keep {#k} tokens for numbers.",
              schema({"text_id": {"type": "string"}, "new_text": {"type": "string"}, "old_text": {"type": "string"}},
                     ["text_id", "new_text"]))
        async def set_text(a):
            return await s.tool_set_text(a["text_id"], a["new_text"], a.get("old_text"))

        @tool("set_style", 'Set CSS on one element\'s style attribute, e.g. {"color": "#b91c1c", "font-weight": "600"}; "" removes one.',
              schema({"node": node, "styles": {"type": "object", "additionalProperties": {"type": "string"}}}, ["node", "styles"]))
        async def set_style(a):
            return await s.tool_set_style(a["node"], a["styles"])

        @tool("set_attr", "Set or remove (value null) one attribute: class, title, alt, aria-label, href, target, rel, hidden, lang, dir, role.",
              schema({"node": node, "name": {"type": "string"}, "value": {"type": ["string", "null"]}}, ["node", "name", "value"]))
        async def set_attr(a):
            return await s.tool_set_attr(a["node"], a["name"], a["value"])

        @tool("set_theme_var", "Change a theme variable's value (v-id), e.g. a color used across the page.",
              schema({"var": {"type": "string"}, "value": {"type": "string"}}, ["var", "value"]))
        async def set_theme_var(a):
            return await s.tool_set_theme_var(a["var"], a["value"])

        @tool("set_page_rule", 'Add or replace one CSS rule for the whole page, e.g. ".card h2", "color: #0f766e; font-size: 20px". '
              'Empty declarations remove the rule.',
              schema({"selector": {"type": "string"}, "declarations": {"type": "string"}}, ["selector", "declarations"]))
        async def set_page_rule(a):
            return await s.tool_set_page_rule(a["selector"], a["declarations"])

        @tool("replace_markup", "Replace the inner HTML of a small, data-free element (from view_markup). Keep {#k} tokens.",
              schema({"node": node, "html": {"type": "string"}}, ["node", "html"]))
        async def replace_markup(a):
            return await s.tool_replace_markup(a["node"], a["html"])

        tools = [outline, around, select, styles, find_text, view_markup, set_text, set_style, set_attr,
                 set_theme_var, set_page_rule, replace_markup]
        server = create_sdk_mcp_server(name="page", version="1.0.0", tools=tools)
        workspace = STATE / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        return ClaudeAgentOptions(
            model=self.settings["model"],
            effort=self.settings["effort"],
            system_prompt=SYSTEM_PROMPT,
            tools=[],                                       # no built-in tools at all (no file reading)
            mcp_servers={"page": server},
            allowed_tools=[f"mcp__page__{n}" for n in TOOL_NAMES],
            permission_mode="dontAsk",                     # anything not pre-approved is denied
            strict_mcp_config=True,                         # ignore other MCP configs / connectors
            setting_sources=[],                             # no CLAUDE.md, settings, hooks, skills
            skills=[],
            max_turns=MAX_TURNS,
            cwd=str(workspace),                             # an empty folder, not the page's folder
            env={"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false"},
        )


async def run_claude(session: Assistant, text: str) -> tuple[str, dict | None]:
    from claude_agent_sdk import AssistantMessage, ClaudeSDKClient, ResultMessage, TextBlock

    if session.client is None:
        session.client = ClaudeSDKClient(options=session.options())
        await session.client.connect()

    async def one_message():
        yield {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]},
               "parent_tool_use_id": None}

    last_text, result = "", None

    async def converse():
        nonlocal last_text, result
        await session.client.query(one_message())
        async for msg in session.client.receive_response():
            if isinstance(msg, AssistantMessage):
                texts = [b.text for b in msg.content if isinstance(b, TextBlock) and b.text.strip()]
                if texts:
                    last_text = " ".join(texts)
            elif isinstance(msg, ResultMessage):
                result = msg

    try:
        await asyncio.wait_for(converse(), REQUEST_TIMEOUT_S)
    except asyncio.TimeoutError:
        await session.close()
        return f"Stopped: that took longer than {REQUEST_TIMEOUT_S} seconds. Changes already made stay (Undo removes them).", None

    usage = result.usage if result is not None else None
    if result is not None and result.is_error:
        if result.subtype == "error_max_turns":
            return f"Stopped after {MAX_TURNS} steps without finishing. Changes already made stay (Undo removes them).", usage
        detail = "; ".join(getattr(result, "errors", None) or []) or (result.result or result.subtype)
        return f"The assistant hit an error: {detail}", usage
    return (result.result if result and result.result else last_text) or "Done.", usage


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)
