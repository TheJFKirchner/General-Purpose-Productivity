"""Connected directories, the settings store, file browsing and hand-editing (fake engine, no tokens)."""
import asyncio
import os
import shutil
from pathlib import Path

import pytest

from agentlib import fake

from app import crew
from app import files as files_mod
from app.hub import Hub
from app.settings import Settings
from app.store import Store, dir_id
from conftest import PLAN, Client, report, script_orchestrator_sequential, script_planner_writes_plan


def _dirs(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    for d in (a, b):
        (d / "docs").mkdir(parents=True)
        (d / "README.md").write_bytes(f"# {d.name}\n".encode("utf-8"))
    return a, b


async def _hub(tmp_path, a, b, **kw):
    store = Store(tmp_path / "home" / "settings.json")
    store.add(b)
    hub = Hub(Settings(project=a, engine="fake", **kw), store=store)
    c = Client(hub)
    await hub.connect(c)
    return hub, c


def _err(c):
    return c.of("file_error")[-1]


# ------------------------------------------------------------------ settings store
def test_settings_persist_and_reload(tmp_path):
    a, b = _dirs(tmp_path)
    s = Store(tmp_path / "settings.json")
    s.add(a)
    s.add(b)
    s.set_default(dir_id(b))
    s.set_values({"question_timeout_s": "90", "autopilot_default": "true", "pilot_model": "haiku"})
    again = Store(tmp_path / "settings.json")
    assert [d["name"] for d in again.directories()] == ["A", "B"] and again.default_id() == dir_id(b)
    v = again.values()
    assert v["question_timeout_s"] == 90.0 and v["autopilot_default"] is True and v["pilot_model"] == "haiku"
    assert v["planner_top_model"] == "opus"                                   # unset -> default
    with pytest.raises(ValueError):
        again.set_values({"question_timeout_s": "soon"})
    with pytest.raises(ValueError):
        again.set_values({"no_such_setting": 1})


def test_directory_messages_and_settings_event(tmp_path):
    a, b = _dirs(tmp_path)
    c_dir = tmp_path / "C"
    c_dir.mkdir()

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        ev = c.of("settings")[0]
        assert {d["name"] for d in ev["directories"]} == {"A", "B"} and ev["can_pick_directory"] is False
        assert next(d for d in ev["directories"] if d["name"] == "A")["is_default"]
        assert ev["values"]["question_timeout_s"] == {"value": 180, "applies": "now", "overridden_by_launch": False}
        assert ev["values"]["planner_start_model"]["applies"] == "new_sessions"
        await hub.handle({"type": "add_directory", "path": str(c_dir)})
        await hub.handle({"type": "add_directory", "path": str(tmp_path / "nope")})
        await hub.handle({"type": "set_settings", "patch": {"permission_timeout_s": 60}})
        await hub.handle({"type": "pick_directory"})
        await hub.handle({"type": "remove_directory", "dir_id": dir_id(c_dir)})
        return hub, c

    hub, c = asyncio.run(go())
    last = c.of("settings")[-1]
    assert {d["name"] for d in last["directories"]} == {"A", "B"} and c_dir.is_dir()     # removal deletes nothing
    assert hub.settings.permission_timeout_s == 60.0 and last["values"]["permission_timeout_s"]["value"] == 60.0
    assert Store(tmp_path / "home" / "settings.json").values()["permission_timeout_s"] == 60.0
    assert any("not a folder" in e["text"] for e in c.of("system"))
    assert c.of("directory_picked")[-1] == {"type": "directory_picked", "path": None}


def test_sessions_run_in_their_own_directory_with_their_own_guard(tmp_path):
    a, b = _dirs(tmp_path)
    script_planner_writes_plan({**PLAN, "steps": PLAN["steps"][:1]})
    script_orchestrator_sequential(1)
    target_in_a = str(a / "from-b.txt")

    def builder(msg):
        if "block me" in msg:                                     # session A: waits on a blocking question
            return [fake.call("ask_question", {"title": "Wait?", "body": "b", "recommended": "ok", "blocking": True}),
                    fake.call("submit_report", report())]
        return [fake.call("Write", {"file_path": "inside-b.txt", "content": "x"}),
                fake.call("Write", {"file_path": target_in_a, "content": "x"}),
                fake.call("submit_report", report())]

    fake.script("launchpad-builder", [builder])

    async def go():
        hub, c = await _hub(tmp_path, a, b, permission_timeout_s=0.2)
        sa = hub.current
        await hub.handle({"type": "user_message", "text": "go"})
        sa.plan_text = sa.plan_text.replace("Make the first thing.", "Make the first thing. block me")
        sa.folder.write_plan(sa.plan_text)
        await hub.handle({"type": "plan_approve", "session_id": sa.id})
        late = Client(hub)
        await hub.connect(late)
        await hub.handle({"type": "remove_directory", "dir_id": dir_id(a)})          # busy: refused
        await hub.handle({"type": "new_session", "dir_id": dir_id(b)})
        sb = hub.current
        await hub.handle({"type": "user_message", "text": "go"})
        await hub.handle({"type": "plan_approve", "session_id": sb.id})
        await hub.handle({"type": "chat_new", "dir_id": dir_id(b)})
        while not [e for e in c.of("run_finished") if e["session_id"] == sb.id]:
            await asyncio.sleep(0.01)
        await hub.handle({"type": "run_stop", "session_id": sa.id})
        return hub, c, sa, sb

    hub, c, sa, sb = asyncio.run(go())
    assert sa.folder.path.parent == a / ".launchpad" and sb.folder.path.parent == b / ".launchpad"
    assert (b / ".launchpad" / sb.id / "report.md").is_file() and not (a / ".launchpad" / sb.id).exists()
    started = {e["session_id"]: e for e in c.of("session_started")}
    assert started[sb.id]["dir_id"] == dir_id(b) and started[sb.id]["cwd"] == str(b.resolve())
    card = next(e for e in c.of("queue_item") if e["session_id"] == sb.id and e["kind"] == "permission")
    assert card["title"] == "Write outside the project folder" and card["body"] == target_in_a   # A is outside B
    assert c.of("chat_started")[-1]["dir_id"] == dir_id(b) and hub.chats[c.of("chat_started")[-1]["chat_id"]].folder.project == b.resolve()
    assert any("a session is running in that folder" in e["text"] for e in c.of("system"))
    assert hub.default_dir == dir_id(b)                                   # last used
    assert Store(tmp_path / "home" / "settings.json").default_id() == dir_id(b)


# ------------------------------------------------------------------ browsing
def test_list_and_read_inside_a_root_and_refuse_outside(tmp_path):
    a, b = _dirs(tmp_path)
    (tmp_path / "secret.md").write_text("# secret\n", encoding="utf-8")
    (a / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00binary")
    (a / "big.md").write_text("x" * (files_mod.MAX_BYTES + 10), encoding="utf-8")
    (a / "notes.txt").write_text("plain text\n", encoding="utf-8")
    (a / ".launchpad" / "20261113-000000-abcd").mkdir(parents=True)
    linked = True
    try:
        os.symlink(tmp_path / "secret.md", a / "link.md")
    except (OSError, NotImplementedError):
        linked = False

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        root = dir_id(a)
        await hub.handle({"type": "list_dir", "root": root, "path": ""})
        await hub.handle({"type": "read_file", "root": root, "path": "README.md"})
        await hub.handle({"type": "read_file", "root": root, "path": "../secret.md"})
        e1 = _err(c)
        await hub.handle({"type": "read_file", "root": root, "path": "docs/../../secret.md"})
        e2 = _err(c)
        await hub.handle({"type": "read_file", "root": root, "path": "image.png"})
        e3 = _err(c)
        await hub.handle({"type": "read_file", "root": root, "path": "big.md"})
        e4 = _err(c)
        await hub.handle({"type": "read_file", "root": "dnope", "path": "README.md"})
        e5 = _err(c)
        e6 = None
        if linked:
            await hub.handle({"type": "read_file", "root": root, "path": "link.md"})
            e6 = _err(c)
        await hub.handle({"type": "list_dir", "root": "app", "path": ""})
        await hub.handle({"type": "list_dir", "root": "app", "path": ".claude/agents"})
        await hub.handle({"type": "read_file", "root": "app", "path": "app/hub.py"})
        e7 = _err(c)
        return c, (e1, e2, e3, e4, e5, e6, e7)

    c, (e1, e2, e3, e4, e5, e6, e7) = asyncio.run(go())
    listing = c.of("dir_listing")[0]
    kinds = {e["name"]: (e["type"], e["kind"], e["editable"]) for e in listing["entries"]}
    assert kinds[".launchpad"] == ("dir", None, False) and kinds["docs"][0] == "dir"
    assert kinds["README.md"] == ("file", "markdown", True) and kinds["notes.txt"] == ("file", "text", False)
    assert kinds["image.png"][1] == "binary" and kinds["big.md"][1] == "too_large"
    assert "secret.md" not in kinds and ("link.md" not in kinds)            # a link leading outside is not listed
    content = c.of("file_content")[0]
    assert content["text"] == "# A\n" and content["editable"] and content["applies"] == "now" and content["version"]
    assert [e["code"] for e in (e1, e2, e3, e4, e5)] == ["not_allowed", "not_allowed", "binary", "too_large", "not_allowed"]
    assert e6 is None or e6["code"] == "not_allowed"
    assert e7["code"] == "not_allowed"
    app_top = {e["name"] for e in c.of("dir_listing")[1]["entries"]}
    assert app_top == {".claude", "app"}
    agents = c.of("dir_listing")[2]["entries"]
    assert {e["name"] for e in agents} == {r["file"] for r in list(crew.ROLES.values()) + list(crew.HELPERS.values())} and all(e["editable"] for e in agents)


# ------------------------------------------------------------------ editing
def test_save_conflict_invalid_backups_and_view_only(tmp_path):
    a, b = _dirs(tmp_path)
    (a / ".claude" / "agents").mkdir(parents=True)
    (a / ".claude" / "agents" / "mine.md").write_text("---\nname: mine\ndescription: x\n---\nHi\n", encoding="utf-8")
    (a / "notes.txt").write_text("plain\n", encoding="utf-8")

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        r = dir_id(a)
        await hub.handle({"type": "read_file", "root": r, "path": "README.md"})
        v1 = c.of("file_content")[-1]["version"]
        await hub.handle({"type": "save_file", "root": r, "path": "README.md", "text": "# A edited\n", "base_version": v1})
        saved = c.of("file_saved")[-1]
        (a / "README.md").write_bytes(b"# changed on disk\n")
        await hub.handle({"type": "save_file", "root": r, "path": "README.md", "text": "# mine\n",
                          "base_version": saved["version"]})
        conflict = _err(c)
        await hub.handle({"type": "read_file", "root": r, "path": ".claude/agents/mine.md"})
        av = c.of("file_content")[-1]
        await hub.handle({"type": "save_file", "root": r, "path": ".claude/agents/mine.md",
                          "text": "---\nname: Mine Agent\nmodel: gpt-9\ntools: Read, bash stuff\n---\nHi\n",
                          "base_version": av["version"]})
        invalid = _err(c)
        await hub.handle({"type": "save_file", "root": r, "path": "notes.txt", "text": "x", "base_version": None})
        view_only = _err(c)
        await hub.handle({"type": "list_backups", "root": r, "path": "README.md"})
        items = c.of("backups")[-1]["items"]
        await hub.handle({"type": "read_file", "root": r, "path": "README.md"})
        cur = c.of("file_content")[-1]["version"]
        await hub.handle({"type": "restore_backup", "root": r, "path": "README.md", "backup_id": items[0]["backup_id"]})
        return c, saved, conflict, av, invalid, view_only, items

    c, saved, conflict, av, invalid, view_only, items = asyncio.run(go())
    assert saved["backup_id"] and saved["applies"] == "now"
    assert conflict["code"] == "conflict" and conflict["current"]["text"] == "# changed on disk\n"
    assert av["validates_as"] == "agent" and av["applies"] == "new_sessions"
    assert invalid["code"] == "invalid" and "model" in invalid["message"] and "tools" in invalid["message"]
    assert view_only["code"] == "not_allowed"
    assert len(items) == 1 and items[0]["size"] == len("# A\n")
    assert (a / "README.md").read_text(encoding="utf-8") == "# A\n"           # restored the first version
    backups_root = Path(os.environ["LAUNCHPAD_HOME"]) / "backups"
    assert backups_root.is_dir() and not (a / ".launchpad-backups").exists()
    assert (a / ".claude" / "agents" / "mine.md").read_text(encoding="utf-8").startswith("---\nname: mine")


def test_plan_file_header_validated(tmp_path):
    a, b = _dirs(tmp_path)
    script_planner_writes_plan()

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        await hub.handle({"type": "user_message", "text": "go"})
        rel = hub.current.folder.rel(hub.current.folder.plan)
        await hub.handle({"type": "read_file", "root": dir_id(a), "path": rel})
        fc = c.of("file_content")[-1]
        broken = fc["text"].replace("- {n: 2,", "- {n: 7,")
        await hub.handle({"type": "save_file", "root": dir_id(a), "path": rel, "text": broken, "base_version": fc["version"]})
        return c, fc

    c, fc = asyncio.run(go())
    assert fc["validates_as"] == "plan" and _err(c)["code"] == "invalid" and "n must be 2" in _err(c)["message"]


def test_edited_agent_file_reaches_crew_list_and_new_sessions(tmp_path, monkeypatch):
    a, b = _dirs(tmp_path)
    agents = tmp_path / "agents-copy"
    shutil.copytree(crew.AGENTS_DIR, agents)
    monkeypatch.setattr(crew, "AGENTS_DIR", agents)
    fake.script("launchpad-planner", [[fake.say("hi")]])

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        rel = ".claude/agents/launchpad-planner.md"
        await hub.handle({"type": "read_file", "root": "app", "path": rel})
        fc = c.of("file_content")[-1]
        new = fc["text"].replace("You plan work with the user.", "You plan work with the user. CUSTOM LINE.")
        await hub.handle({"type": "save_file", "root": "app", "path": rel, "text": new, "base_version": fc["version"]})
        old_session = hub.current
        await hub.handle({"type": "new_session"})
        return hub, c, fc, old_session

    hub, c, fc, old = asyncio.run(go())
    assert fc["applies"] == "new_sessions" and fc["validates_as"] == "agent"
    assert c.of("file_saved")[-1]["applies"] == "new_sessions"
    planner = next(x for x in c.of("crew_list")[-1]["agents"] if x["role"] == "planner")
    assert "CUSTOM LINE." in planner["instructions"] and planner["root"] == "app" and planner["editable"]
    assert planner["path"].endswith("launchpad-planner.md") and planner["promotion"]["root"] == "app"
    assert "CUSTOM LINE." in hub.current.chat.agent.instructions                 # new session: new file
    assert "CUSTOM LINE." not in old.chat.agent.instructions                     # running session keeps its prompt
    assert "CUSTOM LINE." not in (crew.ROOT / ".claude" / "agents" / "launchpad-planner.md").read_text(encoding="utf-8")


def test_saves_keep_each_files_line_endings(tmp_path):
    a, b = _dirs(tmp_path)
    (a / "win.md").write_bytes(b"# Title\r\nline one\r\nline two\r\n")
    (a / "unix.md").write_bytes(b"# Title\nline one\n")

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        r = dir_id(a)
        for name, text in (("win.md", "# Title\nline ONE\nline two\nline three\n"), ("unix.md", "# Title\nline 1\n")):
            await hub.handle({"type": "read_file", "root": r, "path": name})
            v = c.of("file_content")[-1]["version"]
            await hub.handle({"type": "save_file", "root": r, "path": name, "text": text, "base_version": v})
        await hub.handle({"type": "save_file", "root": r, "path": "new.md", "text": "a\nb\n", "base_version": None})
        await hub.handle({"type": "list_backups", "root": r, "path": "win.md"})
        bid = c.of("backups")[-1]["items"][0]["backup_id"]
        await hub.handle({"type": "restore_backup", "root": r, "path": "win.md", "backup_id": bid})
        return c

    c = asyncio.run(go())
    assert (a / "unix.md").read_bytes() == b"# Title\nline 1\n"
    assert (a / "new.md").read_bytes() == b"a\nb\n"
    assert (a / "win.md").read_bytes() == b"# Title\r\nline one\r\nline two\r\n"       # restored, still CRLF
    saved = [e for e in c.of("file_saved") if e["path"] == "win.md"]
    assert len(saved) == 2 and not c.of("file_error")


def test_make_default_folder_via_set_settings(tmp_path):
    a, b = _dirs(tmp_path)

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        await hub.handle({"type": "set_settings", "patch": {"default_dir_id": dir_id(b)}})
        await hub.handle({"type": "set_settings", "patch": {"default_dir_id": "dnope"}})
        await hub.handle({"type": "new_session"})
        return hub, c

    hub, c = asyncio.run(go())
    ev = [e for e in c.of("settings") if any(d["is_default"] and d["dir_id"] == dir_id(b) for d in e["directories"])]
    assert ev and hub.default_dir == dir_id(b) and hub.current.folder.project == b.resolve()
    assert Store(tmp_path / "home" / "settings.json").default_id() == dir_id(b)
    assert any("not connected" in e["text"] for e in c.of("system"))


def test_fake_demo_edits_a_copy_of_the_app_files(tmp_path, monkeypatch):
    import tempfile
    from app import launch, planner
    real = {p.name: p.read_bytes() for p in crew.AGENTS_DIR.glob("*.md")}
    real_criteria = planner.CRITERIA_FILE.read_bytes()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    for name in ("APP_ROOT", "AGENTS_DIR"):
        monkeypatch.setattr(crew, name, getattr(crew, name))
    monkeypatch.setattr(planner, "CRITERIA_FILE", planner.CRITERIA_FILE)
    copy = launch.demo_app_root()
    a, b = _dirs(tmp_path)

    async def go():
        hub, c = await _hub(tmp_path, a, b)
        for rel in (".claude/agents/launchpad-planner.md", "app/planner-promotion.md"):
            await hub.handle({"type": "read_file", "root": "app", "path": rel})
            fc = c.of("file_content")[-1]
            await hub.handle({"type": "save_file", "root": "app", "path": rel, "text": fc["text"] + "\nDEMO EDIT\n",
                              "base_version": fc["version"]})
        return c

    c = asyncio.run(go())
    assert len(c.of("file_saved")) == 2
    assert b"DEMO EDIT" in (copy / ".claude" / "agents" / "launchpad-planner.md").read_bytes()
    assert b"DEMO EDIT" in (copy / "app" / "planner-promotion.md").read_bytes()
    assert {p.name: p.read_bytes() for p in (crew.ROOT / ".claude" / "agents").glob("*.md")} == real   # untouched
    assert (crew.ROOT / "app" / "planner-promotion.md").read_bytes() == real_criteria
