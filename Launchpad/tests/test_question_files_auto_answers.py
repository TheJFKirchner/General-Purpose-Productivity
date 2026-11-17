"""Question files (<session folder>/questions/NNN-<slug>.md) and the per-session Auto answers switch, which is for builders only (fake engine)."""
import asyncio
import re

from agentlib import fake

from app.sessionfiles import SessionFolder, question_slug
from conftest import PLAN, Client, report, script_orchestrator_sequential, script_planner_writes_plan

ONE_STEP = {**PLAN, "steps": PLAN["steps"][:1]}
PLANNER = "launchpad-planner"
ROUND = [{"id": "q1", "question": "Who uses it?", "why": "Sets the scope.", "recommended": "Managers",
          "options": ["Managers", "Analysts"]},
         {"id": "q2", "question": "Which chart library?", "why": "Decides the look.", "recommended": "ECharts"}]


def _files(hub):
    return sorted(hub.current.folder.questions.glob("*.md"))


def _text(path):
    return path.read_text(encoding="utf-8")


def _auto(hub, on=True):
    return hub.handle({"type": "set_auto_answers", "session_id": hub.current.id, "on": on})


def _ask_step(rec="Blue", blocking=False):
    script_planner_writes_plan(ONE_STEP)
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("ask_question", {"title": "Colour?", "body": "Pick one",
                                                                  "recommended": rec, "options": ["Blue", "Red"],
                                                                  "blocking": blocking}),
                                       fake.call("submit_report", report())]])


async def _run(h, *, auto=False):
    hub, c = await h.start()
    if auto:
        await _auto(hub)
    await hub.handle({"type": "user_message", "text": "go"})
    await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
    return hub, c


# ------------------------------------------------------------------ question files
def test_slug_is_safe_and_bounded():
    s = question_slug('Which "chart" library? <CON>:/\\ ' + "x" * 80)
    assert re.fullmatch(r"[a-z0-9-]+", s) and len(s) <= 40 and not s.startswith("-") and not s.endswith("-")
    assert question_slug("???") == "question"


def test_planner_round_writes_one_file_per_question(harness):
    h = harness()
    fake.script(PLANNER, [[fake.ask(ROUND)], [fake.say("Thanks.")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "a dashboard"})
        rnd = c.of("question_round")[-1]
        await hub.handle({"type": "round_answer", "roundId": rnd["id"],
                          "answers": {"q1": {"accepted": True}, "q2": {"accepted": False, "option": "D3", "text": "needs drill-down"}}})
        return hub

    hub = asyncio.run(go())
    a, b = _files(hub)
    assert a.name == "001-who-uses-it.md" and b.name == "002-which-chart-library.md"
    t = _text(a)
    for part in ("## Question", "Who uses it?", "## Asked by", "Planner", "## Options offered", "- Managers", "- Analysts",
                 "## Answer", "Managers", "## Justification", "Reason for asking: Sets the scope.",
                 "Recommended answer: Managers", "## How it was answered", "Answered by the user"):
        assert part in t
    assert "## Step" not in t and "## Run\nBefore launch" in t and "Run 1" not in t
    t2 = _text(b)
    assert "D3" in t2 and "Your note: needs drill-down" in t2 and "Recommended answer: ECharts" in t2
    assert "None (free answer)" in t2


def test_skipped_questions_get_no_file(harness):
    h = harness()
    fake.script(PLANNER, [[fake.ask(ROUND)], [fake.say("ok")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "x"})
        rnd = c.of("question_round")[-1]
        await hub.handle({"type": "round_answer", "roundId": rnd["id"], "skipped": True,
                          "answers": {"q1": {"accepted": True}}})
        return hub

    assert [p.name for p in _files(asyncio.run(go()))] == ["001-who-uses-it.md"]


def test_builder_question_file_report_link_and_step(harness):
    h = harness(timeout_s=5)
    _ask_step()
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Red"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    (f,) = _files(hub)
    t = _text(f)
    assert f.name == "001-colour.md" and "Builder" in t and "## Step\nStep 1" in t and "## Run\nA\n" in t and "Run 1" not in t
    assert "- Blue" in t and "- Red" in t and "## Answer\nRed" in t and "Reason for asking: Pick one" in t
    assert "Recommended answer: Blue" in t and "Answered by the user" in t
    md = c.of("run_finished")[0]["markdown"]
    assert "## Questions" in md and "[001-colour.md](questions/001-colour.md)" in md
    assert (hub.current.folder.path / "questions" / "001-colour.md").is_file()


def test_timed_out_question_is_saved_with_the_assumption(harness):
    h = harness(timeout_s=0.2)
    _ask_step()

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub

    hub = asyncio.run(go())
    t = _text(_files(hub)[0])
    assert "No answer (timed out)" in t and "Timed out" in t and "Assumption taken: Colour? -> Blue" in t
    assert "## Answer\nNo answer (timed out)" in t


def test_numbering_is_unique_and_continues_after_a_restart(project):
    f = SessionFolder(project, "20260101-000000-abcd")
    names = [f.add_question(title="Same title", asked_by="Builder", answer="a").name for _ in range(3)]
    assert names == ["001-same-title.md", "002-same-title.md", "003-same-title.md"]
    again = SessionFolder(project, "20260101-000000-abcd")                      # a new launch, same session folder
    assert again.add_question(title="Next", asked_by="CLI", answer="b").name == "004-next.md"
    (f.questions / "007-gap.md").write_text("x", encoding="utf-8")
    assert again.add_question(title="After gap", asked_by="CLI", answer="c").name == "008-after-gap.md"


def test_files_stay_in_questions_across_runs_and_the_report_lists_only_its_run(harness):
    h = harness(timeout_s=5)
    script_orchestrator_sequential(1)
    fake.script(PLANNER, [[fake.call("write_plan", ONE_STEP)], [fake.call("write_plan", {**ONE_STEP, "name": "Again"})]])
    titles = iter(["Colour?", "Size?"])                                              # one per builder session
    fake.script("launchpad-builder", [lambda m: [fake.call("ask_question", {"title": next(titles), "body": "b",
                                                                            "recommended": "Blue", "blocking": False}),
                                                  fake.call("submit_report", report())]] * 3)
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Red"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "user_message", "text": "again"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: len(c.of("run_finished")) == 2)
        return hub, c

    hub, c = asyncio.run(go())
    assert [p.name for p in _files(hub)] == ["001-colour.md", "002-size.md"]       # nothing moved into run-1/
    first = (hub.current.folder.path / "run-1" / "report.md").read_text(encoding="utf-8")
    assert "](../questions/001-colour.md)" in first and "002-size" not in first
    second = c.of("run_finished")[1]["markdown"]
    assert "](questions/002-size.md)" in second and "001-colour" not in second
    assert "## Run\nA (launch 2)" in _text(_files(hub)[1])


def test_cli_question_is_saved_in_the_chats_own_folder(harness):
    h = harness()
    q = {"question": "Which colour?", "header": "Colour", "options": [{"label": "Red"}, {"label": "Blue"}],
         "multiSelect": False}
    fake.script("launchpad-pilot", [[fake.call("AskUserQuestion", {"questions": [q]}), fake.say("Blue it is.")]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Blue"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "ask me"})
        return hub, cid

    hub, cid = asyncio.run(go())
    (f,) = list(hub.chats[cid].folder.questions.glob("*.md"))
    t = _text(f)
    assert f.name == "001-which-colour.md" and "CLI" in t and "## Answer\nBlue" in t and "Not part of a run" in t


# ------------------------------------------------------------------ Auto answers (builders only)
def _ask_two():
    script_planner_writes_plan(ONE_STEP)
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[
        fake.call("ask_question", {"title": "Colour?", "body": "Pick one", "recommended": "Blue",
                                   "options": ["Blue", "Red"], "blocking": True}),
        fake.call("ask_question", {"title": "Size?", "body": "How big", "recommended": "Small", "blocking": False}),
        fake.call("submit_report", report())]])


def test_auto_answers_builder_questions_blocking_or_not_take_the_recommendation_and_the_step_never_blocks(harness):
    h = harness(timeout_s=5)
    _ask_two()

    async def go():
        hub, c = await _run(h, auto=True)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert not c.of("queue_item") and not c.of("queue_resolved")                  # no card at all
    lines = c.of("auto_answer")
    assert [(e["title"], e["answer"], e["agent"], e["step"]) for e in lines] == [
        ("Colour?", "Blue", "Builder", 1), ("Size?", "Small", "Builder", 1)]
    assert "round_id" not in lines[0] and not [e for e in hub.current.chat.history if e.get("type") == "auto_answer"]
    assert all("recommendation was taken" in r[1] for r in h.tool_results()[:2])
    statuses = [e["status"] for e in c.of("step_update") if e["n"] == 1]
    assert "blocked" not in statuses and "in_progress" in statuses and statuses[-1] == "done"
    a, b = _files(hub)
    for f, ans in ((a, "Blue"), (b, "Small")):
        t = _text(f)
        assert "## How it was answered\nDecided by the Builder (Auto answers on)" in t and f"## Answer\n{ans}" in t
    md = c.of("run_finished")[0]["markdown"]
    assert "[001-colour.md](questions/001-colour.md)" in md and "decided by the agent, Auto answers on: Blue" in md


def test_an_empty_recommendation_or_reason_is_rejected_with_a_tool_error(harness):
    h = harness(timeout_s=5)
    script_planner_writes_plan(ONE_STEP)
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[
        fake.call("ask_question", {"title": "Colour?", "body": "Pick one", "recommended": "   ", "blocking": True}),
        fake.call("ask_question", {"title": "Colour?", "body": " ", "recommended": "Blue", "blocking": True}),
        fake.call("submit_report", report())]])

    async def go():
        hub, c = await _run(h, auto=True)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    first, second = h.tool_results()[:2]
    assert first[2] and "recommended is required" in first[1]
    assert second[2] and "body is required" in second[1]
    assert not c.of("queue_item") and not c.of("auto_answer") and not _files(hub)


def test_a_planner_round_is_never_auto_answered(harness):
    h = harness()
    fake.script(PLANNER, [[fake.ask(ROUND)], [fake.say("Thanks.")]])

    async def go():
        hub, c = await h.start()
        await _auto(hub)
        await hub.handle({"type": "user_message", "text": "a dashboard"})
        waiting = (len(c.of("question_round")), not c.of("auto_answer"), not c.of("planner_message"), not _files(hub))
        await hub.handle({"type": "round_answer", "roundId": c.of("question_round")[-1]["id"],
                          "answers": {"q1": {"accepted": True}, "q2": {"accepted": True}}})
        return hub, c, waiting

    hub, c, waiting = asyncio.run(go())
    assert waiting == (1, True, True, True)                                       # a card, nothing answered for the user
    assert not c.of("auto_answer") and [e["text"] for e in c.of("planner_message")] == ["Thanks."]
    assert all("Answered by the user" in _text(p) for p in _files(hub)) and len(_files(hub)) == 2


def test_a_cli_chat_question_is_never_auto_answered(harness):
    h = harness()
    q = {"question": "Which colour?", "header": "Colour", "options": [{"label": "Red"}, {"label": "Blue"}],
         "multiSelect": False}
    fake.script("launchpad-pilot", [[fake.call("AskUserQuestion", {"questions": [q]}), fake.say("Blue it is.")]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Blue"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await h.start()
        await _auto(hub)
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "ask me"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    (card,) = c.of("queue_item")
    assert card["chat_id"] == cid and not c.of("auto_answer")
    (f,) = list(hub.chats[cid].folder.questions.glob("*.md"))
    assert "Answered by the user" in _text(f)


def test_permission_cards_are_not_affected(harness):
    h = harness(timeout_s=5)
    script_planner_writes_plan(ONE_STEP)
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("Write", {"file_path": "../outside.md", "content": "x"}),
                                       fake.call("submit_report", report())]])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "deny"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h, auto=True)
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    cards = c.of("queue_item")
    assert cards and cards[0]["kind"] == "permission" and not c.of("auto_answer")
    assert c.of("queue_resolved")[0]["by"] == "user"


def test_switching_on_answers_a_waiting_builder_question(harness):
    h = harness(timeout_s=5)
    _ask_step(rec="Blue", blocking=True)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("queue_item"))                                  # blocking question: waits
        await asyncio.sleep(0.1)
        assert not c.of("queue_resolved") and not c.of("run_finished")
        await _auto(hub)                                                          # on now: answered now
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    done = c.of("queue_resolved")[0]
    assert done["by"] == "auto" and done["answer"] == "Blue"
    assert [e["title"] for e in c.of("auto_answer")] == ["Colour?"]
    statuses = [e["status"] for e in c.of("step_update") if e["n"] == 1]
    assert "blocked" in statuses and statuses[-1] == "done"                       # it really waited, then carried on
    assert "Decided by the Builder (Auto answers on)" in _text(_files(hub)[0])


def test_auto_answers_state_and_lines_are_replayed_on_reconnect_and_off_by_default(harness):
    h = harness(timeout_s=5)
    _ask_step(rec="Blue", blocking=True)

    async def go():
        hub, c = await h.start()
        assert hub.current.auto_answers is False
        assert c.of("snapshot")[0]["sessions"][0]["auto_answers"] is False
        await _auto(hub)
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        late = Client(hub)
        await hub.connect(late)
        return late

    late = asyncio.run(go())
    s = late.of("snapshot")[0]["sessions"][0]
    assert s["auto_answers"] is True
    assert not [e for e in s["chat"] if e.get("type") == "auto_answer"]          # never in the planner chat
    assert [e["title"] for e in late.of("auto_answer")] == ["Colour?"]            # replayed beside Incoming's cards
