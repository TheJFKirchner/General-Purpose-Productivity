"""Question files (<session folder>/questions/NNN-<slug>.md) and the per-session Auto answers switch (fake engine)."""
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


# ------------------------------------------------------------------ Auto answers
def test_auto_answers_planner_round_takes_the_recommendations_and_carries_on(harness):
    h = harness()
    seen = []
    fake.script(PLANNER, [[fake.ask(ROUND)], lambda m: seen.append(m) or [fake.say("Carrying on.")]])

    async def go():
        hub, c = await h.start()
        await _auto(hub)
        await hub.handle({"type": "user_message", "text": "a dashboard"})
        return hub, c

    hub, c = asyncio.run(go())
    assert c.of("auto_answers")[0]["on"] is True
    assert not c.of("question_round")                                             # no card
    lines = c.of("auto_answer")
    assert [(e["title"], e["answer"]) for e in lines] == [("Who uses it?", "Managers"), ("Which chart library?", "ECharts")]
    assert seen and "Managers" in seen[0] and "ECharts" in seen[0]                 # the planner got the answers
    assert [e["text"] for e in c.of("planner_message")] == ["Carrying on."]
    a, b = _files(hub)
    assert "Answered automatically (recommended)" in _text(a) and "Answered automatically (recommended)" in _text(b)
    assert "## Answer\nManagers" in _text(a)
    assert [e for e in hub.current.chat.history if e.get("type") == "auto_answer"] == lines


def test_auto_answers_builder_question_is_answered_at_once(harness):
    h = harness(timeout_s=5)
    _ask_step(rec="Blue", blocking=True)

    async def go():
        hub, c = await _run(h, auto=True)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert not c.of("queue_item")
    (line,) = c.of("auto_answer")
    assert line["title"] == "Colour?" and line["answer"] == "Blue" and line["agent"] == "Builder" and line["step"] == 1
    assert "recommendation was taken" in h.tool_results()[0][1]
    t = _text(_files(hub)[0])
    assert "Answered automatically (recommended)" in t and "## Answer\nBlue" in t
    assert "(answered automatically: Blue)" in c.of("run_finished")[0]["markdown"]


def test_question_without_a_recommendation_is_not_guessed(harness):
    h = harness(timeout_s=5)
    _ask_step(rec="", blocking=True)

    async def go():
        hub, c = await _run(h, auto=True)
        await h.wait(lambda: c.of("queue_item"))
        await asyncio.sleep(0.2)
        waiting = not c.of("run_finished") and not c.of("auto_answer")
        await hub.handle({"type": "queue_response", "id": c.of("queue_item")[0]["id"], "answer": "Red"})
        await h.wait(lambda: c.of("run_finished"))
        return hub, waiting

    hub, waiting = asyncio.run(go())
    assert waiting
    assert "Answered by the user" in _text(_files(hub)[0])


def test_planner_round_with_a_missing_recommendation_waits_as_a_card(harness):
    h = harness()
    fake.script(PLANNER, [[fake.ask([ROUND[0], {"id": "q2", "question": "Open one?", "why": "w"}])], [fake.say("ok")]])

    async def go():
        hub, c = await h.start()
        await _auto(hub)
        await hub.handle({"type": "user_message", "text": "x"})
        return hub, c

    hub, c = asyncio.run(go())
    assert len(c.of("question_round")) == 1 and not c.of("auto_answer") and not _files(hub)


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


def test_switching_on_answers_waiting_questions_and_a_waiting_round(harness):
    h = harness(timeout_s=5)
    _ask_step(rec="Blue", blocking=True)
    seen = []
    fake.script(PLANNER, [[fake.call("write_plan", ONE_STEP), fake.ask(ROUND)],
                          lambda m: seen.append(m) or [fake.say("Round answered.")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        assert len(c.of("question_round")) == 1                                   # waiting as a card
        await _auto(hub)                                                          # answers the round
        await h.wait(lambda: c.of("planner_message") and c.of("planner_message")[-1]["text"] == "Round answered.")
        await _auto(hub, False)                                                   # off again for the run
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("queue_item"))                                  # blocking question: waits
        await asyncio.sleep(0.1)
        assert not c.of("queue_resolved")
        await _auto(hub)                                                          # on again: answered now
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert seen and "Managers" in seen[0]
    done = c.of("queue_resolved")[0]
    assert done["by"] == "auto" and done["answer"] == "Blue"
    assert [e["title"] for e in c.of("auto_answer")] == ["Who uses it?", "Which chart library?", "Colour?"]
    assert len(_files(hub)) == 3 and all("automatically" in _text(p) for p in _files(hub))


def test_auto_answers_state_is_replayed_on_reconnect_and_off_by_default(harness):
    h = harness()
    fake.script(PLANNER, [[fake.ask(ROUND)], [fake.say("ok")]])

    async def go():
        hub, c = await h.start()
        assert hub.current.auto_answers is False
        assert c.of("snapshot")[0]["sessions"][0]["auto_answers"] is False
        await _auto(hub)
        await hub.handle({"type": "user_message", "text": "x"})
        late = Client(hub)
        await hub.connect(late)
        return late

    late = asyncio.run(go())
    s = late.of("snapshot")[0]["sessions"][0]
    assert s["auto_answers"] is True
    assert [e["type"] for e in s["chat"] if e.get("type")] == ["auto_answer", "auto_answer"]
