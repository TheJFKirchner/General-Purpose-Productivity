"""Visual sidecar: the planner asks a cheap, tool-free agent (Visualizer) to draw quick visual / design options.

- Planner tool show_visuals(brief, options, library?) creates a set and returns an acknowledgement at once; each
  option renders in the background (one one-shot agent call per option, in parallel), so the planner is never blocked
- Any visual or design question: charts, colour palettes, hero cards, layouts, tiles, type
- Libraries (one per set; app/agents/visualizer/libraries.py): not given = ECharts. Always available (vendored in app/vendor/): ECharts, Chart.js, D3.
  Available when installed: Plotly, Bokeh, found as their bundled JavaScript file inside the installed Python
  package (the connected folder's .venv first, then Launchpad's own environment); never imported or run as Python.
  Anything else (unavailable, or no browser build: matplotlib, seaborn, Recharts ...) is drawn in ECharts and
  labelled "drawn in ECharts, styled like <library>"
- The planner never sees HTML: a user's pick reaches it with their next message as one short line
  (set, option label, saved path); no pick -> nothing is said or assumed
- The user can tweak one option ("same but horizontal") or retry a failed one; both go straight to the visual
  agent with no planner turn
- Output is extracted, size-capped and validated in code (one fragment per option, no outside URLs, no
  script tags with src, no network calls, no other library than the set's); every rendered version is saved under
  <session folder>/visuals/<set>-<option>[-rN].html; a pick is written to the session's decisions.md and its
  file to the flight log (builders get the exact approved look)
- The library is a page-provided global (`echarts`, `Chart`, `d3`, `Plotly`, `Bokeh`): the page fetches it from
  GET /vendor/lib/<key>.js and inlines it into the sealed frame; the agent must never load it
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from agentlib import AgentError
from agentlib.events import Done

from ...meter import Meter
from ...sessionfiles import one_line
from .. import crew
from .libraries import DEFAULT_LIBRARY, LIB_USE, LIBRARIES, LibraryChoice, choose_library

MAX_OPTIONS = 4
MAX_HTML = 40_000                      # characters per option
MAX_LABEL = 60

_FENCE = re.compile(r"```(?:html|HTML)?[ \t]*\r?\n(.*?)```", re.S)
_NAMESPACES = re.compile(r"https?://www\.w3\.org/(?:2000/svg|1999/xlink|1999/xhtml)")
_OUTSIDE = [
    (re.compile(r"(?i)\b(?:https?|ftp|wss?|file):"), "an outside URL"),
    (re.compile(r"(?i)(?:src|href|action|poster|data|srcset)\s*=\s*['\"]?\s*//"), "a protocol-relative URL"),
    (re.compile(r"(?i)url\(\s*['\"]?\s*//"), "a protocol-relative URL"),
    (re.compile(r"(?i)@import"), "a CSS @import"),
    (re.compile(r"(?i)<script[^>]*\bsrc\s*="), "a script tag with src (the library is provided; load nothing)"),
    (re.compile(r"(?i)<(?:iframe|object|embed|link|base|form|frame)\b"), "an embedding or link tag"),
    (re.compile(r"(?i)<meta[^>]*http-equiv"), "a meta http-equiv tag"),
    (re.compile(r"(?i)\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts)\b|\bimport\s*\("),
     "a network call"),
    (re.compile(r"\bd3\s*\.\s*(?:csv|tsv|json|text|xml|html|svg|image|dsv|buffer|blob)\s*\("), "a network call"),
]


class VisualError(ValueError):
    """The agent's output was not a usable visual (message says why)."""


def extract_html(text: str) -> str:
    """The agent's reply -> the HTML fragment (from a ```html block, else the reply if it is HTML)."""
    m = _FENCE.search(text or "")
    html = (m.group(1) if m else (text or "")).strip()
    if not html.startswith("<"):
        raise VisualError("the reply contained no HTML")
    return html


def validate(html: str, drawn_with: str | None = None) -> str:
    """Checks one fragment; drawn_with (a library key) = it may only call that library."""
    html = (html or "").strip()
    if not html:
        raise VisualError("empty visual")
    if len(html) > MAX_HTML:
        raise VisualError(f"too large ({len(html):,} characters; max {MAX_HTML:,})")
    if len(re.findall(r"(?i)<html\b", html)) > 1 or len(_FENCE.findall(html + "\n")) > 0:
        raise VisualError("more than one document")
    probe = _NAMESPACES.sub("", html)
    for rx, what in _OUTSIDE:
        m = rx.search(probe)
        if m:
            raise VisualError(f"references {what} ({one_line(m.group(0), 40)})")
    if drawn_with in LIBRARIES:
        for key, rx in LIB_USE.items():
            if key != drawn_with and rx.search(html):
                raise VisualError(f"uses {LIBRARIES[key].name}, but this option is drawn with "
                                  f"{LIBRARIES[drawn_with].name} (only that library is loaded)")
    return html


@dataclass
class Option:
    id: str
    label: str
    status: str = "rendering"           # rendering | ready | failed
    html: str | None = None
    error: str | None = None
    path: str | None = None
    revision: int = 0
    secs: float | None = None           # how long the last render took

    def to_dict(self) -> dict:
        d = {"id": self.id, "label": self.label, "status": self.status}
        if self.status == "ready" and self.html is not None:
            d["html"] = self.html
        if self.error:
            d["error"] = self.error
        if self.path:
            d["path"] = self.path
        return d


@dataclass
class VisualSet:
    session_id: str
    id: str
    brief: str
    options: list[Option] = field(default_factory=list)
    picked_id: str | None = None
    told_pick: str | None = None        # the pick the planner was last told about (option id or None)
    lib: LibraryChoice = field(default_factory=lambda: LibraryChoice(None, DEFAULT_LIBRARY, (DEFAULT_LIBRARY,), None))

    def event(self) -> dict:
        lib = self.lib
        return {"type": "visual_set", "session_id": self.session_id, "set_id": self.id, "brief": self.brief,
                "options": [dict(o.to_dict(), drawn_with=lib.drawn_with) for o in self.options],
                "picked_id": self.picked_id, "library": lib.asked, "drawn_with": lib.drawn_with,
                "libraries": list(lib.available), "library_note": lib.note}

    def option(self, option_id) -> Option:
        for o in self.options:
            if o.id == option_id:
                return o
        raise ValueError(f"no option {option_id} in set {self.id}")


class VisualBoard:
    """All visual sets of one Launchpad session."""

    def __init__(self, ls):
        self.ls, self.hub, self.folder = ls, ls.hub, ls.folder
        self.sets: dict[str, VisualSet] = {}
        self.meter: Meter | None = None
        self.active = 0
        self.tasks: set[asyncio.Task] = set()
        self.notes: dict[str, str] = {}             # set id -> line for the planner's next user message
        self.gate: asyncio.Event | None = None      # tests only: hold renders until set

    # ---------------------------------------------------------------- planner tool
    async def create(self, brief: str, labels: list[str], library: str | None = None) -> str:
        brief = one_line(brief, 200)
        if isinstance(labels, str):
            labels = [labels]
        labels = [one_line(x, MAX_LABEL) for x in (labels or []) if str(x).strip()]
        if not brief:
            raise ValueError("give a one-line brief of what to draw")
        if not 1 <= len(labels) <= MAX_OPTIONS:
            raise ValueError(f"give 1-{MAX_OPTIONS} option labels")
        lib = choose_library(library, self.folder.project)
        vset = VisualSet(self.ls.id, f"v{len(self.sets) + 1}", brief,
                         [Option(f"o{i}", label) for i, label in enumerate(labels, 1)], lib=lib)
        self.sets[vset.id] = vset
        await self.hub.emit(vset.event())
        for opt in vset.options:
            self._spawn(vset, opt, self._first_message(vset, opt))
        used = LIBRARIES[lib.drawn_with].name
        if lib.note:
            how = (f" {lib.styled_like} is not available here, so they are {lib.note} (available: "
                   + ", ".join(LIBRARIES[k].name for k in lib.available) + ").")
        else:
            how = f" Charts are drawn with {used}."
        return (f"Showing {len(labels)} option(s) as visual set {vset.id} in the panel beside the chat; they are "
                f"rendering now.{how} Do not describe them. The user's pick, if they make one, arrives with their "
                "next message; until then assume nothing.")

    # ---------------------------------------------------------------- UI actions
    async def tweak(self, set_id: str, option_id: str, text: str) -> None:
        vset = self._set(set_id)
        opt = vset.option(option_id)
        text = one_line(text, 300)
        if not text:
            raise ValueError("say what to change")
        if opt.status == "rendering":
            raise ValueError("that option is still rendering")
        msg = (self._revise_message(vset, opt, text) if opt.html else
               self._first_message(vset, opt) + f"\nAlso apply this change: {text}")
        self._spawn(vset, opt, msg)

    async def retry(self, set_id: str, option_id: str) -> None:
        vset = self._set(set_id)
        opt = vset.option(option_id)
        if opt.status == "rendering":
            raise ValueError("that option is still rendering")
        extra = f"\nThe previous attempt was rejected: {opt.error}. Avoid that." if opt.error else ""
        self._spawn(vset, opt, self._first_message(vset, opt) + extra)

    async def pick(self, set_id: str, option_id: str | None) -> None:
        vset = self._set(set_id)
        if option_id is None:
            vset.picked_id = None
            if vset.told_pick is None:
                self.notes.pop(vset.id, None)
            else:
                self.notes[vset.id] = f"[Launchpad] Visual pick cleared: set {vset.id} \"{vset.brief}\" (no option chosen)."
            await self.hub.emit(vset.event())
            return
        opt = vset.option(option_id)
        if opt.status != "ready" or not opt.path:
            raise ValueError("only a rendered option can be picked")
        vset.picked_id = opt.id
        self._record_pick(vset, opt)
        await self.hub.emit(vset.event())

    def take_notes(self) -> str:
        """Lines for the planner's next user message (then forgotten)."""
        if not self.notes:
            return ""
        lines = list(self.notes.values())
        for vset in self.sets.values():
            if vset.id in self.notes:
                vset.told_pick = vset.picked_id
        self.notes.clear()
        return "\n".join(lines) + "\n\n"

    def snapshot(self) -> list[dict]:
        return [{k: v for k, v in s.event().items() if k != "type"} for s in self.sets.values()]

    async def close(self) -> None:
        for t in list(self.tasks):
            t.cancel()

    # ---------------------------------------------------------------- internals
    def _set(self, set_id: str) -> VisualSet:
        vset = self.sets.get(str(set_id))
        if vset is None:
            raise ValueError(f"no visual set {set_id}")
        return vset

    def _record_pick(self, vset: VisualSet, opt: Option) -> None:
        self.folder.add_decision(f"Visual set {vset.id} \"{vset.brief}\": picked \"{opt.label}\" ({opt.path})")
        self.folder.add_flight_log(opt.path, f"Approved look for \"{one_line(vset.brief, 120)}\": {opt.label}",
                                   source="visual pick")
        self.notes[vset.id] = (f"[Launchpad] Visual pick: set {vset.id} \"{vset.brief}\" -> \"{opt.label}\" "
                               f"(saved: {opt.path})")

    @staticmethod
    def _library_line(vset: VisualSet) -> str:
        """What the visual agent may draw charts with (it never loads anything itself)."""
        lib = LIBRARIES[vset.lib.drawn_with]
        line = f"Library: {lib.name} (global `{lib.glob}`, already loaded)"
        if vset.lib.styled_like:
            line += f", styled like {vset.lib.styled_like}: copy {vset.lib.styled_like}'s look in {lib.name}"
        return line + ". Plain HTML/CSS for anything that is not a chart."

    @classmethod
    def _first_message(cls, vset: VisualSet, opt: Option) -> str:
        others = [o.label for o in vset.options if o.id != opt.id]
        return (f"Brief: {vset.brief}\nOption to draw: {opt.label}\n{cls._library_line(vset)}"
                + (f"\nOther options in this set (do not draw them): {', '.join(others)}" if others else ""))

    @classmethod
    def _revise_message(cls, vset: VisualSet, opt: Option, text: str) -> str:
        return (f"Brief: {vset.brief}\nOption: {opt.label}\n{cls._library_line(vset)}\nPrevious version:\n"
                f"```html\n{opt.html}\n```\nChange requested: {text}")

    def _spawn(self, vset: VisualSet, opt: Option, message: str) -> None:
        opt.status, opt.error = "rendering", None
        t = asyncio.get_running_loop().create_task(self._render(vset, opt, message))
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)

    async def _render(self, vset: VisualSet, opt: Option, message: str) -> None:
        hub, s = self.hub, self.hub.settings
        if self.meter is None:                      # one visual agent per session: working while any option renders
            self.meter = Meter(hub, session_id=self.ls.id, role="visual", name=crew.display("visual"))
        meter = self.meter
        await hub.emit(vset.event())
        self.active += 1
        await meter.set_status("working")
        act = await meter.activity_begin("render", f"{vset.id}/{opt.id} {opt.label}: {vset.brief}")
        loop = asyncio.get_running_loop()
        t0, status = loop.time(), "failed"
        try:
            if self.gate is not None:
                await self.gate.wait()
            agent = crew.load("visual", engine=s.engine, project=self.folder.project, model=s.visual_model,
                              save_conversation=False,
                              **crew.session_kw(self.ls, crew.builtin_name("visual"), role="visual"))
            await hub.give_mcp(agent, who=crew.display("visual"), session_id=self.ls.id)

            reply = None
            async with agent.session() as sess:
                async for ev in sess.stream(message):
                    await meter.feed(ev)
                    if isinstance(ev, Done):
                        reply = ev.reply
            if reply is None or reply.status == "error":
                raise VisualError(f"the visual agent stopped: {getattr(reply, 'error', 'no reply')}")
            html = validate(extract_html(reply.text), vset.lib.drawn_with)
            opt.revision += 1
            opt.html, opt.status = html, "ready"
            opt.path = self._save(vset, opt)
            status = "done"
            if vset.picked_id == opt.id:            # a picked option was revised: tell the planner the new file
                self._record_pick(vset, opt)
        except (VisualError, AgentError) as e:
            opt.status = "failed"
            opt.error = getattr(e, "short", None) or str(e)
        except asyncio.CancelledError:
            opt.status, opt.error = "failed", "stopped"
            raise
        finally:
            opt.secs = round(loop.time() - t0, 1)
            self.active -= 1
            await meter.activity_end(act, status)
            if self.active == 0:
                await meter.set_status("idle")
            await hub.emit(vset.event())

    def _save(self, vset: VisualSet, opt: Option) -> str:
        d = self.folder.ensure() / "visuals"
        d.mkdir(exist_ok=True)
        name = f"{vset.id}-{opt.id}" + (f"-r{opt.revision}" if opt.revision > 1 else "") + ".html"
        lib = LIBRARIES[vset.lib.drawn_with]
        source = (f"app/vendor/{lib.files[0]}" if lib.bundled else
                  f"the {lib.package} Python package's {lib.files[0]}")
        styled = f", {vset.lib.note}" if vset.lib.note else ""
        inner = (f"Launchpad visual {vset.id}/{opt.id} \"{opt.label}\" rev {opt.revision}; brief: {vset.brief}. "
                 f"Made-up sample data. Charts need {lib.name} as the global `{lib.glob}` (Launchpad serves "
                 f"{source}){styled}.")
        head = "<!-- " + inner.replace("--", "- -") + " -->\n"
        p = d / name
        p.write_text(head + opt.html + "\n", encoding="utf-8", newline="\n")
        return self.folder.rel(p)
