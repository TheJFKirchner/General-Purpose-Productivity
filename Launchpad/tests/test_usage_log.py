"""The usage log and the Usage screen's data (request 2026-11-17 usage monitor, task A): one line per agent call for
every kind of agent, sums equal to the totals the app already shows, damaged lines skipped, concurrent appends, day /
week grouping, CLI / model / agent splits with "Other", the sessions list, pushes on new spend, and the --fake demo
history (temp home only). Fake engine only, zero tokens."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import subprocess
import sys
import textwrap
from types import SimpleNamespace

from agentlib import fake
from agentlib.reply import Usage

from app import demo, usagelog
from app.agents import crew
from app.hub import Hub
from app.settings import Settings
from app.store import Store, launchpad_home
from app.usagelog import UsageLog, build, model_label

from conftest import PLAN, ROOT, Client, report, script_orchestrator_sequential

ONE = {**PLAN, "steps": PLAN["steps"][:1]}


def near(a, b, tol=1e-6) -> bool:
    return abs(float(a) - float(b)) < tol


def row(ts: dt.datetime, session="S1", agent="Builder", role="builder", model="claude-sonnet-4-5", cost=0.01,
        kind="plan", cli="claude", **kw) -> dict:
    r = {"v": 1, "ts": ts.astimezone().isoformat(timespec="seconds"), "session": session, "kind": kind,
         "label": kw.pop("label", "A plan"), "dir_id": "d1", "folder": "/x/proj", "folder_name": "proj",
         "run_folder": None, "role": role, "agent": agent, "step": None, "stage": None, "model": model, "cli": cli,
         "engine": cli, "cost": cost, "input_tokens": 10, "output_tokens": 100, "cache_read_tokens": 1000,
         "cache_write_tokens": 50}
    r.update(kw)
    return r


# --------------------------------------------------------------------------- sums equal the app's own totals
def test_log_sums_equal_the_app_totals_for_session_planner_chat_and_app(harness):
    h = harness(timeout_s=5)
    fake.script("launchpad-planner", [[fake.spend(0.011), fake.call("explore", {"question": "q"}),
                                       fake.call("write_plan", ONE)]])
    fake.script("launchpad-astronaut", [[fake.spend(0.002), fake.output({"links": []})]])
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.spend(0.02), fake.call("submit_report", report())]])
    fake.script("launchpad-pilot", [[fake.spend(0.005), fake.say("hi")]])
    fake.script("launchpad-drafter", [[fake.spend(0.0003), fake.output(demo.draft_fields("reviews copy"))]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": hub.current.id})
        await h.wait(lambda: c.of("run_finished"))
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        await hub.handle({"type": "agent_draft", "dir_id": hub.default_dir, "text": "an agent that reviews copy"})
        await hub.handle({"type": "usage_get", "period": "7d", "bucket": "day", "split": "agent"})
        return hub, c, cid

    hub, c, cid = asyncio.run(go())
    sid = hub.current.id
    rows = hub.usage.rows()
    session_ev = [e for e in c.of("usage") if e.get("scope") == "session" and e["session_id"] == sid][-1]
    chat_ev = [e for e in c.of("usage") if e.get("scope") == "chat" and e["chat_id"] == cid][-1]
    app_ev = [e for e in c.of("usage") if e.get("scope") == "app"][-1]
    mine = [r for r in rows if r["session"] == sid]
    assert near(sum(r["cost"] for r in mine if r["role"] != "planner"), session_ev["cost"])
    assert near(sum(r["cost"] for r in mine if r["role"] == "planner"), session_ev["planner_cost"])
    for k in usagelog.TOKENS:                                       # the session's crew tokens match too
        assert sum(r[k] for r in mine if r["role"] != "planner") == session_ev[k]
    assert near(sum(r["cost"] for r in rows if r["session"] == cid), chat_ev["cost"])
    assert near(sum(r["cost"] for r in rows), app_ev["cost"])
    assert {r["role"] for r in mine} == {"planner", "astronaut", "orchestrator", "builder"}
    assert all(r["kind"] == "plan" for r in mine)
    assert all(r["label"] == ONE["name"] for r in mine if r["role"] in ("orchestrator", "builder"))
    assert all(r["model"] and r["cli"] == "fake" and r["folder"] == str(h.project.resolve()) for r in rows)
    assert len([m for m in hub.meters if m.cost_usd]) <= len(rows)  # every metered agent wrote at least one line
    chat_rows = [r for r in rows if r["session"] == cid]
    assert chat_rows and all(r["kind"] == "chat" and r["role"] == "pilot" and r["agent"] == "CLI" for r in chat_rows)
    drafted = [r for r in rows if r["role"] == "drafter"]
    assert drafted and drafted[0]["kind"] == "other" and drafted[0]["label"] == "Agent drafting"
    # the screen's data says the same
    data = c.of("usage_data")[-1]
    assert data["pushed"] is False and data["request"] == {"period": "7d", "bucket": "day", "split": "agent",
                                                           "session": None}
    assert near(data["totals"]["cost"], app_ev["cost"]) and data["totals"]["calls"] == len(rows)
    s = next(x for x in data["sessions"] if x["id"] == sid)
    assert near(s["cost"] - s["planner_cost"], session_ev["cost"]) and near(s["planner_cost"], session_ev["planner_cost"])
    assert s["kind"] == "plan" and s["kind_label"] == "Plan" and s["running"] is False
    assert s["folder"]["path"] == str(h.project.resolve()) and s["run_folder"].endswith(sid)
    assert {x["kind"] for x in data["sessions"]} == {"plan", "chat", "other"}
    assert {x["label"] for x in data["series"]} >= {"Planner", "Explorer", "Orchestrator", "Builder", "CLI",
                                                     "Agent drafter"}
    assert len(data["buckets"]) == 7 and data["buckets"][-1]["key"] == dt.date.today().isoformat()
    assert all(len(x["values"][m]) == 7 for x in data["series"] for m, _, _ in usagelog.MEASURES)


def test_workflow_stages_and_role_reviews_are_logged_to_the_monthly_file(project):
    from test_roles_review import case_data, seed
    from test_workflows import last_run, put, script_builder, wait
    put(project, "mini", {"name": "Mini", "output_folder": "out/mini", "stages": [
        {"kind": "agent", "title": "Load data", "agent": "launchpad-builder", "instruction": "Load the data."}]})
    script_builder([])
    fake.script("launchpad-role-reviewer", [[fake.spend(0.012), fake.output(case_data("keep"))]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake", question_timeout_s=5),
                  store=Store(launchpad_home() / "settings.json"))
        c = Client(hub)
        await hub.connect(c)
        wid = c.of("workflows_list")[-1]["workflows"][0]["id"]
        await hub.handle({"type": "workflow_run", "id": wid, "test": False, "unattended": True, "inputs": {}})
        await wait(lambda: (last_run(c) or {}).get("status") == "done")
        seed(hub, project=project)
        await hub.handle({"type": "review_start", "role": "sql-tuner"})
        await hub.handle({"type": "usage_get", "period": "30d", "split": "agent"})
        return hub, c

    hub, c = asyncio.run(go())
    files = list((launchpad_home() / "usage").glob("*.jsonl"))
    assert [f.name for f in files] == [dt.date.today().strftime("%Y-%m") + ".jsonl"]
    rows = hub.usage.rows()
    wf = [r for r in rows if r["kind"] == "workflow"]
    run = last_run(c)
    assert wf and all(r["session"] == run["mission_id"] and r["stage"] == "Load data" and r["agent"] == "Builder"
                      for r in wf)
    assert near(sum(r["cost"] for r in wf), run["cost_usd"])
    assert wf[0]["label"].startswith("Mini, run ") and wf[0]["run_folder"] == run["folder"]
    rv = [r for r in rows if r["kind"] == "review"]
    assert rv and rv[0]["label"] == "Role review: sql-tuner" and rv[0]["session"].startswith("reviewer-")
    reviewer_cost = sum(m.cost_usd for m in hub.meters if m.role == "reviewer")
    assert rv[0]["agent"] == crew.display("role_reviewer") and reviewer_cost >= 0.012
    assert near(sum(r["cost"] for r in rv), reviewer_cost)
    data = c.of("usage_data")[-1]
    assert "Workflow: Builder" in {s["label"] for s in data["series"]}
    assert {s["kind"] for s in data["sessions"]} == {"workflow", "review"}


def test_a_reply_with_several_models_is_split_per_model_and_still_adds_up():
    meter = SimpleNamespace(session_id=None, chat_id=None, agent_id="drafter-1", role="drafter", name="Agent drafter",
                            step=None, usage_info={"folder": None})
    reply = SimpleNamespace(usage=Usage(input_tokens=30, output_tokens=300, cache_read_tokens=3000,
                                        cache_write_tokens=90),
                            cost_usd=0.05, engine="claude", model="opus",
                            usage_by_model={"claude-sonnet-4-5-20250929": {"usage": Usage(10, 100, 1000, 30),
                                                                            "cost_usd": 0.01},
                                            "claude-opus-4-1": {"usage": Usage(15, 150, 1500, 40), "cost_usd": 0.03}})
    r = usagelog.line(SimpleNamespace(), meter, reply)
    assert r["cli"] == "claude" and r["kind"] == "other" and r["cost"] == 0.05 and r["session"] == "drafter-1"
    by = r["by_model"]
    assert near(sum(p["cost"] for p in by), 0.05) and sum(p["input_tokens"] for p in by) == 30
    assert {p["model"] for p in by} == {"claude-sonnet-4-5-20250929", "claude-opus-4-1", "opus"}   # rest on "opus"
    log = UsageLog(None)
    log.append(r)
    data = build(log, {"period": "7d", "split": "model"})
    assert {s["label"]: s["totals"]["cost"] for s in data["series"]} == {"Opus 4.1": 0.03, "Sonnet 4.5": 0.01,
                                                                          "Opus": 0.01}
    assert data["totals"]["calls"] == 1 and near(data["totals"]["cost"], 0.05)
    one = SimpleNamespace(**{**vars(reply), "usage_by_model": {"claude-haiku-4-5": {"usage": reply.usage,
                                                                                     "cost_usd": 0.05}}})
    r1 = usagelog.line(SimpleNamespace(), meter, one)
    assert "by_model" not in r1 and r1["model"] == "claude-haiku-4-5"


def test_costs_are_only_ever_added_in_the_meter_so_no_agent_skips_the_log():
    import re
    hits = []
    for p in (ROOT / "app").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        if re.search(r"\.cost_usd\s*\+=", text):
            hits.append(p.relative_to(ROOT).as_posix())
    assert hits == ["app/meter.py"]                                  # Meter.add_reply: the one place, which logs
    meters = [p.relative_to(ROOT).as_posix() for p in (ROOT / "app").rglob("*.py")
              if "Meter(" in p.read_text(encoding="utf-8") and p.name != "meter.py"]
    assert sorted(meters) == sorted(["app/agents/builder/builder.py", "app/agents/claude_code/pilot.py",
                                     "app/agents/drafter/drafter.py", "app/agents/explorer/astronaut.py",
                                     "app/agents/orchestrator/run.py", "app/agents/planner/planner.py",
                                     "app/agents/role_reviewer/reviewer.py", "app/agents/visualizer/visuals.py",
                                     "app/workflows/runner.py"])          # a new agent kind: check it is logged


def test_model_labels():
    assert model_label("claude-sonnet-4-5-20250929") == "Sonnet 4.5"
    assert model_label("claude-opus-4-1") == "Opus 4.1" and model_label("claude-3-5-haiku-20241022") == "Haiku 3.5"
    assert model_label("sonnet") == "Sonnet" and model_label("claude-sonnet-4-5[1m]") == "Sonnet 4.5 (1M)"
    assert model_label("fake") == "fake" and model_label("") == "Unknown model"


# --------------------------------------------------------------------------- reading: damage, growth, concurrency
def test_damaged_and_half_written_lines_are_skipped_and_reading_is_incremental(tmp_path):
    log = UsageLog(tmp_path / "usage")
    now = dt.datetime.now()
    log.append(row(now, cost=0.5))
    path = log.month_file()
    with open(path, "ab") as f:
        f.write(b"{not json\n" + b'{"session": "S1", "ts": "not a time"}\n' + b"[1, 2]\n" + b'{"session": "S9", "ts": "20')
    data = build(log, {"period": "7d"})
    assert near(data["totals"]["cost"], 0.5) and data["skipped_lines"] == 3 and data["totals"]["calls"] == 1
    log.append(row(now, session="S2", cost=0.25))                  # the half line gets its newline first
    data = build(log, {"period": "7d"})
    assert near(data["totals"]["cost"], 0.75) and data["skipped_lines"] == 4 and data["totals"]["sessions"] == 2
    state = log._files[str(path)]
    assert state.offset == path.stat().st_size                     # read up to the end once; only new bytes after
    other = UsageLog(tmp_path / "usage")                           # a fresh reader (a new launch) sees the same
    again = build(other, {"period": "7d"})
    assert near(again["totals"]["cost"], 0.75) and again["skipped_lines"] == 4
    assert build(UsageLog(tmp_path / "nothing"), {})["range"] is None


def test_a_month_file_per_month_and_short_periods_skip_old_months(tmp_path):
    log = UsageLog(tmp_path / "usage")
    today = dt.date(2026, 11, 17)
    old = dt.datetime(2026, 6, 3, 10, 0)
    log.append_many([row(old, session="OLD", cost=1.0), row(dt.datetime(2026, 11, 16, 9), session="NEW", cost=0.1)])
    assert sorted(p.name for p in log.files()) == ["2026-06.jsonl", "2026-11.jsonl"]
    week = build(log, {"period": "7d"}, today=today)
    assert near(week["totals"]["cost"], 0.1) and [s["id"] for s in week["sessions"]] == ["NEW"]
    assert str(tmp_path / "usage" / "2026-06.jsonl") not in log._files            # never opened for 7 days
    everything = build(log, {"period": "all", "bucket": "week"}, today=today)
    assert near(everything["totals"]["cost"], 1.1) and everything["range"] == {"start": "2026-06-03", "end": "2026-11-17"}
    assert everything["buckets"][0] == {"key": "2026-06-01", "label": "Week of 1 Jun", "start": "2026-06-03",
                                        "end": "2026-06-07", "partial": True}


def test_concurrent_appends_from_several_processes_never_corrupt_the_log(tmp_path):
    folder = tmp_path / "usage"
    script = textwrap.dedent(f"""
        import datetime as dt, sys
        sys.path.insert(0, {str(ROOT)!r})
        from app.usagelog import UsageLog
        log = UsageLog({str(folder)!r})
        for i in range(150):
            log.append({{"v": 1, "ts": dt.datetime.now().astimezone().isoformat(), "session": "P" + sys.argv[1],
                         "kind": "chat", "role": "pilot", "agent": "CLI", "model": "m", "cli": "claude",
                         "cost": 0.001, "input_tokens": 1, "output_tokens": 2, "cache_read_tokens": 3,
                         "cache_write_tokens": 4, "label": "x" * (i % 50)}})
    """)
    procs = [subprocess.Popen([sys.executable, "-c", script, str(k)]) for k in range(4)]
    assert all(p.wait(timeout=120) == 0 for p in procs)
    log = UsageLog(folder)
    raw = b"".join(p.read_bytes() for p in log.files())
    assert raw.count(b"\n") == 600 and all(json.loads(x) for x in raw.split(b"\n") if x)
    data = build(log, {"period": "7d", "split": "cli"})
    assert data["skipped_lines"] == 0 and data["totals"]["calls"] == 600 and data["totals"]["sessions"] == 4
    assert not list(folder.glob("*.lock"))


# --------------------------------------------------------------------------- grouping
def test_day_and_week_buckets_splits_other_and_the_sessions_list():
    log = UsageLog(None)
    today = dt.date(2026, 11, 18)                                    # a Wednesday
    rows = []
    for i in range(9):                                                # nine agents: 6 named + Other
        rows.append(row(dt.datetime(2026, 11, 16, 9, i), session="S1", agent=f"Agent {i}", cost=0.01 * (i + 1)))
    rows.append(row(dt.datetime(2026, 11, 10, 9), session="S2", kind="chat", role="pilot", agent="CLI",
                    model="claude-opus-4-5", cost=0.5, label="CLI chat"))
    rows.append(row(dt.datetime(2026, 11, 18, 8), session="S3", kind="workflow", agent="Builder", cost=0.2,
                    label="Mini, run 1"))
    rows.append(row(dt.datetime(2026, 11, 18, 8, 5), session="S1", role="planner", agent="Planner", cost=0.05))
    log.append_many(rows)
    total = sum(r["cost"] for r in rows)

    days = build(log, {"period": "7d", "bucket": "day", "split": "agent"}, today=today, running={"S2"}.__contains__)
    assert [b["key"] for b in days["buckets"]] == [f"2026-11-{d}" for d in range(12, 19)]
    assert days["buckets"][0]["label"] == "12 Nov" and not days["buckets"][0]["partial"]
    assert len(days["series"]) == 7 and days["series"][-1]["key"] == "__other__"
    other = days["series"][-1]
    assert other["label"] == "Other" and len(other["members"]) == 5   # 9 agents + Planner + Workflow: Builder - 6
    costs = [s["totals"]["cost"] for s in days["series"][:-1]]
    assert costs == sorted(costs, reverse=True)
    assert "Workflow: Builder" in [s["label"] for s in days["series"]] + other["members"]
    assert near(days["totals"]["cost"], total - 0.5)                 # S2 (10 Nov) is outside the last 7 days
    assert near(sum(sum(s["values"]["cost"]) for s in days["series"]), days["totals"]["cost"])
    assert [s["id"] for s in days["sessions"]] == ["S1", "S3"]       # S2 not in the range; latest call first
    s1 = days["sessions"][0]
    assert near(s1["planner_cost"], 0.05) and s1["calls"] == 10 and "Planner" in s1["agents"]

    weeks = build(log, {"period": "30d", "bucket": "week", "split": "model"}, today=today, running={"S2"}.__contains__)
    assert [b["key"] for b in weeks["buckets"]] == ["2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09",
                                                    "2026-11-16"]                    # Mondays
    assert weeks["buckets"][0]["start"] == "2026-10-20" and weeks["buckets"][0]["partial"]   # 30 days back = 20 Oct
    assert weeks["buckets"][-1] == {"key": "2026-11-16", "label": "Week of 16 Nov", "start": "2026-11-16",
                                    "end": "2026-11-18", "partial": True}
    assert not weeks["buckets"][1]["partial"] and weeks["buckets"][1]["end"] == "2026-11-01"
    assert {s["label"] for s in weeks["series"]} == {"Sonnet 4.5", "Opus 4.5"}
    assert weeks["sessions"][0]["id"] == "S2" and weeks["sessions"][0]["running"] is True     # running first
    assert near(weeks["totals"]["cost"], total)

    narrowed = build(log, {"period": "30d", "split": "cli", "session": "S1"}, today=today)
    assert narrowed["totals"]["sessions"] == 1 and narrowed["totals"]["calls"] == 10
    assert [s["label"] for s in narrowed["series"]] == ["Claude"] and len(narrowed["sessions"]) == 3
    bad = build(log, {"period": "1y", "bucket": "month", "split": "x"}, today=today)
    assert bad["request"] == {"period": "30d", "bucket": "day", "split": "agent", "session": None}
    assert [m["key"] for m in bad["measures"]] == ["cost", "input_tokens", "output_tokens", "cache_read_tokens",
                                                   "cache_write_tokens"]


# --------------------------------------------------------------------------- pushes
def test_usage_data_is_pushed_after_new_spend_until_usage_stop(harness, monkeypatch):
    from app import hub as hub_mod
    monkeypatch.setattr(hub_mod, "USAGE_PUSH_DELAY_S", 0.0)
    h = harness()
    fake.script("launchpad-pilot", [[fake.spend(0.004), fake.say("hi")]] * 3)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "usage_get", "period": "7d", "split": "cli"})
        assert len(c.of("usage_data")) == 1 and c.of("usage_data")[0]["range"] is None   # nothing recorded yet
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        await h.wait(lambda: any(e["pushed"] for e in c.of("usage_data")))
        pushed = [e for e in c.of("usage_data") if e["pushed"]][-1]
        await hub.handle({"type": "usage_stop"})
        n = len(c.of("usage_data"))
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "again"})
        await asyncio.sleep(0.05)
        return c, pushed, n

    c, pushed, n = asyncio.run(go())
    assert pushed["request"]["split"] == "cli" and pushed["series"][0]["label"] == "Fake engine (demo)"
    assert pushed["totals"]["calls"] >= 1 and pushed["sessions"][0]["kind"] == "chat"
    assert len(c.of("usage_data")) == n                              # no pushes after usage_stop


def test_a_log_that_cannot_be_written_never_stops_an_agent(harness, monkeypatch):
    h = harness()
    fake.script("launchpad-pilot", [[fake.spend(0.004), fake.say("hi")]])

    def broken(self, rows):
        raise OSError("disk full")

    monkeypatch.setattr(UsageLog, "append_many", broken)

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "chat_new"})
        cid = c.of("chat_started")[-1]["chat_id"]
        await hub.handle({"type": "chat_message", "chat_id": cid, "text": "hello"})
        return c, cid

    c, cid = asyncio.run(go())
    assert c.of("chat_done")[-1]["status"] == "ok"
    assert [e for e in c.of("usage") if e.get("scope") == "chat" and e["chat_id"] == cid][-1]["cost"] > 0


# --------------------------------------------------------------------------- the fake demo
def test_fake_demo_seeds_weeks_of_history_in_its_temp_home_only(tmp_path, monkeypatch):
    import argparse
    import tempfile
    from pathlib import Path
    from app import launch
    from app.agents.planner import planner
    real_home = tmp_path / "real-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: real_home))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    monkeypatch.delenv("LAUNCHPAD_HOME", raising=False)
    for name in ("APP_ROOT", "AGENTS_DIR"):
        monkeypatch.setattr(crew, name, getattr(crew, name))
    monkeypatch.setattr(planner, "CRITERIA_FILE", planner.CRITERIA_FILE)
    settings, store, _ = launch.build_settings(argparse.Namespace(fake=True, cwd="", model=None))
    hub = Hub(settings, store=store)
    demo_home = tmp_path / "tmp" / "launchpad-demo" / "home"
    assert hub.usage.folder == demo_home / "usage" and hub.usage.files()
    assert not (real_home / ".launchpad").exists()
    data = build(hub.usage, {"period": "90d", "bucket": "week", "split": "agent"})
    busy = [b for i, b in enumerate(data["buckets"]) if any(s["values"]["cost"][i] for s in data["series"])]
    assert len(busy) >= 5 and data["totals"]["cost"] > 0                             # five weeks of history
    labels = {s["label"] for s in data["series"]} | {m for s in data["series"] for m in s["members"]}
    assert {"Planner", "Builder", "CLI"} <= labels and any(x.startswith("Workflow: ") for x in labels)
    models = build(hub.usage, {"period": "90d", "split": "model"})
    assert {s["label"] for s in models["series"]} == {"Sonnet 4.5", "Opus 4.5", "Haiku 4.5"}
    assert {s["kind"] for s in data["sessions"]} == {"plan", "chat", "workflow", "review", "other"}
    folders = {s["folder"]["name"] for s in data["sessions"]}
    assert folders == {d["name"] for d in store.directories()}
    n = len(hub.usage.rows())
    demo.seed_usage(hub.usage, store)                                                # never seeded twice
    assert len(hub.usage.rows()) == n
    real = UsageLog(real_home / ".launchpad" / "usage")                              # never a real log
    demo.seed_usage(real, store)
    assert not real.folder.exists()
    elsewhere = Hub(Settings(project=settings.project, engine="fake"), store=Store(real_home / ".launchpad" / "settings.json"))
    assert elsewhere.usage.folder is None
