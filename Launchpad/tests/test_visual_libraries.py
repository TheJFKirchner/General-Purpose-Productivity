"""Visualizer libraries on the fake engine: the library argument, availability detection (bundled, installed in the
folder's .venv or Launchpad's own environment, not installed), the "styled like" fallback label, path safety for
installed files, the /vendor/lib route and library-aware validation."""
import asyncio
import os

import pytest
from fastapi.testclient import TestClient

from agentlib import fake

from app import demo
from app.agents.visualizer import libraries, visuals
from app.agents.planner.planner import SHOW_VISUALS_SCHEMA, planner_tools
from app.server import create_app
from app.settings import Settings
from app.agents.visualizer.libraries import LIB_PART_SEPARATOR, available_libraries, choose_library, library_files
from app.agents.visualizer.visuals import VisualError, validate

BUNDLED = ["echarts", "chartjs", "d3"]
PLOTLY_JS = b"/**\n* plotly.js v9.9.9\n*/\n" + b"var Plotly={};" * 200
BOKEH_JS = b"/*!\n * Copyright (c) Anaconda, Inc., and Bokeh Contributors\n */\n" + b"var Bokeh={};" * 200
BOKEH_API = b"'use strict';\n/* bokeh api */\n" + b"Bokeh.Plotting={};" * 100


@pytest.fixture
def no_env_libs(monkeypatch):
    """Launchpad's own environment has neither Plotly nor Bokeh (whatever this machine has installed)."""
    monkeypatch.setattr(libraries, "_launchpad_site_dirs", lambda: [])


def _install(site_packages, which=("plotly", "bokeh")):
    if "plotly" in which:
        p = site_packages / "plotly" / "package_data"
        p.mkdir(parents=True, exist_ok=True)
        (p / "plotly.min.js").write_bytes(PLOTLY_JS)
    if "bokeh" in which:
        b = site_packages / "bokeh" / "server" / "static" / "js"
        b.mkdir(parents=True, exist_ok=True)
        (b / "bokeh.min.js").write_bytes(BOKEH_JS)
        (b / "bokeh-api.min.js").write_bytes(BOKEH_API)


# ---------------------------------------------------------------- availability
def test_bundled_libraries_are_always_available(project, no_env_libs):
    assert available_libraries(project) == BUNDLED
    for key in BUNDLED:
        files = library_files(key, project)
        assert files and all(f.is_file() and f.parent == libraries.VENDOR for f in files)
        assert (libraries.VENDOR / f"{'CHARTJS' if key == 'chartjs' else key.upper()}-LICENSE").is_file()
    assert library_files("plotly", project) is None and library_files("nope", project) is None


def test_installed_in_the_folders_venv_windows_and_posix_layouts(project, tmp_path, no_env_libs):
    _install(project / ".venv" / "Lib" / "site-packages", ("plotly",))
    assert available_libraries(project) == BUNDLED + ["plotly"]
    _install(project / ".venv" / "lib" / "python3.12" / "site-packages", ("bokeh",))
    assert available_libraries(project) == BUNDLED + ["plotly", "bokeh"]
    assert [f.name for f in library_files("bokeh", project)] == ["bokeh.min.js", "bokeh-api.min.js"]
    other = tmp_path / "other"
    other.mkdir()
    assert available_libraries(other) == BUNDLED                      # another folder: not installed there


def test_installed_in_launchpads_own_environment(project, tmp_path, monkeypatch):
    sp = tmp_path / "env" / "site-packages"
    _install(sp, ("plotly",))
    monkeypatch.setattr(libraries, "_launchpad_site_dirs", lambda: [sp])
    assert available_libraries(project) == BUNDLED + ["plotly"]
    assert available_libraries(None) == BUNDLED + ["plotly"]
    assert library_files("plotly", project)[0] == (sp / "plotly" / "package_data" / "plotly.min.js").resolve()


def test_installed_files_get_path_and_content_checks(project, tmp_path, no_env_libs):
    pkg = project / ".venv" / "Lib" / "site-packages" / "plotly" / "package_data"
    pkg.mkdir(parents=True)
    js = pkg / "plotly.min.js"
    for bad in (b"<!doctype html><html>plotly</html>" + b" " * 2000,      # HTML, not JavaScript
                b"/* some other library */" + b"x" * 2000,               # does not name its library
                b"/* plotly */"):                                       # too small
        js.write_bytes(bad)
        assert library_files("plotly", project) is None
    js.unlink()
    pkg.mkdir(exist_ok=True)
    js.mkdir()                                                          # a folder with the file's name
    assert library_files("plotly", project) is None
    js.rmdir()
    outside = tmp_path / "elsewhere" / "plotly" / "package_data"        # outside the connected folder
    outside.mkdir(parents=True)
    (outside / "plotly.min.js").write_bytes(PLOTLY_JS)
    link = project / ".venv" / "Lib" / "site-packages" / "plotly"
    for p in sorted(link.rglob("*"), reverse=True):
        p.rmdir() if p.is_dir() else p.unlink()
    link.rmdir()
    try:
        os.symlink(outside.parent, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        try:                                                            # Windows without symlink rights: a junction
            import _winapi
            _winapi.CreateJunction(str(outside.parent), str(link))
        except (ImportError, OSError):
            pytest.skip("no symlinks or junctions on this machine")
    assert (link / "package_data" / "plotly.min.js").is_file()
    assert library_files("plotly", project) is None                     # resolved path leaves the folder


def test_libraries_note_for_the_planners_first_message(project, no_env_libs):
    assert libraries.libraries_note(project) == ("Visual libraries for this folder (show_visuals library): "
                                               "ECharts (default), Chart.js, D3.")
    _install(project / ".venv" / "Lib" / "site-packages", ("plotly",))
    assert libraries.libraries_note(project).endswith("ECharts (default), Chart.js, D3, Plotly.")


# ---------------------------------------------------------------- choosing a library
@pytest.mark.parametrize("asked,key", [("Chart.js", "chartjs"), ("chartjs", "chartjs"), ("d3.js", "d3"),
                                       ("D3", "d3"), ("Apache ECharts", "echarts"), ("echarts", "echarts")])
def test_names_are_matched_to_bundled_libraries(project, no_env_libs, asked, key):
    c = choose_library(asked, project)
    assert (c.asked, c.drawn_with, c.note) == (key, key, None)


def test_not_asked_means_echarts(project, no_env_libs):
    c = choose_library(None, project)
    assert (c.asked, c.drawn_with, c.note, c.available) == (None, "echarts", None, tuple(BUNDLED))
    assert choose_library("  ", project).asked is None


@pytest.mark.parametrize("asked,shown", [("matplotlib", "matplotlib"), ("seaborn", "seaborn"),
                                         ("Recharts", "Recharts"), ("plotly", "Plotly"), ("bokeh", "Bokeh")])
def test_unavailable_or_non_browser_libraries_fall_back_with_a_label(project, no_env_libs, asked, shown):
    c = choose_library(asked, project)
    assert c.drawn_with == "echarts" and c.note == f"drawn in ECharts, styled like {shown}"
    assert c.styled_like == shown


def test_installed_plotly_is_used_when_asked(project, no_env_libs):
    _install(project / ".venv" / "Lib" / "site-packages", ("plotly",))
    c = choose_library("Plotly", project)
    assert (c.asked, c.drawn_with, c.note) == ("plotly", "plotly", None) and "plotly" in c.available


def test_odd_library_names_are_cleaned(project, no_env_libs):
    c = choose_library('<b>"ggplot2"</b>' + "x" * 80, project)
    assert "<" not in c.note and '"' not in c.note and len(c.asked) <= libraries.MAX_LIBRARY_NAME


# ---------------------------------------------------------------- the planner tool and the sets
def test_tool_takes_an_optional_library_and_never_changes(project):
    a = planner_tools(None)
    tool = next(t for t in a if t.name == "show_visuals")
    assert SHOW_VISUALS_SCHEMA["required"] == ["brief", "options"] and "library" in SHOW_VISUALS_SCHEMA["properties"]
    assert "ECharts" in tool.description and "styled like" in tool.description
    again = next(t for t in planner_tools(None) if t.name == "show_visuals")
    assert again.description == tool.description                      # fixed text: no folder-specific parts


def _run_sets(harness, calls, visual=None):
    h = harness()
    seen_by_planner, got = [], []
    fake.script("launchpad-planner", [[fake.call("show_visuals", c) for c in calls] + [fake.say("Coming up.")]]
                + [lambda m: seen_by_planner.append(m) or [fake.say("ok")]] * 3)
    fake.script("launchpad-visual", [lambda m: got.append(m) or (visual or demo.visual_turn)(m)])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "show me"})
        await h.wait(lambda: _done(c, len(calls)))
        return hub, c

    hub, c = asyncio.run(go())
    return hub, c, got, seen_by_planner


def _last_sets(c):
    out = {}
    for e in c.of("visual_set"):
        out[e["set_id"]] = e
    return out


def _done(c, n_sets):
    sets = _last_sets(c)
    return len(sets) == n_sets and all(o["status"] != "rendering" for s in sets.values() for o in s["options"])


def test_library_argument_reaches_the_visual_agent_and_the_events(harness, project, no_env_libs):
    hub, c, got, _ = _run_sets(harness, [
        {"brief": "Trend", "options": ["Line"]},
        {"brief": "Channels", "options": ["Doughnut"], "library": "Chart.js"},
        {"brief": "Sections", "options": ["Bubble chart"], "library": "d3"},
    ])
    v1, v2, v3 = _last_sets(c).values()
    assert (v1["library"], v1["drawn_with"], v1["library_note"]) == (None, "echarts", None)
    assert (v2["library"], v2["drawn_with"], v2["library_note"]) == ("chartjs", "chartjs", None)
    assert (v3["library"], v3["drawn_with"]) == ("d3", "d3")
    for s in (v1, v2, v3):
        assert s["libraries"] == BUNDLED
        assert all(o["drawn_with"] == s["drawn_with"] and o["status"] == "ready" for o in s["options"])
    assert any("Library: ECharts (global `echarts`, already loaded)" in m and "Option to draw: Line" in m for m in got)
    assert any("Library: Chart.js (global `Chart`, already loaded)" in m for m in got)
    assert any("Library: D3 (global `d3`, already loaded)" in m for m in got)
    assert "new Chart(" in v2["options"][0]["html"] and "d3.select(" in v3["options"][0]["html"]
    acks = [e["summary"] for e in c.of("activity") if e["tool"] == "show_visuals"]
    assert acks                                                        # the tool calls are in the feed
    saved = (project / v2["options"][0]["path"]).read_text(encoding="utf-8")
    assert "Chart.js as the global `Chart`" in saved.splitlines()[0]
    snap_sets = hub.current.visuals.snapshot()
    assert snap_sets[1]["drawn_with"] == "chartjs" and snap_sets[1]["libraries"] == BUNDLED


def test_fallback_is_drawn_in_echarts_and_labelled(harness, project, no_env_libs):
    replies = []
    orig = visuals.VisualBoard.create

    async def spy(self, brief, labels, library=None):
        r = await orig(self, brief, labels, library)
        replies.append(r)
        return r

    visuals.VisualBoard.create = spy
    try:
        hub, c, got, _ = _run_sets(harness, [{"brief": "Weekly visitors", "options": ["Line with markers", "Bar"],
                                              "library": "matplotlib"},
                                             {"brief": "Same in Plotly", "options": ["Line"], "library": "Plotly"}])
    finally:
        visuals.VisualBoard.create = orig
    v1, v2 = _last_sets(c).values()
    assert (v1["library"], v1["drawn_with"]) == ("matplotlib", "echarts")
    assert v1["library_note"] == "drawn in ECharts, styled like matplotlib"
    assert (v2["library"], v2["drawn_with"], v2["library_note"]) == ("plotly", "echarts",
                                                                     "drawn in ECharts, styled like Plotly")
    assert "plotly" not in v2["libraries"]
    assert all(o["status"] == "ready" and "echarts.init" in o["html"] for o in v1["options"] + v2["options"])
    assert any("styled like matplotlib: copy matplotlib's look in ECharts" in m for m in got)
    assert "matplotlib is not available here, so they are drawn in ECharts, styled like matplotlib" in replies[0]
    saved = (project / v1["options"][0]["path"]).read_text(encoding="utf-8").splitlines()[0]
    assert "styled like matplotlib" in saved and saved.startswith("<!--") and saved.endswith("-->")


def test_installed_library_is_used_for_real(harness, project, no_env_libs):
    _install(project / ".venv" / "Lib" / "site-packages", ("plotly", "bokeh"))
    hub, c, got, _ = _run_sets(harness, [{"brief": "Visitors", "options": ["Line"], "library": "plotly"},
                                         {"brief": "Visitors", "options": ["Bar"], "library": "Bokeh"}])
    v1, v2 = _last_sets(c).values()
    assert v1["drawn_with"] == "plotly" and "Plotly.newPlot(" in v1["options"][0]["html"]
    assert v2["drawn_with"] == "bokeh" and "Bokeh.Plotting" in v2["options"][0]["html"]
    assert v1["libraries"] == BUNDLED + ["plotly", "bokeh"]


def test_wrong_library_in_the_fragment_is_rejected_then_retry_works(harness, project, no_env_libs):
    calls = {"n": 0}

    def visual(msg):
        calls["n"] += 1
        if calls["n"] == 1:                                          # draws ECharts although Chart.js was asked
            return demo.visual_turn(msg.replace("Library: Chart.js", "Library: ECharts"))
        return demo.visual_turn(msg)

    hub, c, got, _ = _run_sets(harness, [{"brief": "Channels", "options": ["Doughnut"], "library": "chartjs"}],
                               visual=visual)
    o = _last_sets(c)["v1"]["options"][0]
    assert o["status"] == "failed" and "uses ECharts, but this option is drawn with Chart.js" in o["error"]


def test_each_visual_drawn_counts_one_use(harness, project, no_env_libs):
    hub, c, got, _ = _run_sets(harness, [{"brief": "A", "options": ["Bar", "Line"]},
                                         {"brief": "B", "options": ["Colour palette"], "library": "seaborn"}])
    uses = [e["uses"] for e in c.of("agent_uses") if e["name"] == "launchpad-visual"]
    assert uses[-1] == 3


def test_first_planner_message_lists_the_folders_libraries(harness, project, no_env_libs):
    h = harness()
    seen = []
    fake.script("launchpad-planner", [lambda m: seen.append(m) or [fake.say("hi")]])

    async def go():
        hub, c = await h.start()
        await hub.handle({"type": "user_message", "text": "hello"})

    asyncio.run(go())
    assert "Visual libraries for this folder (show_visuals library): ECharts (default), Chart.js, D3." in seen[0]


# ---------------------------------------------------------------- validation
CHARTJS_OK = '<div><canvas id="c"></canvas><script>new Chart(document.getElementById("c"),{type:"bar"});</script></div>'


@pytest.mark.parametrize("html,drawn,why", [
    ('<div id="c"></div><script>echarts.init(document.getElementById("c"))</script>', "chartjs", "uses ECharts"),
    (CHARTJS_OK, "echarts", "uses Chart.js"),
    ('<div id="d"></div><script>d3.select("#d")</script>', "plotly", "uses D3"),
    ('<div><script>Plotly.newPlot("p",[])</script></div>', "d3", "uses Plotly"),
    ('<div><script>d3.csv("data.csv")</script></div>', "d3", "network call"),
    ('<div><script>d3.json("/api")</script></div>', "d3", "network call"),
    ('<div><script src="chart.umd.min.js"></script></div>', "chartjs", "the library is provided"),
])
def test_validation_knows_the_sets_library(html, drawn, why):
    with pytest.raises(VisualError, match=why):
        validate(html, drawn)


def test_validation_accepts_the_right_library_and_plain_design_html():
    assert validate(CHARTJS_OK, "chartjs") == CHARTJS_OK
    assert validate(demo.sample_visual("Colour palette"), "echarts").startswith("<div")
    assert validate(demo.sample_visual("Hero card"), "chartjs").startswith("<div")
    for lib, key in (("ECharts", "echarts"), ("Chart.js", "chartjs"), ("D3", "d3"), ("Plotly", "plotly"),
                     ("Bokeh", "bokeh")):
        for label in ("Line with markers", "Bar", "Bubble chart", "Doughnut"):
            validate(demo.sample_visual(label, library=lib), key)
    assert len(demo.sample_visual("Bars with labels", library="D3")) < visuals.MAX_HTML


# ---------------------------------------------------------------- the /vendor/lib route
def _client(project):
    app = create_app(1234, "secret", Settings(project=project, engine="fake"))
    return app, TestClient(app)


def test_bundled_libraries_are_served_without_the_code(project):
    app, client = _client(project)
    for key, marker in (("echarts", b"echarts"), ("chartjs", b"Chart.js"), ("d3", b"d3js.org")):
        r = client.get(f"/vendor/lib/{key}.js")
        assert r.status_code == 200 and r.headers["content-type"].startswith("application/javascript")
        assert r.headers["x-content-type-options"] == "nosniff" and marker in r.content[:2000]
    assert client.get("/vendor/lib/nope.js").status_code == 404
    assert client.get("/vendor/lib/..%2Fserver.js").status_code == 404
    assert client.get("/vendor/echarts.min.js").status_code == 200       # the older path still works


def test_installed_libraries_need_the_code_and_a_connected_folder(project, no_env_libs):
    app, client = _client(project)
    did = app.state.hub.default_dir
    assert client.get(f"/vendor/lib/plotly.js?dir={did}&code=secret").status_code == 404    # not installed
    _install(project / ".venv" / "Lib" / "site-packages")
    assert client.get(f"/vendor/lib/plotly.js?dir={did}").status_code == 403
    assert client.get(f"/vendor/lib/plotly.js?dir={did}&code=wrong").status_code == 403
    assert client.get("/vendor/lib/plotly.js?dir=not-connected&code=secret").status_code == 404
    assert client.get("/vendor/lib/plotly.js?code=secret").status_code == 404     # no dir: Launchpad's env only
    r = client.get(f"/vendor/lib/plotly.js?dir={did}&code=secret")
    assert r.status_code == 200 and r.content == PLOTLY_JS and "access-control-allow-origin" not in r.headers
    r = client.get(f"/vendor/lib/bokeh.js?dir={did}&code=secret")
    assert r.status_code == 200 and r.content.split(LIB_PART_SEPARATOR.encode()) == [BOKEH_JS, BOKEH_API]
