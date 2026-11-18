"""Fake-engine tests for the board and the agent session (zero tokens)."""
import asyncio
import json

import pytest
from agentlib import fake

from whiteboard.agent import AGENT_NAME, Designer, build_prompt
from whiteboard.board import Board
from whiteboard.data import load

BAR = "const c = lib.init(el); c.setOption({series: [{type: 'bar', data: rows.map(r => r.sales)}]});"
TABLE = "el.innerHTML = '<table></table>';"


def make(tmp_path, csv_file, library="echarts", out="out", references=None):
    board = Board(tmp_path / out, library)
    board.open()
    kw = {"references": references} if references else {}
    return board, Designer(board, load(csv_file), "Muted blues.", engine="fake", model=None, **kw)


def run(coro):
    return asyncio.run(coro)


async def collect(gen):
    return [ev async for ev in gen]


def card(title, code=BAR, **kw):
    return fake.call("add_card", {"title": title, "code": code, **kw})


def test_multi_card_request_gives_several_ids(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[fake.say("Three cards. "), card("Sales by region"), card("Sales by month"),
                              card("All rows", TABLE, kind="table"), fake.say("Done.")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        evs = await collect(d.chat("Show sales by region, sales by month, and a table of all rows."))
        await d.close()
        return evs

    evs = run(go())
    cards = [e for e in evs if e["type"] == "card"]
    assert [c["id"] for c in cards] == ["G1", "G2", "G3"]
    assert cards[2]["kind"] == "table" and cards[2]["library"] == "html"
    assert cards[0]["library"] == "echarts" and cards[0]["parent"] is None
    assert set(cards[0]) == {"type", "id", "parent", "title", "library", "kind", "code", "round"}
    assert [c["round"] for c in cards] == [1, 1, 1]                    # one message = one round
    streamed = "".join(e["text"] for e in evs if e["type"] == "text")
    assert "Three cards." in streamed and "Done." in streamed
    assert evs[-1]["type"] == "done" and evs[-1]["cards"] == ["G1", "G2", "G3"]
    assert set(evs[-1]) == {"type", "cards", "round", "usage", "model"}
    assert [c["id"] for c in board.snapshot()] == ["G1", "G2", "G3"] and board.next_id == 4
    assert list(board.out.iterdir()) == []                 # nothing on disk until something is saved


def test_iteration_records_parent_and_agent_sees_board(tmp_path, csv_file):
    seen = []
    fake.script(AGENT_NAME, [
        [card("Sales by region")],
        lambda msg: seen.append(msg) or [card("Region, stacked", parent="G1"), fake.say("G2 iterates on G1.")],
    ])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("Sales by region"))
        evs = await collect(d.chat("Try G1 stacked"))
        await d.close()
        return evs

    evs = run(go())
    new = [e for e in evs if e["type"] == "card"][0]
    assert new["id"] == "G2" and new["parent"] == "G1"
    assert board.get("G2")["parent"] == "G1"
    assert 'G1 "Sales by region"' in seen[0] and seen[0].endswith("Try G1 stacked")


def test_unknown_parent_is_refused_to_the_agent(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("Oops", parent="G9"), fake.say("ok")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        evs = await collect(d.chat("Try G9"))
        reply = d._session.last_reply
        await d.close()
        return evs, reply

    evs, reply = run(go())
    assert not [e for e in evs if e["type"] == "card"]
    assert reply.tool_calls[0].is_error and "G9 does not exist" in reply.tool_calls[0].result
    assert board.cards == []


def test_deleted_cards_are_reported_to_the_agent(tmp_path, csv_file):
    seen = []
    fake.script(AGENT_NAME, [[card("A"), card("B")], lambda msg: seen.append(msg) or [fake.say("ok")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("two charts"))
        board.delete("G1")
        await collect(d.chat("what is left?"))
        await d.close()

    run(go())
    assert "deleted G1" in seen[0] and 'G2 "B"' in seen[0] and '"A"' not in seen[0]


def test_save_writes_recipe_and_result(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("Sales by region"), card("All rows", TABLE, kind="table")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("chart and table"))
        await d.close()

    run(go())
    board.save("G1")
    board.save("G2")
    recipe = json.loads((board.out / "G1.json").read_text(encoding="utf-8"))
    assert recipe == {"id": "G1", "parent": None, "title": "Sales by region", "library": "echarts",
                      "kind": "chart", "code": BAR}
    result = json.loads(board.result_file.read_text(encoding="utf-8"))
    assert result["library"] == "echarts" and result["done"] is False
    assert [(s["id"], s["title"], s["library"]) for s in result["saved"]] == [
        ("G1", "Sales by region", "echarts"), ("G2", "All rows", "html")]
    board.delete("G2")  # deleting a saved card unsaves it
    assert not (board.out / "G2.json").exists()
    final = board.finish()
    assert final["done"] is True and [s["id"] for s in final["saved"]] == ["G1"]
    assert json.loads(board.result_file.read_text(encoding="utf-8"))["done"] is True




def test_chat_history_is_kept_in_memory_and_given_to_a_restarted_agent(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[fake.say("G1: sales by region."), card("Sales by region")],
                             [fake.fail("gateway down")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("sales by region please"))
        await collect(d.chat("and again"))    # the engine fails: the next turn starts a new agent session

    run(go())
    assert [m["role"] for m in board.chat] == ["user", "agent", "user"]
    assert board.chat[0]["text"] == "sales by region please"          # no board header in the visible chat
    assert board.chat[1]["text"] == "G1: sales by region."
    assert d._session is None
    prompt = d.make_agent().instructions
    assert "Conversation so far" in prompt and "- user: sales by region please" in prompt
    assert list(board.out.iterdir()) == []                            # the chat is never written to disk


def test_first_session_prompt_does_not_repeat_the_current_message(tmp_path, csv_file):
    prompts = []
    board, d = make(tmp_path, csv_file)
    real = d.make_agent

    def spy():
        a = real()
        prompts.append(a.instructions)
        return a

    d.make_agent = spy
    fake.script(AGENT_NAME, [[fake.say("hi")]])

    async def go():
        await collect(d.chat("first message"))
        await d.close()

    run(go())
    assert len(prompts) == 1 and "first message" not in prompts[0]


def test_unsave_keeps_the_card(tmp_path, csv_file):
    board = Board(tmp_path / "out", "echarts")
    board.open()
    board.add("A", BAR)
    board.save("G1")
    assert (board.out / "G1.json").exists()
    assert board.unsave("G1") == {"ok": True, "id": "G1", "saved": []}
    assert not (board.out / "G1.json").exists() and board.get("G1") is not None
    assert json.loads(board.result_file.read_text(encoding="utf-8"))["saved"] == []
    assert board.unsave("G1")["ok"]                                     # unsaving twice is harmless


def test_rounds_per_message_and_fix_keeps_round(tmp_path, csv_file):
    fake.script(AGENT_NAME, [
        [card("A"), card("B")],
        [card("C", parent="G1")],
        [fake.call("add_card", {"title": "A", "code": BAR, "replaces": "G1"})],
        [fake.say("nothing this time")],
    ])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("two"))
        evs = await collect(d.chat("iterate G1"))
        fixed = await d.fix("G1", "TypeError")
        last = await collect(d.chat("just talk"))
        await d.close()
        return evs, fixed, last

    evs, fixed, last = run(go())
    assert [e["round"] for e in evs if e["type"] == "card"] == [2] and evs[-1]["round"] == 2
    assert fixed["card"]["round"] == 1 and fixed["round"] == 2      # the fix keeps the card's round
    assert [(c["id"], c["round"]) for c in board.snapshot()] == [("G1", 1), ("G2", 1), ("G3", 2)]
    assert last[-1]["round"] == 3 and board.round == 3               # a message with no cards is a round too
    board.save("G1")
    assert "round" not in json.loads((board.out / "G1.json").read_text(encoding="utf-8"))


def test_usage_is_cumulative_over_chat_and_fix_turns(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("A")], [fake.call("add_card", {"title": "A", "code": BAR, "replaces": "G1"})]])
    board, d = make(tmp_path, csv_file)

    async def go():
        evs = await collect(d.chat("one chart"))
        fixed = await d.fix("G1", "TypeError")
        await d.close()
        return evs[-1], fixed

    done, fixed = run(go())
    u1, u2 = done["usage"], fixed["usage"]
    assert done["model"] == "fake engine" and fixed["model"] == "fake engine"
    assert u1["turns"] == 1 and u2["turns"] == 2
    for u in (u1, u2):
        assert u["total_tokens"] == (u["input_tokens"] + u["output_tokens"] + u["cache_read_tokens"]
                                     + u["cache_write_tokens"])
        assert u["cost_usd"] > 0
    assert u1["cache_write_tokens"] > 0 and u2["cache_read_tokens"] > 0   # prompt sent once, then cached
    assert u2["total_tokens"] > u1["total_tokens"] and u2["cost_usd"] > u1["cost_usd"]
    assert board.usage_view() == u2 and board.model == "fake engine"


def test_usage_passes_agentlib_numbers_through(tmp_path, csv_file):
    # The real-engine path: tokens and cost exactly as agentlib reports them per turn (Reply.usage,
    # Reply.cost_usd), including a turn that fails midway (AgentError.reply, cost unknown -> 0).
    fake.script(AGENT_NAME, [[fake.say("a")], [fake.say("b")], [fake.say("c"), fake.fail("gateway down")]])
    board, d = make(tmp_path, csv_file)
    d.estimate_usage = False
    reported = []
    real_record = d._record

    def spy(reply, message):
        if reply is not None:
            reported.append(reply)
        real_record(reply, message)

    d._record = spy

    async def go():
        for m in ("1", "2", "3"):
            await collect(d.chat(m))

    run(go())
    u = board.usage_view()
    assert len(reported) == 3 and u["turns"] == 3
    assert u["input_tokens"] == sum(r.usage.input_tokens for r in reported) > 0
    assert u["output_tokens"] == sum(r.usage.output_tokens for r in reported)
    assert u["cost_usd"] == pytest.approx(sum(r.cost_usd for r in reported)) and u["cost_usd"] > 0
    assert reported[2].cost_usd == 0                     # the failed turn: agentlib does not know its cost
    before = u["input_tokens"]
    board.add_usage({"input_tokens": 5}, None, None)    # an engine giving tokens but no cost
    assert board.usage_view()["cost_usd"] is None and board.usage_view()["input_tokens"] == before + 5


def test_current_visual_is_round_0_and_the_default_starting_point(tmp_path, csv_file):
    seen = []
    fake.script(AGENT_NAME, [lambda msg: seen.append(msg) or [card("Horizontal", parent="G1")]])
    board, d = make(tmp_path, csv_file)
    g1 = board.add("", BAR, "chart", card_id="G1", round=0)
    assert g1["title"] == "Current visual" and g1["round"] == 0
    prompt = d.make_agent().instructions
    assert "## The current visual: G1" in prompt
    assert "without naming an ID" in prompt and 'parent="G1"' in prompt

    async def go():
        evs = await collect(d.chat("make it horizontal"))
        await d.close()
        return evs

    evs = run(go())
    assert '"Current visual" (chart, the current visual)' in seen[0]
    new = [e for e in evs if e["type"] == "card"][0]
    assert (new["id"], new["parent"], new["round"]) == ("G2", "G1", 1)
    # Without --existing there is no current visual, and no such section.
    other, d2 = make(tmp_path, csv_file, out="other")
    assert "The current visual" not in d2.make_agent().instructions


def test_existing_recipe_without_title_gets_one(tmp_path):
    from whiteboard.cli import load_existing
    p = tmp_path / "current.json"
    p.write_text(json.dumps({"code": BAR, "title": "  "}), encoding="utf-8")
    assert load_existing(p, "echarts")["title"] == "Current visual"
    js = tmp_path / "current.js"
    js.write_text(BAR, encoding="utf-8")
    assert load_existing(js, "echarts")["title"] == "Current visual"






def test_card_error_goes_back_once_and_fix_keeps_id(tmp_path, csv_file):
    seen = []
    fixed_code = "const c = lib.init(el); c.setOption({});"
    fake.script(AGENT_NAME, [
        [card("Sales", "lib.oops(el);"), card("Other")],
        lambda msg: seen.append(msg) or [fake.call("add_card", {"title": "Sales", "code": fixed_code,
                                                                 "replaces": "G1"}), fake.say("Fixed G1.")],
        [fake.say("should never run")],
    ])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("two charts"))
        first = await d.fix("G1", "TypeError: lib.oops is not a function")
        second = await d.fix("G1", "TypeError again")
        await d.close()
        return first, second

    first, second = run(go())
    assert "TypeError: lib.oops is not a function" in seen[0] and 'replaces="G1"' in seen[0]
    assert first["ok"] and first["fixed"] and first["card"]["id"] == "G1"
    assert first["card"]["code"] == fixed_code and first["text"].strip() == "Fixed G1."
    assert [c["id"] for c in board.cards] == ["G1", "G2"] and board.get("G1")["code"] == fixed_code
    assert second["fixed"] is False and "already sent back once" in second["message"]
    assert board.next_id == 3


def test_replaces_without_error_report_is_refused(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("A")], [fake.call("add_card", {"title": "A2", "code": BAR, "replaces": "G1"})]])
    board, d = make(tmp_path, csv_file)

    async def go():
        await collect(d.chat("a"))
        await collect(d.chat("change G1"))
        reply = d._session.last_reply
        await d.close()
        return reply

    reply = run(go())
    assert reply.tool_calls[0].is_error and "parent=" in reply.tool_calls[0].result
    assert board.get("G1")["title"] == "A"


def test_prompt_holds_columns_samples_style_and_only_session_reference(tmp_path, csv_file):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "plotly.md").write_text("PLOTLY NOTES", encoding="utf-8")
    (refs / "echarts.md").write_text("ECHARTS NOTES", encoding="utf-8")
    (refs / "html.md").write_text("HTML TABLE NOTES", encoding="utf-8")
    table = load(csv_file)
    p = build_prompt("plotly", table, "Muted blues.", [], refs)
    assert "- sales (number)" in p and "- month (date)" in p and "- active (boolean)" in p
    assert '"region": "North"' in p and "Muted blues." in p
    assert "PLOTLY NOTES" in p and "HTML TABLE NOTES" in p and "ECHARTS NOTES" not in p
    # a missing reference file is tolerated
    p2 = build_prompt("d3", table, None, [], refs)
    assert "d3 library's global" in p2 and "HTML TABLE NOTES" in p2 and "Style note" not in p2


def test_engine_failure_becomes_error_event_and_session_restarts(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("A"), fake.fail("gateway down")]])
    board, d = make(tmp_path, csv_file)

    async def go():
        evs = await collect(d.chat("a"))
        return evs, d._session

    evs, session = run(go())
    assert [e["type"] for e in evs] == ["card", "error", "done"]
    assert "gateway down" in evs[1]["error"] and session is None


def test_output_folder_must_be_empty_or_missing(tmp_path):
    from whiteboard.board import OutputNotEmpty
    Board(tmp_path / "missing", "echarts").open()                     # missing: created
    assert (tmp_path / "missing").is_dir()
    (tmp_path / "empty").mkdir()
    Board(tmp_path / "empty", "echarts").open()                       # empty: fine
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.txt").write_text("x", encoding="utf-8")
    Board(tmp_path / "notes", "echarts").open()                       # no *.json: fine
    old = tmp_path / "old"
    old.mkdir()
    (old / "G2.json").write_text("{}", encoding="utf-8")
    (old / "result.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OutputNotEmpty, match="new, empty output folder"):
        Board(old, "echarts").open()
    assert (old / "G2.json").read_text(encoding="utf-8") == "{}"      # untouched


def test_result_has_no_board_path(tmp_path):
    board = Board(tmp_path / "out", "echarts")
    board.open()
    board.add("A", BAR)
    board.save("G1")
    result = board.finish(done=False)
    assert set(result) == {"library", "done", "saved"} and result["done"] is False
    assert sorted(p.name for p in board.out.iterdir()) == ["G1.json", "result.json"]


def test_saved_recipe_from_earlier_session_is_accepted_as_existing(tmp_path, csv_file):
    from whiteboard.cli import LaunchError, load_existing
    earlier = Board(tmp_path / "earlier", "echarts")
    earlier.open()
    earlier.add("Revenue by region", BAR)
    earlier.add("Revenue, stacked", BAR + " // stacked", parent="G1")
    earlier.save("G2")
    saved = tmp_path / "earlier" / "G2.json"
    before = saved.read_text(encoding="utf-8")

    existing = load_existing(saved, "echarts")
    assert existing == {"title": "Revenue, stacked", "kind": "chart", "code": BAR + " // stacked"}
    board = Board(tmp_path / "new", "echarts")
    board.open()
    g1 = board.add(existing["title"], existing["code"], existing["kind"], card_id="G1", round=0)
    assert (g1["id"], g1["round"], g1["parent"], g1["title"]) == ("G1", 0, None, "Revenue, stacked")
    assert saved.read_text(encoding="utf-8") == before                # the saved file is not changed
    with pytest.raises(LaunchError, match="made for library 'echarts'"):
        load_existing(saved, "plotly")
