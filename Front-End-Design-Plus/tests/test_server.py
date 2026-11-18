"""The launcher and the HTTP server, on the fake engine with the built-in demo script (zero tokens)."""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from conftest import PROJECT
from agentlib import fake

from whiteboard import cli, data, server
from whiteboard.agent import AGENT_NAME


def start(csv_file, out, *extra):
    args = cli.parse_args(["--data", str(csv_file), "--library", "echarts", "--out", str(out), "--fake",
                           "--no-open", *extra])
    app = cli.build(args)
    app.start(port=0)
    t = threading.Thread(target=app.serve, args=(False,), daemon=True)
    t.start()
    return app, t


def get(app, path):
    with urllib.request.urlopen(app.url.rstrip("/") + path, timeout=10) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def post(app, path, body, headers=None):
    req = urllib.request.Request(app.url.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.headers.get("Content-Type"), r.read().decode("utf-8")


def sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_session_data_chat_save_done(tmp_path, csv_file):
    out = tmp_path / "out"
    app, thread = start(csv_file, out)
    try:
        status, ctype, body = get(app, "/api/session")
        s = json.loads(body)
        assert status == 200 and ctype.startswith("application/json")
        assert s["library"] == "echarts" and s["style"] == "" and s["cards"] == [] and s["engine"] == "fake"
        assert set(s) == {"library", "columns", "style", "cards", "saved", "chat", "row_count", "engine",
                          "round", "usage", "model"}
        assert s["round"] == 0 and s["model"] == "fake engine" and s["usage"]["turns"] == 0
        assert s["chat"] == []
        assert s["columns"] == [{"name": "region", "type": "string"}, {"name": "month", "type": "date"},
                                {"name": "sales", "type": "number"}, {"name": "active", "type": "boolean"}]
        rows = json.loads(get(app, "/api/data")[2])
        assert len(rows) == 3
        assert rows[1] == {"region": "South", "month": "2026-01", "sales": 95.5, "active": False}
        assert rows[0]["sales"] == 120 and isinstance(rows[0]["sales"], int)

        ctype, text = post(app, "/api/chat", {"message": "show me sales"})
        assert ctype.startswith("text/event-stream")
        events = sse(text)
        kinds = [k for k, _ in events]
        assert kinds[-1] == "done" and kinds.count("card") == 2 and "text" in kinds
        assert all(k == d["type"] for k, d in events)
        cards = [d for k, d in events if k == "card"]
        assert [c["id"] for c in cards] == ["G1", "G2"] and cards[1]["library"] == "html"

        _, text = post(app, "/api/chat", {"message": "try G1 as a line"})
        it = [d for k, d in sse(text) if k == "card"][0]
        assert it["id"] == "G3" and it["parent"] == "G1"

        fix = json.loads(post(app, "/api/card-error", {"id": "G3", "error": "ReferenceError: x"})[1])
        assert fix["fixed"] and fix["card"]["id"] == "G3"
        again = json.loads(post(app, "/api/card-error", {"id": "G3", "error": "ReferenceError: x"})[1])
        assert again["fixed"] is False

        saved = json.loads(post(app, "/api/save", {"id": "G1"})[1])
        assert saved["ok"] and (out / "G1.json").is_file()
        assert json.loads(post(app, "/api/delete", {"id": "G2"})[1])["ok"]
        bad = json.loads(post(app, "/api/save", {"id": "G2"})[1])
        assert bad["ok"] is False and "not on the board" in bad["error"]
        s = json.loads(get(app, "/api/session")[2])
        assert [(c["id"], c["saved"]) for c in s["cards"]] == [("G1", True), ("G3", False)]
        roles = [m["role"] for m in s["chat"]]
        assert roles == ["user", "agent", "user", "agent", "agent"]          # last one: the fix note
        assert s["chat"][0]["text"] == "show me sales" and "Fixed G3" in s["chat"][4]["text"]

        post(app, "/api/save", {"id": "G3"})
        un = json.loads(post(app, "/api/unsave", {"id": "G3"})[1])
        assert un["ok"] and un["saved"] == ["G1"] and not (out / "G3.json").exists()
        assert [x["id"] for x in json.loads((out / "result.json").read_text(encoding="utf-8"))["saved"]] == ["G1"]
        assert app.board.get("G3") is not None                                # the card stays
        assert json.loads(post(app, "/api/heartbeat", {})[1]) == {"ok": True}

        with pytest.raises(urllib.error.HTTPError) as e:  # another site cannot drive the page
            post(app, "/api/save", {"id": "G1"}, {"Origin": "http://evil.example"})
        assert e.value.code == 403

        done = json.loads(post(app, "/api/done", {})[1])
        assert done["ok"] and done["done"] is True and [x["id"] for x in done["saved"]] == ["G1"]
        thread.join(10)
        assert not thread.is_alive(), "server should stop after Done"
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        assert result["library"] == "echarts" and result["saved"][0]["title"]
    finally:
        if thread.is_alive():
            app.stop()


def test_existing_becomes_g1_then_its_saved_variant_seeds_a_fresh_launch(tmp_path, csv_file):
    existing = tmp_path / "existing.js"
    existing.write_text("lib.init(el).setOption({});", encoding="utf-8")
    out = tmp_path / "out"
    app, thread = start(csv_file, out, "--existing", str(existing), "--style", "Navy, no gridlines")
    try:
        s = json.loads(get(app, "/api/session")[2])
        g1 = s["cards"][0]
        assert [c["id"] for c in s["cards"]] == ["G1"] and g1["code"].startswith("lib.init")
        assert g1["round"] == 0 and g1["title"] == "Current visual" and s["round"] == 0
        assert s["style"] == "Navy, no gridlines"
        # No ID named: the demo agent, like the brief, starts from the current visual.
        _, text = post(app, "/api/chat", {"message": "make it horizontal"})
        events = sse(text)
        new = [d for k, d in events if k == "card"]
        assert [(c["id"], c["parent"], c["round"]) for c in new] == [("G2", "G1", 1)]
        done = events[-1][1]
        assert done["round"] == 1 and done["usage"]["turns"] == 1 and done["model"] == "fake engine"
        post(app, "/api/save", {"id": "G2"})
        post(app, "/api/done", {})
        thread.join(10)
    finally:
        if thread.is_alive():
            app.stop()
    saved = out / "G2.json"
    before = saved.read_text(encoding="utf-8")

    # Relaunching on the same folder is refused: nothing is loaded or overwritten.
    r = run_cli("--data", str(csv_file), "--library", "echarts", "--out", str(out), "--no-open")
    assert r.returncode == 2 and "new, empty output folder" in r.stderr and "--existing" in r.stderr
    assert saved.read_text(encoding="utf-8") == before

    # The saved visual comes back only through --existing, unchanged, as the round-0 current visual,
    # on a fresh board: no old cards, no chat, usage at zero.
    app2, thread2 = start(csv_file, tmp_path / "out2", "--existing", str(saved))
    try:
        s = json.loads(get(app2, "/api/session")[2])
        recipe = json.loads(before)
        assert [(c["id"], c["round"], c["title"], c["code"]) for c in s["cards"]] == [
            ("G1", 0, recipe["title"], recipe["code"])]
        assert s["chat"] == [] and s["round"] == 0 and s["usage"]["turns"] == 0
        _, text = post(app2, "/api/chat", {"message": "in navy"})
        assert [(d["id"], d["parent"], d["round"]) for k, d in sse(text) if k == "card"] == [("G2", "G1", 1)]
    finally:
        app2.stop()
    assert saved.read_text(encoding="utf-8") == before


def test_static_files_and_traversal(tmp_path, csv_file):
    app, thread = start(csv_file, tmp_path / "out")
    try:
        status, ctype, body = get(app, "/")
        assert status == 200 and ctype.startswith("text/html")
        with pytest.raises(urllib.error.HTTPError) as e:
            get(app, "/vendor/..%2F..%2Fwhiteboard%2Fcli.py")
        assert e.value.code in (403, 404)
        with pytest.raises(urllib.error.HTTPError) as e:
            get(app, "/api/nope")
        assert e.value.code == 404
    finally:
        app.stop()


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "whiteboard", *args], cwd=PROJECT, capture_output=True,
                          text=True, timeout=60, env={**os.environ, "WHITEBOARD_FAKE": "1", **(env or {})})


def test_unsupported_library_exits_nonzero_with_message(tmp_path, csv_file):
    r = run_cli("--data", str(csv_file), "--library", "matplotlib", "--out", str(tmp_path / "out"))
    assert r.returncode == 2
    assert "Library 'matplotlib' is not supported" in r.stderr and "echarts" in r.stderr
    assert not (tmp_path / "out").exists()


def test_library_aliases_and_bad_data(tmp_path, csv_file):
    assert cli.normalise_library("Vega-Lite") == "vegalite" and cli.normalise_library("Chart.js") == "chartjs"
    r = run_cli("--data", str(tmp_path / "missing.csv"), "--library", "plotly", "--out", str(tmp_path / "o"))
    assert r.returncode == 2 and "Data file not found" in r.stderr


def test_json_data_types(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps([{"a": 1, "b": "x", "c": "2026-01-02", "d": True},
                             {"a": 2.5, "b": None, "c": "2026-01-03T10:00:00", "e": "late key"}]), encoding="utf-8")
    t = data.load(p)
    assert t.columns == [{"name": "a", "type": "number"}, {"name": "b", "type": "string"},
                         {"name": "c", "type": "date"}, {"name": "d", "type": "boolean"},
                         {"name": "e", "type": "string"}]
    assert t.rows[0]["e"] is None and len(t.samples()) == 2


def wait_stopped(thread, seconds=10):
    thread.join(seconds)
    return not thread.is_alive()


def test_heartbeat_keeps_alive_then_silence_ends_with_done_false(tmp_path, csv_file, monkeypatch):
    monkeypatch.setenv("WHITEBOARD_IDLE_S", "0.6")
    out = tmp_path / "out"
    app, thread = start(csv_file, out)
    try:
        get(app, "/api/session")                       # the page connects
        post(app, "/api/chat", {"message": "sales"})
        post(app, "/api/save", {"id": "G1"})
        for _ in range(6):                             # 1.2 s of heartbeats: well past the 0.6 s limit
            time.sleep(0.2)
            post(app, "/api/heartbeat", {})
        assert thread.is_alive()
        assert wait_stopped(thread), "server should stop once the page goes silent"
        assert app.ended_by.startswith("the page was silent")
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        assert result["done"] is False and [x["id"] for x in result["saved"]] == ["G1"]
        # Unsaved cards are simply gone: only the saved visual and result.json remain.
        assert sorted(p.name for p in out.iterdir()) == ["G1.json", "result.json"]
    finally:
        if thread.is_alive():
            app.stop()


def test_running_agent_turn_counts_as_activity(tmp_path, csv_file, monkeypatch):
    monkeypatch.setenv("WHITEBOARD_IDLE_S", "0.5")
    app, thread = start(csv_file, tmp_path / "out")
    fake.reset()
    fake.script(AGENT_NAME, [lambda msg: time.sleep(1.5) or [fake.say("slow reply")]])
    try:
        _, text = post(app, "/api/chat", {"message": "take your time"})   # 1.5 s with no other request
        assert [k for k, _ in sse(text)][-1] == "done"
        assert app.ended_by is None and thread.is_alive()
        assert wait_stopped(thread)                                        # then silence ends it
    finally:
        if thread.is_alive():
            app.stop()


def test_no_page_within_connect_window_ends_session(tmp_path, csv_file, monkeypatch):
    monkeypatch.setenv("WHITEBOARD_CONNECT_S", "0.5")
    out = tmp_path / "out"
    app, thread = start(csv_file, out)
    assert wait_stopped(thread)
    assert app.ended_by.startswith("no page connected")
    assert json.loads((out / "result.json").read_text(encoding="utf-8"))["done"] is False


def test_launcher_exits_on_its_own_with_result_line(tmp_path, csv_file):
    out = tmp_path / "out"
    r = run_cli("--data", str(csv_file), "--library", "d3", "--out", str(out), "--no-open",
                env={"WHITEBOARD_CONNECT_S": "1"})
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert "Stopped without Done: no page connected" in r.stdout
    assert lines[-1] == f"RESULT: {out.resolve() / 'result.json'}"
    assert json.loads((out / "result.json").read_text(encoding="utf-8"))["done"] is False


def test_opaque_origin_frames_can_read_vendor_and_data(tmp_path, csv_file):
    """Sealed card frames send Origin: null (or none). GETs are never filtered by origin."""
    app, thread = start(csv_file, tmp_path / "out")
    try:
        for headers in ({"Origin": "null"}, {}):
            req = urllib.request.Request(app.url + "api/data", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                assert r.status == 200 and len(json.loads(r.read())) == 3
        vendor_files = sorted(server.VENDOR.glob("*.js")) if server.VENDOR.is_dir() else []
        if vendor_files:
            req = urllib.request.Request(app.url + "vendor/" + vendor_files[0].name, headers={"Origin": "null"})
            with urllib.request.urlopen(req, timeout=10) as r:
                assert r.status == 200 and r.headers["Access-Control-Allow-Origin"] == "*"
                assert r.headers["Content-Type"].startswith("text/javascript")
        with pytest.raises(urllib.error.HTTPError) as e:   # but a frame cannot POST
            post(app, "/api/save", {"id": "G1"}, {"Origin": "null"})
        assert e.value.code == 403
    finally:
        app.stop()
