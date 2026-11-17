"""Offline pipeline tests with a stand-in writer (no model calls)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
MOCK = f'"{sys.executable}" "{REPO / "tests" / "mock_writer.py"}"'
sys.path.insert(0, str(SCRIPTS))

from store import OutputStore  # noqa: E402


@pytest.fixture()
def work(tmp_path):
    subprocess.run([sys.executable, str(REPO / "examples/make_examples.py"), str(tmp_path), "--broken"], check=True,
                   capture_output=True)
    return tmp_path


def gen(plan, *args, env=None):
    e = dict(os.environ, COMMENTARY_WRITER_CMD=MOCK, **(env or {}))
    p = subprocess.run([sys.executable, str(SCRIPTS / "generate.py"), str(plan), *args],
                       capture_output=True, text=True, env=e)
    return p.returncode, p.stdout + p.stderr


def rows(d):
    plan = json.loads((d / "commentary_shell.json").read_text())
    return OutputStore(plan, d).rows()


def outputs(d):
    return sorted((d / "commentary_outputs").glob("commentary_*.json"))


def test_report_one_output_file_per_run(work):
    d = work / "report_html"
    code, out = gen(d / "commentary_shell.json")
    assert code == 0, out
    assert "4 generated" in out
    assert len(outputs(d)) == 1
    # no per-run brief folders or run-log history
    assert not (d / "briefs").exists() and not (d / "runs").exists()
    assert not (d / "commentary_filled.json").exists()
    # the output file is the shell with commentary written into each unit
    data = json.loads(outputs(d)[0].read_text())
    assert data["snapshot"] is None
    assert [u["id"] for u in data["units"]] == [u["id"] for u in json.loads((d / "commentary_shell.json").read_text())["units"]]
    assert all(u["commentary"][0]["bullets"] for u in data["units"])
    # rerun with nothing to do: no new file
    code, out = gen(d / "commentary_shell.json")
    assert "0 generated, 4 reused" in out and "0 writer calls" in out and "No output file saved" in out
    assert len(outputs(d)) == 1
    # override one unit: one new, complete file
    code, out = gen(d / "commentary_shell.json", "--override", "volume")
    assert len(outputs(d)) == 2
    vs = [r["version"] for r in rows(d) if r["unit_id"] == "volume"]
    assert vs == [1, 2]
    # the whole generator was called, but only the named unit got a new version
    assert [r["version"] for r in rows(d) if r["unit_id"] == "channels"] == [1]
    newest = json.loads(outputs(d)[-1].read_text())
    assert {u["id"]: u["commentary"][0]["version"] for u in newest["units"]} == \
        {"volume": 2, "channels": 1, "backlog": 1, "sla": 1}


def test_retry_then_pass(work):
    d = work / "report_html"
    code, out = gen(d / "commentary_shell.json", env={"MOCK_BAD_FIRST": "1"})
    assert code == 0, out
    log = (d / "commentary_run.md").read_text()
    assert "Needed a retry | 2" in log  # first unit of each generator


def test_fail_after_retry_is_saved_failed_and_blank(work):
    d = work / "report_html"
    code, out = gen(d / "commentary_shell.json", env={"MOCK_ALWAYS_BAD": "1"})
    assert code == 1
    failed = [r for r in rows(d) if r["status"] == "failed"]
    assert {r["unit_id"] for r in failed} == {"volume", "backlog"}
    subprocess.run([sys.executable, str(SCRIPTS / "fill.py"), str(d / "commentary_shell.json")], check=True,
                   capture_output=True)
    filled = (d / "support_report_filled.html").read_text()
    assert "987654321" not in filled and "{{commentary" not in filled
    # failed units are retried on the next run
    code, out = gen(d / "commentary_shell.json")
    assert code == 0 and "2 generated" in out


def test_hand_edit_and_override_all_skips_it(work):
    d = work / "report_html"
    gen(d / "commentary_shell.json")
    subprocess.run([sys.executable, str(SCRIPTS / "edit.py"), str(d / "commentary_shell.json"), "sla",
                    "--bullet", "Edited by hand."], check=True, capture_output=True)
    assert len(outputs(d)) == 2  # the edit saved one new output file
    code, out = gen(d / "commentary_shell.json", "--override", "all")
    log = (d / "commentary_run.md").read_text()
    assert "Skipped hand edits | 1" in log
    sla = [r for r in rows(d) if r["unit_id"] == "sla"]
    assert sla[-1]["source"] == "edited"
    code, out = gen(d / "commentary_shell.json", "--use-version", "sla", "1")
    sla = [r for r in rows(d) if r["unit_id"] == "sla"]
    assert sla[-1]["version"] == 3 and sla[-1]["source"] == "generated"
    subprocess.run([sys.executable, str(SCRIPTS / "fill.py"), str(d / "commentary_shell.json")], check=True,
                   capture_output=True)
    assert "Edited by hand." not in (d / "support_report_filled.html").read_text()


def test_broken_plan_session_vs_batch(work):
    d = work / "broken_shell"
    code, out = gen(d / "commentary_shell.json")
    assert code == 2 and "Nothing generated" in out
    # remove the plan-level error, keep unit errors: batch fails units and continues
    plan = json.loads((d / "commentary_shell.json").read_text())
    (d / "page.md").write_text((d / "page.md").read_text().replace("{{commentary:ghost}}\n", ""))
    (d / "commentary_shell.json").write_text(json.dumps(plan))
    code, out = gen(d / "commentary_shell.json", "--batch")
    assert code == 1
    log = (d / "commentary_run.md").read_text()
    assert "- good" in log and "Generated | 1" in log
    assert "too_big" in log and "60 rows (limit 50)" in log


def test_dashboard_refresh_cycle(work):
    d = work / "dashboard_programmatic"
    plan = d / "commentary_shell.json"
    assert gen(plan, "--setup")[0] == 0
    assert (d / "run_commentary.py").exists()
    assert not outputs(d)  # setup saves no commentary
    code, out = gen(plan, "--batch")
    assert code == 0, out
    assert "7 generated" in out  # overview x1 + (2 units x 3 LOBs)
    sep = outputs(d)
    assert len(sep) == 1 and "commentary_2026-09_" in sep[0].name
    data = json.loads(sep[0].read_text())
    assert data["snapshot"] == "2026-09"
    lob = next(u for u in data["units"] if u["id"] == "lob_trend")
    assert lob["filters"] == ["paid_month", "line_of_business"]
    assert sorted(e["filters"]["line_of_business"] for e in lob["commentary"]) == ["Commercial", "Medicaid", "Medicare"]
    # refresh to October: a separate file for the new snapshot
    for f in (d / "snapshots/2026-10").iterdir():
        (d / "data" / f.name).write_bytes(f.read_bytes())
    code, out = gen(plan, "--batch")
    assert "as of 2026-10" in out and "7 generated" in out
    files = outputs(d)
    assert len(files) == 2 and any("commentary_2026-10_" in f.name for f in files)
    octo = json.loads(next(f for f in files if "2026-10" in f.name).read_text())
    assert octo["snapshot"] == "2026-10"
    assert all(e["filters"].get("paid_month") == "2026-10" for u in octo["units"] for e in u["commentary"])
    lob = next(u for u in octo["units"] if u["id"] == "lob_trend")
    assert all("(had prior)" in e["bullets"][0]["text"] for e in lob["commentary"]), \
        "use_prior should pass last period's bullets"
    # rerun: nothing new, no new file
    code, out = gen(plan, "--batch")
    assert "0 generated" in out and len(outputs(d)) == 2
    # restate October data: warn only
    p = d / "data/claims_by_lob.csv"
    p.write_text(p.read_text().replace("2026-10,Medicare,", "2026-10,Medicare,1").replace("\n2026-10", "\n2026-10", 1))
    code, out = gen(plan, "--batch")
    log = (d / "commentary_run.md").read_text()
    assert "0 generated" in out and "data restated" in log
    # combination cap
    cfg = REPO / "config.json"
    old = cfg.read_text()
    try:
        cfg.write_text(old.replace('"max_combinations": 50', '"max_combinations": 2'))
        code, out = gen(plan, "--batch", "--override", "all")
        assert "cap 2" in (d / "commentary_run.md").read_text()
    finally:
        cfg.write_text(old)


def test_dashboard_versions_status_and_runtime(work):
    from runtime import CommentaryRuntime
    d = work / "dashboard_programmatic"
    shell = d / "commentary_shell.json"
    gen(shell, "--batch")
    gen(shell, "--batch", "--override", "overview")
    files = outputs(d)
    assert len(files) == 2  # same snapshot rerun: a newer file for it
    newest = json.loads(files[-1].read_text())
    versions = {u["id"]: sorted(e["version"] for e in u["commentary"]) for u in newest["units"]}
    assert versions == {"overview": [2], "lob_trend": [1, 1, 1], "lob_categories": [1, 1, 1]}  # complete
    assert sorted(r["version"] for r in rows(d) if r["unit_id"] == "overview") == [1, 2]
    p = subprocess.run([sys.executable, str(SCRIPTS / "status.py"), str(shell)], capture_output=True, text=True)
    assert "| overview | 1 |" in p.stdout and "up to v2" in p.stdout and "Output files: 2" in p.stdout
    rt = CommentaryRuntime.from_outputs(shell)
    assert rt.lookup("lob_trend", {"paid_month": "2026-09", "line_of_business": "Medicare", "region": "West"})
    assert rt.lookup("lob_trend", {"paid_month": "2026-09", "line_of_business": "Nope"}) == []


def test_runtime_failed_refresh_shows_blank():
    from runtime import CommentaryRuntime
    ok = lambda a, v: {"unit_id": "u", "as_of": a, "version": v, "status": "ok", "bullets": [{"text": a}]}  # noqa: E731
    rows = [ok("2026-09", 1), {**ok("2026-10", 1), "status": "failed"}]
    rt = CommentaryRuntime({"u": []}, {"u": False}, rows)
    assert rt.lookup("u", {}) == []
    rows = [ok("2026-10", 1), {**ok("2026-10", 2), "status": "failed"}]
    assert CommentaryRuntime({"u": []}, {"u": False}, rows).lookup("u", {}) == []


def test_templated_covers_rejected(work):
    d = work / "report_html"
    shell = json.loads((d / "commentary_shell.json").read_text())
    shell["units"][0]["covers"] = "The trend for this period is {trend}"
    (d / "commentary_shell.json").write_text(json.dumps(shell))
    code, out = gen(d / "commentary_shell.json")
    assert code == 2 and "belong in code" in out
