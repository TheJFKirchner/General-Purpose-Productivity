"""plan.md format and the session folder basics."""
import re

from app import plan as plan_mod
from app.sessionfiles import SessionFolder, new_session_id

from conftest import PLAN


def test_render_validate_parse_roundtrip():
    text = plan_mod.render(name=PLAN["name"], goal=PLAN["goal"], steps=PLAN["steps"], session="s1")
    assert plan_mod.validate(text) == []
    p = plan_mod.parse(text)
    assert p["status"] == "draft" and [s["n"] for s in p["steps"]] == [1, 2] and p["steps"][1]["after"] == [1]
    assert "Make the second thing." in plan_mod.step_text(text, 2)
    t2 = plan_mod.set_status(text, plan_status="approved", step=1, step_status="done")
    p2 = plan_mod.parse(t2)
    assert p2["status"] == "approved" and p2["steps"][0]["status"] == "done" and p2["body"] == p["body"]


def test_bad_plans_are_rejected():
    bad_dep = plan_mod.render(name="x", goal="g", session="s", steps=[{"title": "a", "details": "d", "after": [2]},
                                                                       {"title": "b", "details": "d"}])
    assert any("after" in p for p in plan_mod.validate(bad_dep))
    assert any("title" in p for p in plan_mod.validate(plan_mod.render(name="x", goal="g", session="s",
                                                                       steps=[{"title": "", "details": "d"}])))
    assert plan_mod.validate("no header") and plan_mod.validate("---\nplan: x\n---\n")


def test_session_id_and_gitignore(project):
    sid = new_session_id()
    assert re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", sid)
    f = SessionFolder(project, sid)
    assert not f.path.exists()                                    # created on first write
    f.add_assumption("x", agent="a", step=1, source="test")
    assert (project / ".launchpad" / ".gitignore").read_text(encoding="utf-8").strip().endswith("*")
    assert f.assumptions.is_file()


def test_flight_log_links_dedupe_and_refuse_outside(project):
    f = SessionFolder(project, new_session_id())
    assert f.add_flight_log("CLAUDE.md", "rules", source="test")
    assert not f.add_flight_log("CLAUDE.md", "again", source="test")           # duplicate
    assert not f.add_flight_log("../outside.md", "nope", source="test")        # outside the project
    assert not f.add_flight_log("missing.py", "nope", source="test")
    text = f.read(f.flight_log)
    assert "[CLAUDE.md](../../CLAUDE.md) — rules" in text and "outside" not in text
