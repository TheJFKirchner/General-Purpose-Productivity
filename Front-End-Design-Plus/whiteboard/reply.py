"""Parse the agent's plain-text reply into cards and chat, as it streams.

The format the agent is told to use (one model call, no tools, no JSON escaping):

    @card chart G1 | Revenue by region, horizontal bars      kind = chart|table, parent = ID or -
    ```js
    ...body of render(el, rows, lib)...
    ```
    @fix G3 | Title                                          only when asked to fix a broken card
    ```js
    ...
    ```
    @say G5 horizontal bars, G6 stacked, G7 share.           the one chat line

Lenient on purpose: a code block with no header becomes an untitled chart card; a header with no code is
skipped with a note; any other text is passed on as chat; an unclosed last block is still accepted.
Events: {"kind": "card", "card_kind", "parent", "title", "code", "fix"} | {"kind": "text", "text"} |
{"kind": "note", "text"}.
"""
from __future__ import annotations

import re

CARD_RE = re.compile(r"^@card\b\s*(?P<kind>chart|table)?\s*(?P<parent>G\d+|-)?\s*\|?\s*(?P<title>.*)$", re.I)
FIX_RE = re.compile(r"^@fix\b\s*(?P<id>G\d+)\s*\|?\s*(?P<title>.*)$", re.I)
SAY_RE = re.compile(r"^@say\b:?\s*(?P<text>.*)$", re.I)
FENCE_RE = re.compile(r"^\s*```")


class ReplyParser:
    def __init__(self):
        self._buf = ""
        self._header: dict | None = None    # waiting for its code block
        self._code: list[str] | None = None  # inside a code block

    def feed(self, chunk: str) -> list[dict]:
        self._buf += chunk
        out: list[dict] = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            out.extend(self._line(line.rstrip("\r")))
        return out

    def finish(self) -> list[dict]:
        out: list[dict] = []
        if self._buf:
            line, self._buf = self._buf, ""
            out.extend(self._line(line.rstrip("\r")))
        if self._code is not None:   # the closing fence never came: keep what there is
            out.extend(self._close_block())
        elif self._header is not None:
            out.append(self._no_code())
        return out

    # ---- internals ---------------------------------------------------------------------------------
    def _line(self, line: str) -> list[dict]:
        if self._code is not None:
            if FENCE_RE.match(line) and line.strip().strip("`") == "":
                return self._close_block()
            self._code.append(line)
            return []
        if FENCE_RE.match(line):
            self._code = []
            return []
        stripped = line.strip()
        out: list[dict] = []
        m_card, m_fix, m_say = CARD_RE.match(stripped), FIX_RE.match(stripped), SAY_RE.match(stripped)
        if stripped and self._header is not None:
            out.append(self._no_code())      # a header that never got its code block
        if m_fix:
            self._header = {"card_kind": None, "parent": None, "title": m_fix["title"].strip(),
                            "fix": m_fix["id"].upper()}
        elif m_card:
            parent = (m_card["parent"] or "-").upper()
            self._header = {"card_kind": (m_card["kind"] or "chart").lower(),
                            "parent": None if parent == "-" else parent,
                            "title": m_card["title"].strip(), "fix": None}
        elif m_say:
            if m_say["text"].strip():
                out.append({"kind": "text", "text": m_say["text"].strip()})
        elif stripped:
            out.append({"kind": "text", "text": stripped})
        return out

    def _close_block(self) -> list[dict]:
        code = "\n".join(self._code or []).strip("\n")
        header = self._header or {"card_kind": "chart", "parent": None, "title": "", "fix": None}
        self._code, self._header = None, None
        if not code.strip():
            return [{"kind": "note", "text": f"A card ({header['title'] or 'untitled'}) came with empty code "
                                             "and was skipped."}]
        return [{"kind": "card", **header, "code": code}]

    def _no_code(self) -> dict:
        header, self._header = self._header, None
        return {"kind": "note", "text": f"A card ({header['title'] or 'untitled'}) came without code and was "
                                        "skipped."}


def parse(text: str) -> list[dict]:
    """Whole-reply convenience (tests)."""
    p = ReplyParser()
    return p.feed(text) + p.finish()
