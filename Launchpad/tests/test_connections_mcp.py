"""Settings > Connections (one test script per CLI tool) and the MCP library (store, secrets, tests, import, per-agent
servers at run time). Fake engine only, zero tokens: MCP tests use a scripted tester, except two that start the demo's
own tiny local server (no network, no model)."""
import asyncio
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

import agentlib
from agentlib import fake
from agentlib.engines import register_engine
from agentlib.fake.engine import FakeEngine

from app import connections, mcpimport, mcplib
from app.agents import crew
from app.agents.planner import choices
from app.connections import claude_code, cursor
from app.hub import Hub
from app.settings import Settings
from app.store import Store
from conftest import PLAN, Client, report, script_orchestrator_sequential

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- a fake engine that takes MCP servers
class McpFakeEngine(FakeEngine):
    """The fake engine with mcp_servers=True; records what every opened agent was given."""
    name = "fake_mcp"
    capabilities = dataclasses.replace(FakeEngine.capabilities, mcp_servers=True)
    opened: list = []

    def open(self, agent, *, resume, fork, cost_base):
        McpFakeEngine.opened.append((agent.name, dict(agent.mcp_servers)))
        return super().open(agent, resume=resume, fork=fork, cost_base=cost_base)


register_engine("fake_mcp", McpFakeEngine)


@pytest.fixture(autouse=True)
def _mcp_isolated(monkeypatch, tmp_path):
    McpFakeEngine.opened.clear()
    monkeypatch.setattr(mcpimport, "CLAUDE_HOME", tmp_path / "no-claude-home")    # never the real ~/.claude.json
    # harness choice -> the launch engine as is, so a fake_mcp launch never reaches the real Claude engine
    monkeypatch.setattr(choices, "engine_for", lambda harness, launch: launch)


def scripted_tester(results: dict):
    """TESTER replacement: server command or url -> {ok, error, tools}; records the configs it was given."""
    seen = []

    async def tester(config):
        seen.append(config)
        await asyncio.sleep(0)
        key = config.get("command") or config.get("url")
        return results.get(key, {"ok": False, "error": "unknown server"})
    tester.seen = seen
    return tester


def cmd(name, command, **env):
    return {"name": name, "kind": "command", "config": {"command": command, "args": [], "env": env}}


async def wait(cond, timeout=10.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("timed out")
        await asyncio.sleep(0.01)


# --------------------------------------------------------------------------- connections
def test_connection_list_comes_from_the_server():
    assert connections.listing() == [{"id": "claude_code", "name": "Claude Code"}, {"id": "cursor", "name": "Cursor"}]


def test_claude_code_three_steps_on_the_fake_engine(monkeypatch):
    monkeypatch.setattr(claude_code, "find_program", lambda: "/bin/claude")
    monkeypatch.setattr(claude_code, "program_version", lambda p: "2.1.0")
    ev = asyncio.run(connections.run("claude_code", "fake"))
    assert ev == {"type": "connection_test", "id": "claude_code", "installed": True, "version": "2.1.0",
                  "reachable": True, "usable": True, "detail": ev["detail"]}
    assert "fake engine" in ev["detail"]


def test_claude_code_unreachable_shows_the_error(monkeypatch):
    monkeypatch.setattr(claude_code, "find_program", lambda: "/bin/claude")
    monkeypatch.setattr(claude_code, "program_version", lambda p: "2.1.0")
    fake.script(agentlib.connection.CHECK_AGENT, [[fake.fail("Not logged in. Please run /login")]])
    ev = asyncio.run(connections.run("claude_code", "fake"))
    assert ev["installed"] and ev["reachable"] is False and ev["usable"] is False
    assert "Not logged in" in ev["detail"]


def test_claude_code_missing_sends_nothing(monkeypatch):
    monkeypatch.setattr(claude_code, "find_program", lambda: None)
    st = agentlib.ConnectionStatus(engine="claude", ok=False, method="login", summary="",
                                   problems=["the Claude Code program was not found (neither ...)"])
    monkeypatch.setattr(agentlib, "connection_status", lambda engine="claude": st)

    async def never(*a, **k):
        raise AssertionError("no request may be sent")
    monkeypatch.setattr(agentlib, "check_connection", never)
    ev = asyncio.run(connections.run("claude_code", "claude"))
    assert ev["installed"] is False and ev["usable"] is False and "not found" in ev["detail"]


def test_cursor_is_install_check_only(monkeypatch):
    monkeypatch.setattr(cursor, "find_program", lambda: None)
    ev = asyncio.run(connections.run("cursor", "claude"))
    assert ev["installed"] is False and ev["usable"] is False and ev["reachable"] is None
    monkeypatch.setattr(cursor, "find_program", lambda: "/bin/cursor-agent")
    monkeypatch.setattr(cursor, "program_version", lambda p: "2026.11.01")
    ev = asyncio.run(connections.run("cursor", "claude"))
    assert ev["installed"] is True and ev["version"] == "2026.11.01" and ev["usable"] is False
    assert "cannot use it yet" in ev["detail"]


@pytest.mark.parametrize("mod", [claude_code, cursor])
@pytest.mark.parametrize("raw, number", [("2.1.160 (Claude Code)", "2.1.160"), ("cursor-agent 2026.11.01-ab12c\n", "2026.11.01-ab12c"),
                                         ("v1.4.0", "1.4.0"), ("no number here", "no number here"), ("", None)])
def test_version_is_just_the_number(mod, raw, number, monkeypatch):
    assert mod.version_number(raw) == number

    class Out:                                            # what `<program> --version` printed
        stdout, stderr, returncode = raw, "", 0
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Out())
    assert mod.program_version("/bin/x") == number


def test_bundled_claude_code_version_is_the_number(monkeypatch):
    monkeypatch.setattr(claude_code, "find_program", lambda: None)
    st = agentlib.ConnectionStatus(engine="claude", ok=True, method="login", summary="",
                                   version="claude-agent-sdk 0.2.175 (bundled Claude Code 2.1.160)")
    monkeypatch.setattr(agentlib, "connection_status", lambda engine="claude": st)
    r = asyncio.run(claude_code.test("claude", request=False))
    assert r["installed"] is True and r["version"] == "2.1.160" and "bundled" in r["detail"]


@pytest.mark.parametrize("args", [["app/connections/cursor.py", "--json"],
                                  ["-m", "app.connections.claude_code", "--engine", "fake", "--json"]])
def test_each_script_runs_alone_from_a_terminal(args):
    out = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=120)
    r = json.loads(out.stdout)
    assert set(r) == {"installed", "version", "reachable", "usable", "detail"}, out.stderr


def test_hub_test_connection_message(project, monkeypatch):
    monkeypatch.setattr(cursor, "find_program", lambda: None)

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "test_connection", "id": "cursor"})
        await hub.handle({"type": "test_connection", "id": "nope"})
        return c
    c = asyncio.run(go())
    evs = c.of("connection_test")
    assert evs[0]["id"] == "cursor" and evs[0]["installed"] is False
    assert evs[1]["id"] == "nope" and "Unknown" in evs[1]["detail"]


# --------------------------------------------------------------------------- the library: store and secrets
def test_secrets_masked_and_kept_on_edit(tmp_path):
    lib = mcplib.McpLibrary(tmp_path / "mcp.json")
    lib.save({"name": "db", "kind": "command", "config": {
        "command": "db-mcp", "args": ["--api-key=abc123", "--token", "tok456", "--verbose"],
        "env": {"DB_PASS": "hunter22", "DB_HOST": "${DB_HOST}"}}})
    lib.save({"name": "api", "kind": "url", "config": {"url": "https://u:pw@api.example/mcp?key=k1&x=1",
                                                       "headers": {"Authorization": "Bearer zzz"}}})
    ev = lib.event()
    db, api = ev["servers"]
    assert db["config"] == {"command": "db-mcp", "args": ["--api-key=" + mcplib.MASK, "--token", mcplib.MASK,
                                                          "--verbose"],
                            "env": {"DB_PASS": mcplib.MASK, "DB_HOST": "${DB_HOST}"}}
    assert api["config"]["url"] == f"https://{mcplib.MASK}@api.example/mcp?key={mcplib.MASK}&x=1"
    assert api["config"]["headers"] == {"Authorization": mcplib.MASK}
    text = json.dumps(ev)
    assert not any(s in text for s in ("abc123", "tok456", "hunter22", "pw@", "k1", "zzz"))
    # edit: the page sends the masked values back unchanged -> the stored secrets stay
    lib.save({**db, "config": {**db["config"], "args": db["config"]["args"] + ["--extra"]}}, "db")
    lib.save({**api, "name": "api2"}, "api")
    stored = {s["name"]: s for s in lib.data()["servers"]}
    assert stored["db"]["config"]["args"] == ["--api-key=abc123", "--token", "tok456", "--verbose", "--extra"]
    assert stored["db"]["config"]["env"] == {"DB_PASS": "hunter22", "DB_HOST": "${DB_HOST}"}
    assert stored["api2"]["config"]["url"] == "https://u:pw@api.example/mcp?key=k1&x=1"
    assert stored["api2"]["config"]["headers"] == {"Authorization": "Bearer zzz"}
    # a hidden value with nothing stored behind it is refused
    with pytest.raises(ValueError, match="hidden value"):
        lib.save({"name": "new", "kind": "command", "config": {"command": "x", "env": {"K": mcplib.MASK}}})
    # the file lives in the given folder, readable as JSON, secrets kept there only
    assert json.loads((tmp_path / "mcp.json").read_text(encoding="utf-8"))["servers"][0]["name"] == "db"


def test_names_validation_rename_and_delete_follow_assignments(tmp_path):
    lib = mcplib.McpLibrary(None)
    for bad in ("", "has space", "agentlib", "x" * 70):
        with pytest.raises(ValueError):
            lib.save(cmd(bad, "x"))
    with pytest.raises(ValueError, match="command"):
        lib.save(cmd("a", " "))
    with pytest.raises(ValueError, match="URL"):
        lib.save({"name": "u", "kind": "url", "config": {"url": "ftp://x"}})
    lib.save(cmd("a", "a-mcp"))
    lib.save(cmd("b", "b-mcp"))
    with pytest.raises(ValueError, match="already"):
        lib.save(cmd("a", "other"))
    lib.set_agent("launchpad-builder", ["a", "b"])
    lib.set_agent("launchpad-planner", ["a"])
    with pytest.raises(ValueError, match="not in the library"):
        lib.set_agent("launchpad-builder", ["zzz"])
    lib.save(cmd("a2", "a-mcp"), "a")                           # rename follows into assignments
    assert lib.assignments() == {"launchpad-builder": ["a2", "b"], "launchpad-planner": ["a2"]}
    lib.remove("a2")                                            # delete clears it from every agent
    assert lib.assignments() == {"launchpad-builder": ["b"]}
    lib.set_agent("launchpad-builder", [])
    assert lib.assignments() == {}


def test_sse_kept_or_guessed():
    lib = mcplib.McpLibrary(None)
    lib.save({"name": "s", "kind": "url", "config": {"url": "https://x.example/sse"}})
    assert lib.get("s")["config"]["type"] == "sse"
    lib.save({"name": "h", "kind": "url", "config": {"url": "https://x.example/mcp"}})
    assert "type" not in lib.get("h")["config"]
    assert mcplib.agent_config(lib.get("h"))["type"] == "http"


def test_env_references_expanded_at_run_time(monkeypatch):
    monkeypatch.setenv("LP_TEST_TOKEN", "real-value")
    s = {"kind": "command", "config": {"command": "x", "args": ["--t=${LP_TEST_TOKEN}", "${LP_NOPE:-dflt}", "${LP_NOPE}"],
                                       "env": {"T": "${LP_TEST_TOKEN}"}}}
    c = mcplib.agent_config(s)
    assert c["args"] == ["--t=real-value", "dflt", "${LP_NOPE}"] and c["env"] == {"T": "real-value"}
    assert c["type"] == "stdio"


def test_library_file_beside_settings_never_in_the_project(project, tmp_path):
    store = Store(tmp_path / "home" / "settings.json")
    lib = mcplib.McpLibrary.beside(store)
    assert lib.path == tmp_path / "home" / "mcp.json"
    lib.save(cmd("a", "a-mcp", SECRET="v"))
    assert lib.path.is_file() and not list(project.rglob("mcp.json"))
    assert mcplib.McpLibrary.beside(Store(None)).path is None


# --------------------------------------------------------------------------- the websocket messages
def test_every_library_message(project, monkeypatch):
    tester = scripted_tester({"good-mcp": {"ok": True, "tools": ["a", "b", "c"]},
                              "bad-mcp": {"ok": False, "error": "could not start 'bad-mcp': program not found"}})
    monkeypatch.setattr(mcplib, "TESTER", tester)

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        await hub.handle({"type": "get_mcp"})
        first = c.of("mcp_library")[-1]
        await hub.handle({"type": "save_mcp_server", "server": cmd("good", "good-mcp", TOKEN="s3cret")})
        await hub.mcp_idle()
        after_add = list(c.of("mcp_library"))
        await hub.handle({"type": "save_mcp_server", "server": cmd("bad", "bad-mcp")})
        await hub.mcp_idle()
        await hub.handle({"type": "save_mcp_server", "server": cmd("good", "dup")})          # refused: name taken
        refused = c.of("mcp_library")[-1]
        await hub.handle({"type": "test_mcp_server", "name": "good"})
        await hub.mcp_idle()
        await hub.handle({"type": "set_agent_mcp", "agent": "launchpad-builder", "servers": ["good", "bad"]})
        assigned = c.of("mcp_library")[-1]
        await hub.handle({"type": "set_agent_mcp", "agent": "launchpad-builder", "servers": ["nope"]})
        await hub.handle({"type": "remove_mcp_server", "name": "bad"})
        removed = c.of("mcp_library")[-1]
        # edit with the masked value: the secret stays, and the edit is re-tested
        good = next(s for s in removed["servers"] if s["name"] == "good")
        await hub.handle({"type": "save_mcp_server", "server": {**good, "config": {**good["config"], "args": ["-v"]}},
                          "original_name": "good"})
        await hub.mcp_idle()
        return hub, c, first, after_add, refused, assigned, removed

    hub, c, first, after_add, refused, assigned, removed = asyncio.run(go())
    assert first["servers"] == [] and first["assignments"] == {}
    assert first["connections"] == connections.listing() and first["import_sources"] == [{"id": "claude_code",
                                                                                           "name": "Claude Code"}]
    statuses = [e["servers"][0]["status"] for e in after_add if e["servers"]]
    assert statuses[:3] == ["untested", "testing", "connected"]
    done = after_add[-1]["servers"][0]
    assert done["tool_count"] == 3 and done["detail"] == "3 tools" and done["tested_at"]
    assert done["config"]["env"] == {"TOKEN": mcplib.MASK}
    assert refused["error"] and "already" in refused["error"]
    bad = next(s for s in assigned["servers"] if s["name"] == "bad")
    assert bad["status"] == "failed" and "program not found" in bad["detail"] and bad["tool_count"] is None
    assert assigned["assignments"] == {"launchpad-builder": ["good", "bad"]}
    assert any("not in the library" in e["text"] for e in c.of("system"))
    assert removed["assignments"] == {"launchpad-builder": ["good"]}
    assert [s["name"] for s in removed["servers"]] == ["good"]
    assert hub.mcp.get("good")["config"]["env"] == {"TOKEN": "s3cret"}           # kept through the masked edit
    assert hub.mcp.get("good")["status"] == "connected" and tester.seen[-1]["args"] == ["-v"]
    assert all("s3cret" not in json.dumps(e) for e in c.events)                  # never sent to the page


def test_every_server_retested_in_the_background_at_start(project, monkeypatch, tmp_path):
    store = Store(tmp_path / "home" / "settings.json")
    lib = mcplib.McpLibrary.beside(store)
    lib.save(cmd("one", "good-mcp"))
    lib.save(cmd("two", "bad-mcp"))
    tester = scripted_tester({"good-mcp": {"ok": True, "tools": ["t"]}, "bad-mcp": {"ok": False, "error": "boom"}})
    monkeypatch.setattr(mcplib, "TESTER", tester)

    async def go():
        hub = Hub(Settings(project=project, engine="fake"), store=store)
        assert hub.mcp.path == lib.path
        c = Client(hub)
        await hub.connect(c)                                   # no server: the first connection starts it
        await wait(lambda: len(tester.seen) == 2)
        await hub.mcp_idle()
        await hub.connect(Client(hub))                         # once per launch
        await hub.mcp_idle()
        return c
    c = asyncio.run(go())
    assert len(tester.seen) == 2
    final = {s["name"]: s["status"] for s in c.of("mcp_library")[-1]["servers"]}
    assert final == {"one": "connected", "two": "failed"}
    assert any(s["status"] == "testing" for e in c.of("mcp_library") for s in e["servers"])


# --------------------------------------------------------------------------- import from Claude Code
def claude_setup(tmp_path, project) -> Path:
    home = tmp_path / "claude-home"
    home.mkdir()
    (home / ".claude.json").write_text(json.dumps({
        "mcpServers": {"shared": {"command": "user-shared"}, "userwide": {"type": "http", "url": "https://u.example/mcp",
                                                                         "headers": {"Authorization": "Bearer U-SECRET"}},
                       "socket": {"type": "ws", "url": "ws://x"}},
        "projects": {project.resolve().as_posix(): {"mcpServers": {
            "shared": {"type": "stdio", "command": "local-shared", "args": ["--api-key=L-SECRET"]}}}}}),
        encoding="utf-8")
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "shared": {"command": "project-shared"}, "events": {"type": "sse", "url": "https://e.example/sse"}}}),
        encoding="utf-8")
    return home


def test_claude_code_candidates_follow_its_precedence(tmp_path, project, monkeypatch):
    monkeypatch.setattr(mcpimport, "CLAUDE_HOME", claude_setup(tmp_path, project))
    found = {c["name"]: c for c in mcpimport.candidates("claude_code", [project])}
    assert set(found) == {"shared", "events", "userwide"}                    # ws is not importable
    assert found["shared"]["config"]["command"] == "local-shared" and found["shared"]["scope"] == "local"
    assert found["events"]["kind"] == "url" and found["events"]["config"]["type"] == "sse"
    assert found["userwide"]["scope"] == "user"
    view = mcpimport.page_view(list(found.values()), {"events"})
    text = json.dumps(view)
    assert "L-SECRET" not in text and "U-SECRET" not in text
    assert next(v for v in view if v["name"] == "events")["exists"] is True
    assert set(view[0]) >= {"name", "kind", "summary", "exists"}
    with pytest.raises(ValueError):
        mcpimport.candidates("nope", [project])


def test_import_messages(tmp_path, project, monkeypatch):
    monkeypatch.setattr(mcpimport, "CLAUDE_HOME", claude_setup(tmp_path, project))
    tester = scripted_tester({"local-shared": {"ok": True, "tools": ["x"]}})
    monkeypatch.setattr(mcplib, "TESTER", tester)

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        c = Client(hub)
        await hub.connect(c)
        hub.mcp.save(cmd("events", "mine"))
        await hub.handle({"type": "list_mcp_imports", "source": "claude_code"})
        listed = c.of("mcp_imports")[-1]
        await hub.handle({"type": "import_mcp_servers", "source": "claude_code", "names": ["shared", "events", "gone"]})
        await hub.mcp_idle()
        return hub, c, listed
    hub, c, listed = asyncio.run(go())
    assert listed["source"] == "claude_code"
    assert {s["name"]: s["exists"] for s in listed["servers"]} == {"shared": False, "events": True, "userwide": False}
    assert hub.mcp.get("shared")["config"]["args"] == ["--api-key=L-SECRET"]      # secret copied, never shown
    assert hub.mcp.get("shared")["status"] == "connected"                          # tested on add
    assert hub.mcp.get("events")["config"]["command"] == "mine"                    # existing one left alone
    note = next(e["text"] for e in c.of("system") if e["text"].startswith("MCP import"))
    assert "already in the library" in note and "gone" in note


# --------------------------------------------------------------------------- servers reach the agents
def library_with(hub, assignments: dict) -> None:
    hub.mcp.save(cmd("good", "good-mcp"))
    hub.mcp.set_result("good", {"ok": True, "tools": ["q"]})
    hub.mcp.save(cmd("bad", "bad-mcp"))
    hub.mcp.set_result("bad", {"ok": False, "error": "could not start 'bad-mcp'"})
    hub.mcp.save(cmd("fresh", "fresh-mcp"))                    # never tested
    for agent, names in assignments.items():
        hub.mcp.set_agent(agent, names)


def test_run_gets_only_passing_servers_and_warns_for_the_rest(project, monkeypatch):
    monkeypatch.setattr(mcplib, "TESTER", scripted_tester({}))
    script_orchestrator_sequential(1)
    fake.script("launchpad-builder", [[fake.call("submit_report", report())]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake_mcp"))
        hub.mcp_started = True                                 # no background re-test here
        c = Client(hub)
        await hub.connect(c)
        library_with(hub, {"launchpad-builder": ["good", "bad", "fresh"]})
        ls = hub.current
        await ls.save_plan({**PLAN, "steps": PLAN["steps"][:1]})
        await hub.handle({"type": "plan_approve", "session_id": ls.id})
        await wait(lambda: c.of("run_finished"))
        return hub, c, ls
    hub, c, ls = asyncio.run(go())
    fin = c.of("run_finished")[-1]
    assert fin["status"] == "done"                                       # a failing server never stops the run
    given = dict(McpFakeEngine.opened)
    assert set(given["launchpad-builder"]) == {"good"}
    assert given["launchpad-builder"]["good"] == {"type": "stdio", "command": "good-mcp", "args": [], "env": {}}
    assert given["launchpad-orchestrator"] == {}                         # nothing by default
    warns = [e for e in c.of("system") if e["text"].startswith("MCP server")]
    assert {w["text"].split("'")[1] for w in warns} == {"bad", "fresh"}
    assert all(w["session_id"] == ls.id for w in warns)
    assert "last test failed" in warns[0]["text"] + warns[1]["text"]
    step = ls.folder.read(ls.folder.step_path(1))
    assert "MCP server 'bad'" in step and "It runs without it" in step


def test_planner_and_cli_chat_treated_the_same(project, monkeypatch):
    monkeypatch.setattr(mcplib, "TESTER", scripted_tester({}))
    fake.script("launchpad-planner", [[fake.say("hello")]])
    fake.script("launchpad-pilot", [[fake.say("hi")]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake_mcp"))
        hub.mcp_started = True
        c = Client(hub)
        await hub.connect(c)
        library_with(hub, {"launchpad-planner": ["good", "bad"], "launchpad-pilot": ["good"]})
        await hub.handle({"type": "user_message", "text": "hi"})
        chat = await hub.chat_new()
        await chat.message("hello")
        return hub, c, chat
    hub, c, chat = asyncio.run(go())
    given = dict(McpFakeEngine.opened)
    assert set(given["launchpad-planner"]) == {"good"} and set(given["launchpad-pilot"]) == {"good"}
    warn = [e for e in c.of("system") if e["text"].startswith("MCP server 'bad'")]
    assert len(warn) == 1 and warn[0]["session_id"] == hub.current.id and "Planner" in warn[0]["text"]


def test_no_server_unless_assigned(project, monkeypatch):
    fake.script("launchpad-planner", [[fake.say("hello")]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake_mcp"))
        hub.mcp_started = True
        await hub.connect(Client(hub))
        library_with(hub, {})
        await hub.handle({"type": "user_message", "text": "hi"})
    asyncio.run(go())
    assert dict(McpFakeEngine.opened)["launchpad-planner"] == {}


def test_engine_without_mcp_skips_assignments_cleanly(project, monkeypatch):
    fake.script("launchpad-planner", [[fake.say("hello")]])

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        hub.mcp_started = True
        c = Client(hub)
        await hub.connect(c)
        library_with(hub, {"launchpad-planner": ["good", "bad"]})
        await hub.handle({"type": "user_message", "text": "hi"})
        return hub, c
    hub, c = asyncio.run(go())
    assert hub.current.chat.agent.mcp_servers == {}                         # fake cannot take them: none given
    assert not [e for e in c.of("system") if "MCP" in e["text"] or "error" in e["text"].lower()]
    assert c.of("planner_message")


def test_crew_cards_say_whether_the_engine_takes_mcp(project):
    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        return hub.crew_event()
    agents = asyncio.run(go())["agents"]
    assert all(a["mcp_supported"] is False and a["engine_label"] == "Fake engine (demo)" for a in agents)
    assert crew.mcp_supported("claude") is True and crew.mcp_supported("cursor") is False


# --------------------------------------------------------------------------- the real agentlib check + the demo
def test_real_check_on_the_demo_server(project):
    """agentlib's MCP check through the hub on the demo's own local server: start, list tools, stop (zero tokens)."""
    from app import demo
    server = demo.demo_mcp_servers()[0]

    async def go():
        hub = Hub(Settings(project=project, engine="fake"))
        hub.mcp_started = True
        await hub.connect(Client(hub))
        await hub.handle({"type": "save_mcp_server", "server": server})
        await hub.mcp_idle()
        return hub.mcp.get("notes")
    s = asyncio.run(go())
    assert s["status"] == "connected", s["detail"]
    assert s["tool_count"] == 3 and sorted(s["tools"]) == ["add_note", "list_notes", "search_notes"]


def test_demo_seeds_library_and_import_sample_in_temp_only(tmp_path, monkeypatch):
    from app import demo
    folder = tmp_path / "Demo shop"
    folder.mkdir()
    lib = mcplib.McpLibrary(tmp_path / "home" / "mcp.json")
    demo.seed_mcp(lib, [folder], tmp_path / "claude-home")
    assert lib.names() == ["notes", "glossary", "warehouse"]
    assert lib.assignments() == demo.DEMO_MCP_ASSIGNMENTS
    monkeypatch.setattr(mcpimport, "CLAUDE_HOME", tmp_path / "claude-home")
    names = {c["name"] for c in mcpimport.candidates("claude_code", [folder])}
    assert names == {"shop-db", "figma", "github", "notes"}
    lib.remove("notes")                                                    # edited in one demo run ...
    lib.save(cmd("mine", "x"))
    demo.seed_mcp(lib, [folder], tmp_path / "claude-home")                 # ... the next launch starts fresh
    assert lib.names() == ["notes", "glossary", "warehouse"]
    assert lib.assignments() == demo.DEMO_MCP_ASSIGNMENTS
    real = mcplib.McpLibrary(Path.home() / ".launchpad-test-never" / "mcp.json")
    demo.seed_mcp(real, [folder], tmp_path / "claude-home")                 # outside temp: nothing written
    assert not real.path.exists()
