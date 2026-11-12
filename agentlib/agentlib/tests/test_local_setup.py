"""Local setup file (setup/local.toml), sign-in resolution, status and the check command. Zero tokens: no Claude
process is started; all files are temp files with made-up values."""
import asyncio
import json

import pytest

from agentlib import (Agent, EngineUnavailable, SetupError, check_connection_sync, connection_status, fake,
                      local_setup)
from agentlib.check import main as check_main
from agentlib.connection import CHECK_AGENT
from agentlib.engines import claude as ce
from agentlib.engines.claude import LEAN_ENV, ClaudeSession
from agentlib.engines.claude_setup import ClaudeSetup

SECRET = "made-up-secret-not-real-123"


@pytest.fixture(autouse=True)
def _reset():
    fake.reset()
    yield
    fake.reset()


def _write_setup(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def _settings_file(tmp_path, data, name="settings.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _opts(agent):
    return ClaudeSession(agent, resume=None, fork=False, cost_base=0).options(resume=None)


SETTINGS = {
    "env": {"ANTHROPIC_BASE_URL": "https://gateway.example.test", "ANTHROPIC_AUTH_TOKEN": SECRET},
    "apiKeyHelper": "echo made-up-helper",
    # not sign-in: must NOT be passed through
    "permissions": {"allow": ["Bash(rm:*)"]}, "hooks": {"Stop": []}, "model": "opus",
    "enabledPlugins": {"x@y": True},
}


# ---------------------------------------------------------------- default: the Claude Code login
def test_default_is_login_and_adds_nothing(_isolated_local_setup):
    conn = local_setup.connection("claude")
    assert conn.method == "login" and conn.env == {} and conn.engine_settings == {} and not conn.problems
    o = _opts(Agent("a", include_ask_user=False))
    assert o.env == LEAN_ENV and o.settings is None


def test_no_file_at_all_is_fine(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTLIB_SETUP_FILE")
    monkeypatch.setattr(local_setup, "DEFAULT_FILE", tmp_path / "nothing-here.toml")
    st = connection_status("claude")
    assert st.method == "login" and st.setup_file is None and not [p for p in st.problems if "setup" in p]


def test_login_notes_env_vars_already_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    conn = local_setup.connection("claude")
    assert any("ANTHROPIC_API_KEY" in n for n in conn.notes) and SECRET not in " ".join(conn.notes)


# ---------------------------------------------------------------- settings-file pass-through
def test_settings_file_passes_only_sign_in_parts(tmp_path, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n')
    conn = local_setup.connection("claude")
    assert not conn.problems and conn.method == "settings-file"
    assert conn.env == SETTINGS["env"]
    assert conn.engine_settings == {"apiKeyHelper": "echo made-up-helper"}
    assert SECRET not in conn.summary and SECRET not in repr(conn)
    assert "ANTHROPIC_AUTH_TOKEN" in conn.summary and "apiKeyHelper" in conn.summary

    o = _opts(Agent("a", include_ask_user=False))
    assert o.env["ANTHROPIC_AUTH_TOKEN"] == SECRET and o.env["ANTHROPIC_BASE_URL"] == "https://gateway.example.test"
    assert o.env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"           # lean defaults still applied
    assert json.loads(o.settings) == {"apiKeyHelper": "echo made-up-helper"}   # nothing else from the file
    assert o.setting_sources == []                                   # still lean: the file is not loaded whole


def test_settings_file_default_location_and_relative_path(tmp_path, monkeypatch, _isolated_local_setup):
    cfg = tmp_path / "claude-config"
    cfg.mkdir()
    _settings_file(cfg, {"apiKeyHelper": "echo x"})
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    _write_setup(_isolated_local_setup, '[claude]\nauth = "settings-file"\n')
    assert local_setup.connection("claude").engine_settings == {"apiKeyHelper": "echo x"}

    _settings_file(tmp_path, {"env": {"ANTHROPIC_BASE_URL": "https://rel.example.test"}}, "rel.json")
    _write_setup(_isolated_local_setup, '[claude]\nauth = "settings-file"\nsettings_file = "rel.json"\n')
    assert local_setup.connection("claude").env == {"ANTHROPIC_BASE_URL": "https://rel.example.test"}


def test_settings_file_plus_env_section_overrides(tmp_path, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n'
                                        '[claude.env]\nANTHROPIC_BASE_URL = "https://override.example.test"\n')
    assert local_setup.connection("claude").env["ANTHROPIC_BASE_URL"] == "https://override.example.test"


# ---------------------------------------------------------------- explicit environment variables
def test_explicit_env_with_reference(monkeypatch, _isolated_local_setup):
    monkeypatch.setenv("MY_MADE_UP_TOKEN", SECRET)
    _write_setup(_isolated_local_setup, '[claude]\nauth = "env"\n[claude.env]\n'
                                        'ANTHROPIC_BASE_URL = "https://gw.example.test"\n'
                                        'ANTHROPIC_AUTH_TOKEN = "${MY_MADE_UP_TOKEN}"\n')
    conn = local_setup.connection("claude")
    assert not conn.problems and conn.method == "env"
    assert conn.env == {"ANTHROPIC_BASE_URL": "https://gw.example.test", "ANTHROPIC_AUTH_TOKEN": SECRET}
    assert SECRET not in conn.summary
    o = _opts(Agent("a", include_ask_user=False))
    assert o.env["ANTHROPIC_AUTH_TOKEN"] == SECRET and o.settings is None


# ---------------------------------------------------------------- the caller's env= wins
def test_caller_env_overrides_local_setup(tmp_path, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n')
    o = _opts(Agent("a", include_ask_user=False, env={"ANTHROPIC_BASE_URL": "https://caller.example.test",
                                                      "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "0"}))
    assert o.env["ANTHROPIC_BASE_URL"] == "https://caller.example.test"
    assert o.env["ANTHROPIC_AUTH_TOKEN"] == SECRET                   # untouched keys still come from the setup
    assert o.env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "0"


def test_local_env_cannot_undo_lean_defaults(_isolated_local_setup):
    _write_setup(_isolated_local_setup, '[claude]\nauth = "env"\n[claude.env]\nCLAUDE_CODE_DISABLE_CLAUDE_MDS = "0"\n')
    assert _opts(Agent("a", include_ask_user=False)).env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] == "1"


def test_list_models_uses_local_setup(tmp_path, monkeypatch, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n')
    seen = {}

    class StubClient:
        def __init__(self, opts):
            seen["opts"] = opts

        async def connect(self):
            return None

        async def get_server_info(self):
            return {"models": []}

        async def disconnect(self):
            return None

    monkeypatch.setattr(ce, "ClaudeSDKClient", StubClient)
    asyncio.run(ce.ClaudeEngine().list_models(env={"ANTHROPIC_BASE_URL": "https://caller.example.test"},
                                              timeout_s=5))
    o = seen["opts"]
    assert o.env["ANTHROPIC_AUTH_TOKEN"] == SECRET and o.env["ANTHROPIC_BASE_URL"] == "https://caller.example.test"
    assert json.loads(o.settings) == {"apiKeyHelper": "echo made-up-helper"}


# ---------------------------------------------------------------- missing / invalid setup -> clear messages
@pytest.mark.parametrize("text, expect", [
    ("[claude\nauth = 1", "not valid TOML"),
    ('[claude]\nauth = "sso"\n', 'is not one of "login", "settings-file", "env"'),
    ('[claude]\nauht = "login"\n', "unknown setting(s) auht"),
    ('[claude]\nauth = "env"\n', "no [claude.env] section"),
    ('[claude]\nauth = "env"\n[claude.env]\nANTHROPIC_AUTH_TOKEN = "${SURELY_NOT_SET_XYZ}"\n',
     "${SURELY_NOT_SET_XYZ}, which is not set"),
    ('[claude]\nauth = "login"\n[claude.env]\nANTHROPIC_BASE_URL = "https://x.example.test"\n',
     'set auth = "env"'),
    ('[claude]\nauth = "settings-file"\nsettings_file = "does-not-exist.json"\n', "does not exist"),
    ('claude = "login"\n', "must be a [claude] section"),
])
def test_bad_setup_gives_clear_message(text, expect, _isolated_local_setup):
    _write_setup(_isolated_local_setup, text)
    st = connection_status("claude")
    assert not st.ok and any(expect in p for p in st.problems), st.problems
    with pytest.raises(SetupError) as ei:
        _opts(Agent("a", include_ask_user=False))
    assert expect in str(ei.value) and "setup/claude-setup.md" in str(ei.value).replace("\\", "/")


def test_bad_settings_files(tmp_path, _isolated_local_setup):
    bad = tmp_path / "bad.json"
    bad.write_text('{"env": {"A": "' + SECRET + '",}', encoding="utf-8")
    empty = _settings_file(tmp_path, {"model": "opus", "permissions": {}}, "nosignin.json")
    for path, expect in [(bad, "is not valid JSON"), (empty, "has no sign-in settings")]:
        _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{path}\'\n')
        st = connection_status("claude")
        assert any(expect in p for p in st.problems) and SECRET not in " ".join(st.problems)


def test_setup_file_env_var_pointing_nowhere(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLIB_SETUP_FILE", str(tmp_path / "missing.toml"))
    assert any("does not exist" in p for p in connection_status("claude").problems)


def test_session_start_raises_setup_error_before_any_process(_isolated_local_setup):
    _write_setup(_isolated_local_setup, '[claude]\nauth = "sso"\n')

    async def go():
        async with Agent("a", include_ask_user=False).session():
            pass
    with pytest.raises(SetupError):
        asyncio.run(go())


# ---------------------------------------------------------------- status for apps
def test_status_shape_never_has_values(tmp_path, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n')
    st = connection_status("claude")
    assert st.engine == "claude" and st.method == "settings-file"
    assert st.env_names == ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"]
    assert st.setup_file == str(_isolated_local_setup) and st.setup_doc.replace("\\", "/").endswith("setup/claude-setup.md")
    assert SECRET not in json.dumps(st.to_dict())


def test_status_other_engines():
    assert connection_status("fake").ok and connection_status("fake").method == "none"
    assert any("not built yet" in p for p in connection_status("cursor").problems)
    with pytest.raises(EngineUnavailable):
        connection_status("no-such-engine")


def test_claude_fix_hints():
    s = ClaudeSetup()
    assert "sign in" in s.fix_for("Not logged in · Please run /login")
    assert "apiKeyHelper" in s.fix_for("Your apiKeyHelper script is failing")
    assert "gateway" in s.fix_for("turn timed out after 90s")
    assert s.fix_for("something nobody expected") is None


# ---------------------------------------------------------------- the check command (fake engine)
def test_check_success_on_fake(capsys):
    r = check_connection_sync("fake")
    assert r.ok and r.sent and r.model == "fake-small" and r.reply_text and r.error is None
    assert check_main(["--engine", "fake"]) == 0
    out = capsys.readouterr().out
    assert "RESULT: WORKS" in out and "fake-small" in out and "fake engine: no sign-in needed" in out


def test_check_failure_on_fake(capsys):
    fake.script(CHECK_AGENT, [[fake.fail("Not logged in · Please run /login")]])
    r = check_connection_sync("fake")
    assert not r.ok and r.sent and "Not logged in" in r.error and r.fix
    fake.script(CHECK_AGENT, [[fake.fail("Not logged in · Please run /login")]])
    assert check_main(["--engine", "fake"]) == 1
    out = capsys.readouterr().out
    assert "RESULT: FAILED. Not logged in" in out and "What to do:" in out


def test_check_not_set_up_sends_nothing(capsys, _isolated_local_setup):
    _write_setup(_isolated_local_setup, '[fake]\nauth = "bogus"\n')
    r = check_connection_sync("fake")
    assert not r.ok and not r.sent and "bogus" in r.error
    assert check_main(["--engine", "fake"]) == 1
    out = capsys.readouterr().out
    assert "RESULT: NOT SET UP. Nothing was sent." in out and "Problem:" in out
    with pytest.raises(SetupError):                                  # the fake engine mirrors Claude here
        Agent("a", engine="fake").ask_sync("hi")


def test_check_status_only(capsys):
    assert check_main(["--engine", "fake", "--status"]) == 0
    assert "RESULT: SET UP" in capsys.readouterr().out


def test_check_status_claude_never_prints_secrets(tmp_path, capsys, _isolated_local_setup):
    sf = _settings_file(tmp_path, SETTINGS)
    _write_setup(_isolated_local_setup, f'[claude]\nauth = "settings-file"\nsettings_file = \'{sf}\'\n')
    check_main(["--status"])
    out = capsys.readouterr().out
    assert SECRET not in out and "ANTHROPIC_AUTH_TOKEN" in out and "gateway.example.test" not in out


def test_check_unknown_engine(capsys):
    assert check_main(["--engine", "no-such-engine"]) == 1
    assert "unknown engine" in capsys.readouterr().out
