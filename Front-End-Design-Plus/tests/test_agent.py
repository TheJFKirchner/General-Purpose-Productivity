"""Fake-engine tests for the board and the agent conversation (zero tokens)."""
import asyncio
import json

import pytest

from whiteboard.agent import Designer, build_prompt, prompt_parts
from whiteboard.board import Board
from whiteboard.data import load
from whiteboard.engine import EngineError, FakeEngine, TurnResult

BAR = "const c = lib.init(el); c.setOption({series: [{type: 'bar', data: rows.map(r => r.sales)}]});"
TABLE = "el.innerHTML = '<table></table>';"


def card(title, code=BAR, kind="chart", parent=None):
    return f"@card {kind} {parent or '-'} | {title}\n```js\n{code}\n```\n"


def fix(card_id, code, title="Fixed"):
    return f"@fix {card_id} | {title}\n```js\n{code}\n```\n"


def say(text):
    return f"@say {text}\n"


def make(tmp_path, csv_file, replies=None, library="echarts", out="out", references=None, engines=None):
    """A board and a Designer on the fake engine. `engines` (a list) collects every engine session opened."""
    board = Board(tmp_path / out, library)
    board.open()
    opened = engines if engines is not None else []

    def factory():
        eng = FakeEngine(replies)
        eng._turn = sum(e._turn for e in opened)      # a restarted session continues the script
        opened.append(eng)
        return eng

    kw = {"references": references} if references else {}
    d = Designer(board, load(csv_file), "Muted blues.", engine="fake", model=None, engine_factory=factory, **kw)
    return board, d, opened


def run(coro):
    return asyncio.run(coro)


async def collect(gen):
    return [ev async for ev in gen]


def chat_all(d, *messages):
    async def go():
        out = [await collect(d.chat(m)) for m in messages]
        await d.close()
        return out
    return run(go())


def test_multi_card_request_gives_several_ids(tmp_path, csv_file):
    reply = card("Sales by region") + card("Sales by month") + card("All rows", TABLE, "table") + say("G1 to G3.")
    board, d, engines = make(tmp_path, csv_file, [reply])
    (evs,) = chat_all(d, "Show sales by region, sales by month, and a table of all rows.")
    cards = [e for e in evs if e["type"] == "card"]
    assert [c["id"] for c in cards] == ["G1", "G2", "G3"]
    assert cards[2]["kind"] == "table" and cards[2]["library"] == "html"
    assert cards[0]["library"] == "echarts" and cards[0]["parent"] is None and cards[0]["code"] == BAR
    assert set(cards[0]) == {"type", "id", "parent", "title", "library", "kind", "code", "round"}
    assert [c["round"] for c in cards] == [1, 1, 1]
    assert "".join(e["text"] for e in evs if e["type"] == "text") == "G1 to G3."   # the code never reaches chat
    assert evs[-1]["type"] == "done" and evs[-1]["cards"] == ["G1", "G2", "G3"]
    assert set(evs[-1]) == {"type", "cards", "round", "usage", "model"}
    assert evs[-1]["usage"]["turns"] == 1 and len(engines) == 1
    assert list(board.out.iterdir()) == []                 # nothing on disk until something is saved


def test_iteration_records_parent_and_agent_sees_board_line(tmp_path, csv_file):
    board, d, engines = make(tmp_path, csv_file, [card("Sales by region"),
                                                  card("Region, stacked", parent="G1") + say("G2.")])
    _, evs = chat_all(d, "Sales by region", "Try G1 stacked")
    new = [e for e in evs if e["type"] == "card"][0]
    assert new["id"] == "G2" and new["parent"] == "G1" and board.get("G2")["parent"] == "G1"
    sent = engines[0].sent[1]
    assert sent.startswith('[Board: G1 "Sales by region". Next ID: G2.]') and sent.endswith("Try G1 stacked")
    assert BAR not in sent                                  # the board line carries IDs and titles only


def test_unknown_parent_keeps_the_card_without_parent(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, [card("Oops", parent="G9") + say("ok")])
    (evs,) = chat_all(d, "Try G9")
    new = [e for e in evs if e["type"] == "card"]
    assert [(c["id"], c["parent"]) for c in new] == [("G1", None)]


def test_deleted_cards_are_reported_to_the_agent(tmp_path, csv_file):
    board, d, engines = make(tmp_path, csv_file, [card("A") + card("B"), say("ok")])

    async def go():
        await collect(d.chat("two charts"))
        board.delete("G1")
        await collect(d.chat("what is left?"))
        await d.close()

    run(go())
    sent = engines[0].sent[1]
    assert "deleted G1" in sent and 'G2 "B"' in sent and '"A"' not in sent and "Next ID: G3" in sent


def test_save_writes_recipe_and_result(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, [card("Sales by region") + card("All rows", TABLE, "table")])
    chat_all(d, "chart and table")
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


def test_malformed_reply_is_shown_as_text_without_crashing(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, ["Sure! I would draw a bar chart of sales by region.\nAnything else?",
                                            "@card chart - | No code here\n@say done"])
    first, second = chat_all(d, "a chart", "another")
    assert [e["type"] for e in first] == ["text", "text", "done"] and board.cards == []
    assert "".join(e["text"] for e in first if e["type"] == "text") =="Sure! I would draw a bar chart of sales by region.\nAnything else?"
    texts = [e["text"] for e in second if e["type"] == "text"]
    assert "without code and was skipped" in texts[0] and texts[1].strip() == "done"
    assert board.chat[1]["text"].startswith("Sure!")


def test_chat_history_is_kept_in_memory_and_given_to_a_restarted_agent(tmp_path, csv_file):
    board, d, engines = make(tmp_path, csv_file, [card("Sales by region") + say("G1: sales by region."),
                                                  EngineError("gateway down"), say("back")])
    first, second, third = chat_all(d, "sales by region please", "and again", "hello?")
    assert [e["type"] for e in second] == ["error", "done"] and "gateway down" in second[0]["error"]
    assert [m["role"] for m in board.chat] == ["user", "agent", "user", "user", "agent"]
    assert board.chat[0]["text"] == "sales by region please"          # no board line in the visible chat
    assert len(engines) == 2                                           # the failure started a new session
    restarted = engines[1].system_prompt
    assert "Conversation so far" in restarted and "- user: sales by region please" in restarted
    assert "G1 | Sales by region" in restarted and BAR in restarted    # card code only after a restart
    assert BAR not in engines[0].system_prompt


def test_first_session_prompt_does_not_repeat_the_current_message(tmp_path, csv_file):
    board, d, engines = make(tmp_path, csv_file, [say("hi")])
    chat_all(d, "first message")
    assert "first message" not in engines[0].system_prompt


def test_unsave_keeps_the_card(tmp_path):
    board = Board(tmp_path / "out", "echarts")
    board.open()
    board.add("A", BAR)
    board.save("G1")
    assert board.unsave("G1") == {"ok": True, "id": "G1", "saved": []}
    assert not (board.out / "G1.json").exists() and board.get("G1") is not None
    assert json.loads(board.result_file.read_text(encoding="utf-8"))["saved"] == []
    assert board.unsave("G1")["ok"]


def test_rounds_per_message_and_fix_keeps_round(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, [card("A") + card("B"), card("C", parent="G1"),
                                            fix("G1", BAR + " "), say("nothing this time")])

    async def go():
        await collect(d.chat("two"))
        evs = await collect(d.chat("iterate G1"))
        fixed = await d.fix("G1", "TypeError")
        last = await collect(d.chat("just talk"))
        await d.close()
        return evs, fixed, last

    evs, fixed, last = run(go())
    assert [e["round"] for e in evs if e["type"] == "card"] == [2] and evs[-1]["round"] == 2
    assert fixed["card"]["round"] == 1 and fixed["round"] == 2
    assert [(c["id"], c["round"]) for c in board.snapshot()] == [("G1", 1), ("G2", 1), ("G3", 2)]
    assert last[-1]["round"] == 3 and board.round == 3
    board.save("G1")
    assert "round" not in json.loads((board.out / "G1.json").read_text(encoding="utf-8"))


def test_card_error_goes_back_once_and_fix_keeps_id(tmp_path, csv_file):
    fixed_code = "const c = lib.init(el); c.setOption({});"
    board, d, engines = make(tmp_path, csv_file, [card("Sales", "lib.oops(el);") + card("Other"),
                                                  fix("G1", fixed_code, "Sales") + say("Fixed G1."),
                                                  say("should never run")])

    async def go():
        await collect(d.chat("two charts"))
        first = await d.fix("G1", "TypeError: lib.oops is not a function")
        second = await d.fix("G1", "TypeError again")
        await d.close()
        return first, second

    first, second = run(go())
    sent = engines[0].sent[1]
    assert "TypeError: lib.oops is not a function" in sent and "@fix G1" in sent
    assert first["ok"] and first["fixed"] and first["card"]["id"] == "G1" and first["card"]["code"] == fixed_code
    assert first["text"].strip() == "Fixed G1."
    assert [c["id"] for c in board.cards] == ["G1", "G2"] and board.get("G1")["code"] == fixed_code
    assert second["fixed"] is False and "already sent back once" in second["message"]
    assert len(engines[0].sent) == 2


def test_fix_without_error_report_becomes_a_variant(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, [card("A"), fix("G1", BAR + "// v2", "A2")])
    chat_all(d, "a", "change G1")
    assert board.get("G1")["code"] == BAR and board.get("G2")["parent"] == "G1"


def test_usage_is_cumulative_over_chat_and_fix_turns(tmp_path, csv_file):
    board, d, _ = make(tmp_path, csv_file, [card("A"), fix("G1", BAR + " ")])

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
                                     + u["cache_write_tokens"]) and u["cost_usd"] > 0
    assert u1["cache_write_tokens"] > 0 and u2["cache_read_tokens"] > 0
    assert u2["total_tokens"] > u1["total_tokens"] and u2["cost_usd"] > u1["cost_usd"]


class StubEngine:
    """Reports fixed figures, like the real engine would per turn."""
    info = {"model": "stub"}

    def __init__(self, turns):
        self.turns = list(turns)

    async def start(self, prompt):
        pass

    async def send(self, message):
        t = self.turns.pop(0)
        if isinstance(t, EngineError):
            raise t
        yield t.text
        yield t

    async def close(self):
        pass


def test_usage_and_model_are_taken_as_the_engine_reports_them(tmp_path, csv_file):
    turns = [TurnResult(text=say("a"), usage={"input_tokens": 4, "output_tokens": 300, "cache_read_tokens": 0,
                                              "cache_write_tokens": 5000}, cost_usd=0.02, model="claude-x", api_calls=1),
             TurnResult(text=say("b"), usage={"input_tokens": 3, "output_tokens": 200, "cache_read_tokens": 5100,
                                              "cache_write_tokens": 90}, cost_usd=0.005, model="claude-x", api_calls=1),
             EngineError("died", TurnResult(usage={"input_tokens": 2, "output_tokens": 10, "cache_read_tokens": 0,
                                                   "cache_write_tokens": 0}, cost_usd=None))]
    board = Board(tmp_path / "out", "echarts")
    board.open()
    stub = StubEngine(turns)
    d = Designer(board, load(csv_file), engine="claude", model="sonnet", engine_factory=lambda: stub)
    assert d.model_name() == "sonnet"                      # before the first turn: the configured model
    chat_all(d, "1", "2", "3")
    u = board.usage_view()
    assert (u["input_tokens"], u["output_tokens"], u["cache_read_tokens"], u["cache_write_tokens"]) == (9, 510, 5100, 5090)
    assert u["turns"] == 3 and u["total_tokens"] == 9 + 510 + 5100 + 5090
    assert u["cost_usd"] is None                           # a turn without a cost makes the total unknown
    assert d.model_name() == "claude-x"


def test_current_visual_is_round_0_and_the_default_starting_point(tmp_path, csv_file):
    board, d, engines = make(tmp_path, csv_file, [card("Horizontal", parent="G1") + say("G2.")])
    g1 = board.add("", BAR, "chart", card_id="G1", round=0)
    assert g1["title"] == "Current visual" and g1["round"] == 0
    (evs,) = chat_all(d, "make it horizontal")
    prompt = engines[0].system_prompt
    assert "G1 is the deliverable's visual as it is today" in prompt and "parent G1" in prompt
    assert BAR in prompt                                   # its code is in the first prompt (it was not made here)
    assert '"Current visual" (current visual)' in engines[0].sent[0]
    new = [e for e in evs if e["type"] == "card"][0]
    assert (new["id"], new["parent"], new["round"]) == ("G2", "G1", 1)
    other, d2, engines2 = make(tmp_path, csv_file, out="other")
    chat_all(d2, "hi")
    assert "deliverable's visual" not in engines2[0].system_prompt


def test_existing_recipe_without_title_gets_one(tmp_path):
    from whiteboard.cli import load_existing
    p = tmp_path / "current.json"
    p.write_text(json.dumps({"code": BAR, "title": "  "}), encoding="utf-8")
    assert load_existing(p, "echarts")["title"] == "Current visual"
    js = tmp_path / "current.js"
    js.write_text(BAR, encoding="utf-8")
    assert load_existing(js, "echarts")["title"] == "Current visual"


def test_prompt_is_lean_and_holds_only_the_session_reference(tmp_path, csv_file):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "plotly.md").write_text("PLOTLY NOTES", encoding="utf-8")
    (refs / "echarts.md").write_text("ECHARTS NOTES", encoding="utf-8")
    (refs / "html.md").write_text("HTML TABLE NOTES", encoding="utf-8")
    table = load(csv_file)
    p = build_prompt("plotly", table, "Muted blues.", [], refs)
    assert "sales (number)" in p and "month (date)" in p and "active (boolean)" in p
    assert '{"region": "North"' in p and "Muted blues." in p
    assert "PLOTLY NOTES" in p and "ECHARTS NOTES" not in p
    assert "HTML TABLE NOTES" not in p and "header background" in p      # a few table lines, not html.md
    assert "@card" in p and "@say" in p and "No wrapper, imports, fetch or comments" in p
    names = [n for n, _ in prompt_parts("plotly", table, None, [], refs)]
    assert names == ["brief", "data", "plotly.md", "table_notes"]
    p_html = build_prompt("html", table, None, [], refs)
    assert "HTML TABLE NOTES" in p_html and "header background" not in p_html
    p_d3 = build_prompt("d3", table, None, [], refs)                    # a missing reference is tolerated
    assert "d3 library's global" in p_d3 and "Style note" not in p_d3


def test_output_folder_must_be_empty_or_missing(tmp_path):
    from whiteboard.board import OutputNotEmpty
    Board(tmp_path / "missing", "echarts").open()
    assert (tmp_path / "missing").is_dir()
    (tmp_path / "empty").mkdir()
    Board(tmp_path / "empty", "echarts").open()
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.txt").write_text("x", encoding="utf-8")
    Board(tmp_path / "notes", "echarts").open()
    old = tmp_path / "old"
    old.mkdir()
    (old / "G2.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OutputNotEmpty, match="new, empty output folder"):
        Board(old, "echarts").open()
    assert (old / "G2.json").read_text(encoding="utf-8") == "{}"


def test_result_has_no_board_path(tmp_path):
    board = Board(tmp_path / "out", "echarts")
    board.open()
    board.add("A", BAR)
    board.save("G1")
    result = board.finish(done=False)
    assert set(result) == {"library", "done", "saved"} and result["done"] is False
    assert sorted(p.name for p in board.out.iterdir()) == ["G1.json", "result.json"]


def test_saved_recipe_from_earlier_session_is_accepted_as_existing(tmp_path):
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
    assert (g1["id"], g1["round"], g1["parent"]) == ("G1", 0, None)
    assert saved.read_text(encoding="utf-8") == before
    with pytest.raises(LaunchError, match="made for library 'echarts'"):
        load_existing(saved, "plotly")
