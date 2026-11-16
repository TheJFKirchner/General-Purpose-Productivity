"""Visual sidecar on the fake engine: non-blocking tool, render + save, pick -> planner line, tweak, retry, limits."""
import asyncio

import pytest

from agentlib import fake

from app import demo
from app.agents.visualizer.visuals import MAX_HTML, VisualError, extract_html, validate
from conftest import Client

OPTIONS = ["Bar", "Stacked bar", "Line"]


def _planner(seen: list):
    fake.script("launchpad-planner", [
        [fake.call("show_visuals", {"brief": "Monthly trend", "options": OPTIONS}), fake.say("Options are on the way.")],
    ] + [lambda m: seen.append(m) or [fake.say("ok")]] * 5)


def _sets(c, sid=None):
    return [e for e in c.of("visual_set") if sid is None or e["session_id"] == sid]


def _wait_ready(h, c, n=3):
    return h.wait(lambda: _sets(c) and sum(o["status"] != "rendering" for o in _sets(c)[-1]["options"]) == n)


def test_tool_does_not_block_and_options_render_and_save(harness, project):
    h = harness()
    seen = []
    _planner(seen)
    fake.script("launchpad-visual", [demo.visual_turn])

    async def go():
        hub, c = await h.start()
        ls = hub.current
        ls.visuals.gate = asyncio.Event()                         # hold every render
        await hub.handle({"type": "user_message", "text": "which chart?"})
        # the planner's turn finished while all options were still rendering
        assert c.of("planner_message")[-1]["text"] == "Options are on the way."
        assert [o["status"] for o in _sets(c)[-1]["options"]] == ["rendering"] * 3
        ls.visuals.gate.set()
        await _wait_ready(h, c)
        return hub, c, ls

    hub, c, ls = asyncio.run(go())
    final = _sets(c)[-1]
    assert final["set_id"] == "v1" and final["brief"] == "Monthly trend" and final["picked_id"] is None
    assert [o["label"] for o in final["options"]] == OPTIONS
    for o in final["options"]:
        assert o["status"] == "ready" and "echarts.init" in o["html"]
        assert o["path"] == f".launchpad/{ls.id}/visuals/v1-{o['id']}.html"
        saved = (project / o["path"]).read_text(encoding="utf-8")
        assert o["html"] in saved and saved.startswith("<!-- Launchpad visual")
    usage = [e for e in c.of("agent_usage") if e["role"] == "visual"]
    assert len({e["agent_id"] for e in usage}) == 1 and usage[-1]["status"] == "idle" and usage[-1]["cost_usd"] > 0
    renders = [e for e in c.of("activity") if e["role"] == "visual" and e["status"] != "started"]
    assert len(renders) == 3 and all(e["tool"] == "render" and e["status"] == "done" for e in renders)
    tool_ack = [e for e in c.of("activity") if e["tool"] == "show_visuals" and e["status"] == "done"]
    assert tool_ack                                           # the planner's tool call itself is in the feed


def test_pick_reaches_planner_as_short_line_once(harness, project):
    h = harness()
    seen = []
    _planner(seen)
    fake.script("launchpad-visual", [demo.visual_turn])

    async def go():
        hub, c = await h.start()
        ls = hub.current
        await hub.handle({"type": "user_message", "text": "which chart?"})
        await _wait_ready(h, c)
        await hub.handle({"type": "user_message", "text": "no pick yet"})
        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": "v1", "option_id": "o2"})
        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": "v1", "option_id": "o3"})   # change
        await hub.handle({"type": "user_message", "text": "go on"})
        await hub.handle({"type": "user_message", "text": "and then"})
        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": "v1", "option_id": None})
        await hub.handle({"type": "user_message", "text": "after clearing"})
        return hub, c, ls

    hub, c, ls = asyncio.run(go())
    assert seen[0] == "no pick yet"                                            # nothing assumed without a pick
    path = f".launchpad/{ls.id}/visuals/v1-o3.html"
    assert seen[1] == f'[Launchpad] Visual pick: set v1 "Monthly trend" -> "Line" (saved: {path})\n\ngo on'
    assert "<" not in seen[1]                                                  # never HTML
    assert seen[2] == "and then"                                               # told once
    assert seen[3].startswith("[Launchpad] Visual pick cleared: set v1")
    assert _sets(c)[-1]["picked_id"] is None
    f = ls.folder
    assert 'picked "Line"' in f.read(f.decisions) and "v1-o3.html" in f.read(f.flight_log)
    assert ls.chat.history[-1] == {"role": "assistant", "text": "ok"}
    assert {"role": "user", "text": "go on"} in ls.chat.history               # chat history keeps the user's words


def test_tweak_revises_one_option_without_a_planner_turn(harness, project):
    h = harness()
    seen = []
    _planner(seen)
    got = []
    fake.script("launchpad-visual", [lambda m: got.append(m) or demo.visual_turn(m)])

    async def go():
        hub, c = await h.start()
        ls = hub.current
        await hub.handle({"type": "user_message", "text": "which chart?"})
        await _wait_ready(h, c)
        planner_usage = len([e for e in c.of("agent_usage") if e["role"] == "planner"])
        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": "v1", "option_id": "o1"})
        await hub.handle({"type": "visual_tweak", "session_id": ls.id, "set_id": "v1", "option_id": "o1",
                          "text": "same but horizontal"})
        await h.wait(lambda: _sets(c)[-1]["options"][0].get("path", "").endswith("-r2.html"))
        assert len([e for e in c.of("agent_usage") if e["role"] == "planner"]) == planner_usage
        await hub.handle({"type": "user_message", "text": "next"})
        return c, ls

    c, ls = asyncio.run(go())
    assert "Previous version:" in got[-1] and "Change requested: same but horizontal" in got[-1]
    o1, o2 = _sets(c)[-1]["options"][:2]
    assert "revised: same but horizontal" in o1["html"] and "revised" not in o2["html"]
    assert (ls.folder.project / f".launchpad/{ls.id}/visuals/v1-o1.html").is_file()      # first version kept
    assert seen[-1].startswith('[Launchpad] Visual pick: set v1 "Monthly trend" -> "Bar"') and "-r2.html" in seen[-1]
    assert len(got) == 4 and not seen[:-1]                                       # no planner turn for the tweak


def test_failed_option_can_be_retried(harness):
    h = harness()
    _planner([])
    calls = {"n": 0}

    def visual(msg):
        calls["n"] += 1
        if "Option to draw: Line" in msg and "rejected" not in msg:
            return [fake.say('```html\n<div><img src="https://example.com/x.png"></div>\n```')]
        return demo.visual_turn(msg)

    fake.script("launchpad-visual", [visual])

    async def go():
        hub, c = await h.start()
        ls = hub.current
        await hub.handle({"type": "user_message", "text": "which chart?"})
        await _wait_ready(h, c)
        failed = _sets(c)[-1]["options"][2]
        assert failed["status"] == "failed" and "outside URL" in failed["error"] and "html" not in failed
        await hub.handle({"type": "visual_pick", "session_id": ls.id, "set_id": "v1", "option_id": "o3"})
        await hub.handle({"type": "visual_retry", "session_id": ls.id, "set_id": "v1", "option_id": "o3"})
        await _wait_ready(h, c)
        return c

    c = asyncio.run(go())
    assert any("only a rendered option can be picked" in e["text"] for e in c.of("system"))
    line = _sets(c)[-1]["options"][2]
    assert line["status"] == "ready" and "error" not in line
    assert [e["status"] for e in c.of("activity") if e["role"] == "visual" and e["status"] != "started"].count("failed") == 1


@pytest.mark.parametrize("html,why", [
    ("x" * 10, "no HTML"),
    ("<div>" + "x" * MAX_HTML + "</div>", "too large"),
    ('<div><script src="echarts.min.js"></script></div>', "script tag with src"),
    ("<div style=\"background:url(//evil.example/a.png)\"></div>", "protocol-relative"),
    ("<div><script>fetch('/x')</script></div>", "network call"),
    ("<style>@import 'x.css';</style><div></div>", "@import"),
    ("<html><body>a</body></html><html><body>b</body></html>", "more than one document"),
    ('<div><a href="http://example.com">x</a></div>', "outside URL"),
])
def test_bad_output_is_rejected(html, why):
    with pytest.raises(VisualError, match=why):
        validate(extract_html(html))


def test_svg_namespace_and_fenced_reply_are_fine():
    html = extract_html('Here:\n```html\n<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>\n```\n')
    assert validate(html).startswith("<svg")


def test_snapshot_restores_sets(harness):
    h = harness()
    _planner([])
    fake.script("launchpad-visual", [demo.visual_turn])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "which chart?"})
        await _wait_ready(h, c)
        await hub.handle({"type": "visual_pick", "session_id": hub.current.id, "set_id": "v1", "option_id": "o2"})
        late = Client(hub)
        await hub.connect(late)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    s = next(x for x in late.events[0]["sessions"] if x["session_id"] == hub.current.id)
    live = {k: v for k, v in _sets(c)[-1].items() if k != "type"}
    assert s["visual_sets"] == [live] and live["picked_id"] == "o2"
