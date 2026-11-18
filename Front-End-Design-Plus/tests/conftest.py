import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

SAMPLE_CSV = "region,month,sales,active\nNorth,2026-01,120,true\nSouth,2026-01,95.5,false\nNorth,2026-02,130,true\n"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    # Never open a browser; every test uses the fake engine (zero tokens).
    monkeypatch.setenv("WHITEBOARD_NO_OPEN", "1")
    monkeypatch.delenv("WHITEBOARD_DEBUG_USAGE", raising=False)
    yield


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "data.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    return p
