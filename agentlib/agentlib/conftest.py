"""Test isolation: every test sees an empty local setup file (defaults), never the developer's setup/local.toml."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_local_setup(tmp_path, monkeypatch):
    empty = tmp_path / "agentlib-local-setup.toml"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("AGENTLIB_SETUP_FILE", str(empty))
    return empty
