import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from agentlib import fake  # noqa: E402  (registers the fake engine)

SAMPLE_CSV = "region,month,sales,active\nNorth,2026-01,120,true\nSouth,2026-01,95.5,false\nNorth,2026-02,130,true\n"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    # Never read a personal agentlib setup file; never open a browser; always the fake engine.
    empty = tmp_path / "agentlib-local.toml"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("AGENTLIB_SETUP_FILE", str(empty))
    monkeypatch.setenv("WHITEBOARD_NO_OPEN", "1")
    fake.reset()
    yield
    fake.reset()


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    return p
