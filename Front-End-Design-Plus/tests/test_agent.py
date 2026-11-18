"""Fake-engine tests for the board and the agent session (zero tokens)."""
import asyncio
import json

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
    assert set(cards[0]) == {"type", "id", "parent", "title", "library", "kind", "code"}
    streamed = "".join(e["text"] for e in evs if e["type"] == "text")
    assert "Three cards." in streamed and "Done." in streamed
    assert evs[-1] == {"type": "done", "cards": ["G1", "G2", "G3"]}
    saved = json.loads(board.board_file.read_text(encoding="utf-8"))
    assert [c["id"] for c in saved["cards"]] == ["G1", "G2", "G3"] and saved["next_id"] == 4


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


def test_resume_from_board_json(tmp_path, csv_file):
    fake.script(AGENT_NAME, [[card("A"), card("B"), card("C", parent="G1")]])
    board, d = make(tmp_path, csv_file)

    async def go(designer, msg):
        evs = await collect(designer.chat(msg))
        await designer.close()
        return evs

    run(go(d, "three"))
    board.save("G1")
    board.delete("G3")

    fake.reset()
    fake.script(AGENT_NAME, [[card("D", parent="G2")]])
    board2, d2 = make(tmp_path, csv_file)
    assert board2.resumed and [c["id"] for c in board2.cards] == ["G1", "G2"]
    assert board2.saved == ["G1"]
    prompt = d2.make_agent().instructions
    assert "### G1: A" in prompt and BAR in prompt          # the agent sees the recipes it made before
    evs = run(go(d2, "try G2 again"))
    new = [e for e in evs if e["type"] == "card"][0]
    assert new["id"] == "G4" and new["parent"] == "G2"     # IDs never reused, even after a delete


def test_chat_history_is_kept_and_given_to_a_resumed_session(tmp_path, csv_file):
    seen = []
    fake.script(AGENT_NAME, [[fake.say("G1: sales by region."), card("Sales by region")],
                             lambda msg: seen.append(msg) or [fake.say("ok")]])
    board, d = make(tmp_path, csv_file)

    async def go(designer, msg):
        await collect(designer.chat(msg))
        await designer.close()

    run(go(d, "sales by region please"))
    assert [m["role"] for m in board.chat] == ["user", "agent"]
    assert board.chat[0]["text"] == "sales by region please"          # no board header in the visible chat
    assert board.chat[1]["text"] == "G1: sales by region."

    board2, d2 = make(tmp_path, csv_file)
    assert board2.chat == board.chat
    prompt = d2.make_agent().instructions
    assert "Conversation so far" in prompt and "- user: sales by region please" in prompt


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
    assert json.loads(board.board_file.read_text(encoding="utf-8"))["saved"] == []


def test_resume_refuses_other_library(tmp_path):
    Board(tmp_path / "out", "echarts").open()
    import pytest
    from whiteboard.board import BoardMismatch
    with pytest.raises(BoardMismatch, match="library 'echarts'"):
        Board(tmp_path / "out", "plotly").open()


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
