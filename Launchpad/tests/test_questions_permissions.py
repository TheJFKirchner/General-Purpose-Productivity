"""Builder questions (timed / blocking) and the write / shell guards."""
import asyncio

import pytest

from agentlib import fake

from app.agents.builder.deny import deny_match
from conftest import Client, PLAN, report, script_orchestrator_sequential, script_planner_writes_plan

ONE_STEP = {**PLAN, "steps": PLAN["steps"][:1]}


def _setup(builder_steps):
    script_planner_writes_plan(ONE_STEP)
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [builder_steps])


async def _run(h):
    hub, c = await h.start()
    await hub.handle({"type": "user_message", "text": "go"})
    await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
    return hub, c


def test_timed_question_auto_answers_and_logs_assumption(harness):
    h = harness(timeout_s=0.3)
    _setup([fake.call("ask_question", {"title": "Colour?", "body": "Pick one", "recommended": "Blue",
                                       "options": ["Blue", "Red"], "blocking": False}),
            fake.call("submit_report", report())])

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    item = c.of("queue_item")[0]
    assert item["kind"] == "question" and item["blocking"] is False and item["timeout_s"] == 0.3
    assert item["expires_at"] and item["rec"] == "Blue" and item["options"] == ["Blue", "Red"]
    assert c.of("queue_resolved")[0] == {"type": "queue_resolved", "id": item["id"], "answer": "Blue", "by": "timer"}
    name, text, err = h.tool_results()[0]
    assert name == "ask_question" and not err and "Proceed on your recommendation: Blue" in text
    f = hub.current.folder
    assert "Colour? -> Blue" in f.read(f.assumptions) and "timer" in f.read(f.assumptions)
    assert "Colour? -> Blue" in f.read(f.report)
    assert not [e for e in c.of("step_update") if e["status"] == "blocked"]      # timed questions do not block


def test_timed_question_answered_by_user(harness):
    h = harness(timeout_s=5)
    _setup([fake.call("ask_question", {"title": "Colour?", "body": "b", "recommended": "Blue"}),
            fake.call("submit_report", report())])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "answer": "Red"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert c.of("queue_resolved")[0]["by"] == "user" and "The user answered: Red" in h.tool_results()[0][1]
    assert "Colour?" not in hub.current.folder.read(hub.current.folder.assumptions)


def test_blocking_question_pauses_run_until_answered(harness):
    h = harness(timeout_s=0.1)
    _setup([fake.call("ask_question", {"title": "Delete old data?", "body": "b", "recommended": "No",
                                       "blocking": True}),
            fake.call("submit_report", report())])

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("queue_item"))
        item = c.of("queue_item")[0]
        assert item["blocking"] is True and item["timeout_s"] is None and item["expires_at"] is None
        await asyncio.sleep(0.5)                                   # well past the timed-question timeout
        assert not c.of("run_finished") and not c.of("queue_resolved")
        assert c.of("step_update")[-1]["status"] == "blocked"
        await hub.handle({"type": "queue_response", "id": item["id"], "answer": "Yes"})
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    assert c.of("queue_resolved")[0]["by"] == "user"
    assert "The user answered: Yes" in h.tool_results()[0][1]
    assert c.of("run_finished")[0]["status"] == "done"


def test_writes_outside_the_project_raise_a_card(harness):
    """Inside the project: no card. Outside / .launchpad/ / .git/: a timed card the user can allow or deny."""
    answers = {"../escape.txt": "allow", ".launchpad/sneaky.md": "deny"}
    h = harness(responder=lambda ev: ({"type": "queue_response", "id": ev["id"],
                                       "decision": answers.get(ev["body"], "deny")}
                                      if ev.get("type") == "queue_item" else None))
    _setup([fake.call("Write", {"file_path": "out/ok.txt", "content": "x"}),
            fake.call("Edit", {"file_path": "app/main.py", "old_string": "a", "new_string": "b"}),
            fake.call("Write", {"file_path": "../escape.txt", "content": "x"}),
            fake.call("Write", {"file_path": ".launchpad/sneaky.md", "content": "x"}),
            fake.call("submit_report", report())])

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    cards = c.of("queue_item")
    assert [(x["title"], x["body"], x["timeout_s"]) for x in cards] == [
        ("Write outside the project folder", "../escape.txt", 180),
        ("Write inside .launchpad/ (session records)", ".launchpad/sneaky.md", 180)]
    results = h.tool_results()[:4]
    assert [err for _, _, err in results] == [False, False, False, True]
    assert "The user denied this request" in results[3][1]
    step = hub.current.folder.read(hub.current.folder.step_path(1))
    assert "User denied: Write inside .launchpad/ (session records): .launchpad/sneaky.md" in step


def test_unanswered_permission_card_is_denied_by_the_timer(harness):
    h = harness(permission_timeout_s=0.3)
    _setup([fake.call("Bash", {"command": "pip install requests"}), fake.call("submit_report", report())])

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    card = c.of("queue_item")[0]
    assert card["timeout_s"] == 0.3 and card["expires_at"] and card["blocking"] is False
    assert c.of("queue_resolved")[0] == {"type": "queue_resolved", "id": card["id"], "answer": "deny", "by": "timer"}
    name, text, err = h.tool_results()[0]
    assert err and "Nobody answered this permission request within 0 seconds" in text
    rep = c.of("run_finished")[0]["markdown"]
    assert "Permission request denied after 0s with no answer: Bash · package install: pip install requests" in rep


def test_autopilot_approves_everything_and_logs_it(harness, project):
    h = harness(autopilot=True)
    _setup([fake.call("Bash", {"command": "git push origin main"}),
            fake.call("Write", {"file_path": "../outside.txt", "content": "x"}),
            fake.call("Write", {"file_path": "inside.txt", "content": "x"}),
            fake.call("submit_report", report())])

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return hub, c

    hub, c = asyncio.run(go())
    assert not c.of("queue_item")                                         # no cards at all
    assert [err for _, _, err in h.tool_results()[:3]] == [False, False, False]
    assert c.of("run_started")[0]["autopilot"] is True
    autos = [e for e in c.of("activity") if e.get("auto")]
    assert [(e["tool"], e["status"]) for e in autos] == [("Bash", "done"), ("Write", "done")]   # inside write: not "auto"
    rep = c.of("run_finished")[0]["markdown"]
    assert "## Approved by autopilot (no card shown)" in rep
    assert "Step 1: Bash · git push: git push origin main" in rep and "Write outside the project folder" in rep
    f = hub.current.folder
    assert f.read(f.assumptions).count("_(autopilot)_") == 2
    assert "Autopilot approved" not in rep.split("## Approved by autopilot")[0]     # not repeated as assumptions


def test_switching_autopilot_on_mid_run_approves_open_cards(harness):
    h = harness()
    _setup([fake.call("Bash", {"command": "git push"}), fake.call("Bash", {"command": "npm install left-pad"}),
            fake.call("submit_report", report())])

    async def go():
        hub, c = await h.start()
        sid = hub.current.id
        await hub.handle({"type": "set_autopilot", "session_id": sid, "on": False})        # before launch
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": sid})
        await h.wait(lambda: c.of("queue_item"))
        await hub.handle({"type": "set_autopilot", "session_id": sid, "on": True})          # mid-run
        await h.wait(lambda: c.of("run_finished"))
        late = Client(hub)
        await hub.connect(late)
        return hub, c, late

    hub, c, late = asyncio.run(go())
    assert [e["on"] for e in c.of("autopilot")] == [False, True]
    assert c.of("run_started")[0]["autopilot"] is False
    assert len(c.of("queue_item")) == 1                                    # the second request needed no card
    assert c.of("queue_resolved")[0]["answer"] == "allow" and c.of("queue_resolved")[0]["by"] == "autopilot"
    assert [err for _, _, err in h.tool_results()[:2]] == [False, False]
    assert len([e for e in c.of("activity") if e.get("auto")]) == 2
    s = next(x for x in late.events[0]["sessions"] if x["session_id"] == hub.current.id)
    assert s["autopilot"] is True


@pytest.mark.parametrize("decision,expect_error", [("deny", True), ("allow", False)])
def test_deny_listed_shell_command_raises_permission_card(harness, decision, expect_error):
    h = harness()
    _setup([fake.call("Bash", {"command": "python -m pytest -q"}),
            fake.call("Bash", {"command": "git push origin main"}),
            fake.call("submit_report", report())])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": decision}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    cards = c.of("queue_item")
    assert len(cards) == 1 and cards[0]["kind"] == "permission" and cards[0]["timeout_s"] == 180
    assert cards[0]["blocking"] is False and cards[0]["expires_at"] and cards[0]["body"] == "git push origin main"
    assert cards[0]["rec"] is None and cards[0]["title"] == "Bash · git push"
    assert [err for _, _, err in h.tool_results()[:2]] == [False, expect_error]
    assert c.of("queue_resolved")[0]["answer"] == decision


def test_always_allow_skips_later_cards(harness):
    h = harness()
    _setup([fake.call("Bash", {"command": "git push"}), fake.call("Bash", {"command": "git push --tags"}),
            fake.call("submit_report", report())])
    h.responder = lambda ev: ({"type": "queue_response", "id": ev["id"], "decision": "always"}
                              if ev.get("type") == "queue_item" else None)

    async def go():
        hub, c = await _run(h)
        await h.wait(lambda: c.of("run_finished"))
        return c

    c = asyncio.run(go())
    assert len(c.of("queue_item")) == 1
    assert [err for _, _, err in h.tool_results()[:2]] == [False, False]


@pytest.mark.parametrize("cmd,label", [
    ("git push origin main", "git push"), ("git commit -m 'x'", "git commit"),
    ("cd sub && git -c a=b commit -am x", "git commit"),
    ("pip install requests", "package install"), ("python -m pip install x", "package install"),
    ("npm i left-pad", "package install"), ("uv add httpx", "package install"),
    ("winget install foo", "package install"),
    ("rm -rf ../other", "delete outside the project"), ("rm -rf /", "delete outside the project"),
    ("cd .. && rm -rf proj", "delete outside the project"), ("rm $HOME/x", "delete outside the project"),
    ("rm -rf build", None), ("rm out/a.txt", None), ("python -m pytest -q", None), ("git status", None),
    ("ls -la | grep x", None),
])
def test_deny_list(project, cmd, label):
    assert deny_match(cmd, project) == label
