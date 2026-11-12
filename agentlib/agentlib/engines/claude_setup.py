"""Claude sign-in: the [claude] section of the local setup file (setup/local.toml). Guide: setup/claude-setup.md.

SDK-free on purpose (never imports claude_agent_sdk), so status and the check can explain a missing install.

    auth = "login"          default. The ordinary Claude Code login; nothing is added. Like typing `claude`, any
                            ANTHROPIC_* variables already set on the computer still apply (they are noted)
    auth = "settings-file"  the sign-in parts of a Claude Code settings file (settings_file =, default
                            ~/.claude/settings.json, or $CLAUDE_CONFIG_DIR/settings.json): its "env" block goes into
                            the Claude process environment; the credential keys in SIGN_IN_KEYS (apiKeyHelper, ...)
                            go to Claude Code as --settings. Nothing else from the file is used
    auth = "env"            the variables in [claude.env]. A value "${NAME}" is taken from this computer's
                            environment, so secrets need not be written in the file
    [claude.env] may also be given with "settings-file": it adds to / overrides the file's env block.

The Claude engine merges: Connection.env, then its lean defaults, then the caller's Agent(env=) (caller wins).
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .base import Connection, EngineSetup

METHODS = ("login", "settings-file", "env")
SECTION_KEYS = ("auth", "settings_file", "env")
# Settings-file keys that decide how Claude Code signs in (besides "env"); passed through, nothing else is
SIGN_IN_KEYS = ("apiKeyHelper", "awsAuthRefresh", "awsCredentialExport", "gcpAuthRefresh", "forceLoginMethod",
                "forceLoginOrgUUID", "forceLoginGatewayUrl")
# Variables that change which credential Claude Code uses (noted in login mode when already set on the computer)
AUTH_ENV_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
                 "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def claude_config_dir() -> Path:
    named = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(os.path.expanduser(named)) if named else Path.home() / ".claude"


def default_settings_file() -> Path:
    return claude_config_dir() / "settings.json"


def _env_section(raw) -> tuple[dict[str, str], list[str]]:
    """[claude.env] -> (variables, problems). "${NAME}" is replaced from os.environ."""
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return {}, ["'env' must be a [claude.env] section of NAME = \"value\" lines"]
    env, problems = {}, []
    for k, v in raw.items():
        if isinstance(v, bool) or not isinstance(v, (str, int)):
            problems.append(f"[claude.env] {k} must be text in quotes")
            continue
        missing = [n for n in _REF.findall(str(v)) if n not in os.environ]
        if missing:
            problems.append(f"[claude.env] {k} refers to ${{{missing[0]}}}, which is not set on this computer")
            continue
        env[str(k)] = _REF.sub(lambda m: os.environ[m.group(1)], str(v))
    return env, problems


def read_settings_file(path: Path) -> tuple[dict[str, str], dict, list[str]]:
    """Sign-in parts of a Claude Code settings file -> (env block, SIGN_IN_KEYS present, problems).
    Problems never quote the file's contents."""
    if not path.is_file():
        return {}, {}, [f'auth = "settings-file" but {path} does not exist. Fix: set settings_file to your Claude '
                        f'Code settings file, or use auth = "login"']
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        return {}, {}, [f"{path} is not valid JSON ({e.msg}, line {e.lineno})"]
    except OSError as e:
        return {}, {}, [f"could not read {path}: {e.strerror or e}"]
    if not isinstance(data, dict):
        return {}, {}, [f"{path} is not a Claude Code settings file (expected a JSON object)"]
    problems = []
    env: dict[str, str] = {}
    block = data.get("env")
    if block is not None and not isinstance(block, dict):
        problems.append(f'the "env" entry in {path} is not an object of NAME: "value" pairs')
    elif block:
        env = {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in block.items()}
    settings = {k: data[k] for k in SIGN_IN_KEYS if k in data}
    if not env and not settings and not problems:
        problems.append(f'{path} has no sign-in settings (no "env" block and none of {", ".join(SIGN_IN_KEYS)}). '
                        f'If you sign in with the normal Claude Code login, use auth = "login"')
    return env, settings, problems


def _login_notes() -> list[str]:
    present = [k for k in AUTH_ENV_VARS if os.environ.get(k)]
    if present:
        return [f"{', '.join(present)} {'is' if len(present) == 1 else 'are'} set on this computer, which changes "
                f"how Claude Code signs in or where it sends requests (same as typing `claude` here). "
                f"agentlib.use_login_only() removes ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL "
                f"for one app"]
    if sys.platform != "darwin" and not (claude_config_dir() / ".credentials.json").is_file():
        return [f"no saved Claude Code login found in {claude_config_dir()}; if the check fails, run `claude` in a "
                f"terminal once and sign in"]
    return []


class ClaudeSetup(EngineSetup):
    doc = "setup/claude-setup.md"
    section_keys = SECTION_KEYS
    check_model = "haiku"

    def __init__(self, name: str = "claude"):
        super().__init__(name)

    def resolve(self, section: dict, *, base: Path | None = None) -> Connection:
        problems: list[str] = []
        unknown = sorted(set(section) - set(SECTION_KEYS))
        if unknown:
            problems.append(f"[claude] has unknown setting(s) {', '.join(unknown)}; allowed: auth, settings_file, "
                            f"[claude.env]")
        auth = section.get("auth", "login")
        if auth not in METHODS:
            problems.append(f'[claude] auth = {auth!r} is not one of "login", "settings-file", "env"')
            return Connection("claude", str(auth), "(invalid setup)", problems=problems)
        extra_env, env_problems = _env_section(section.get("env"))
        problems += env_problems

        if auth == "login":
            if section.get("env"):
                problems.append('[claude.env] is filled in but auth = "login"; set auth = "env" to use those '
                                'variables, or delete the section')
            notes = _login_notes()
            if "settings_file" in section:
                notes.append('settings_file is ignored unless auth = "settings-file"')
            return Connection("claude", "login", "your Claude Code login (the same sign-in as typing `claude` in a "
                              "terminal)", problems=problems, notes=notes)

        if auth == "env":
            if not section.get("env"):
                problems.append('auth = "env" but there is no [claude.env] section with variables')
            names = ", ".join(sorted(extra_env)) or "(none)"
            return Connection("claude", "env", f"environment variables from the local setup file: {names}",
                              env=extra_env, problems=problems)

        raw = section.get("settings_file")
        if raw is not None and not isinstance(raw, str):
            problems.append("[claude] settings_file must be a path in quotes")
            raw = None
        if raw:
            path = Path(os.path.expandvars(os.path.expanduser(raw)))
            if not path.is_absolute() and base is not None:
                path = base / path
        else:
            path = default_settings_file()
        env, settings, file_problems = read_settings_file(path)
        problems += file_problems
        env.update(extra_env)
        parts = []
        if env:
            parts.append("environment variables " + ", ".join(sorted(env)))
        if settings:
            parts.append(", ".join(settings))
        return Connection("claude", "settings-file", f"sign-in settings from {path}: " + ("; ".join(parts) or "none"),
                          env=env, engine_settings=settings, problems=problems)

    def prerequisites(self) -> list[str]:
        if sys.version_info < (3, 11):
            return [f"Python 3.11 or newer is needed (this is {sys.version.split()[0]})"]
        spec = importlib.util.find_spec("claude_agent_sdk")
        if spec is None or not spec.origin:
            return ["the Claude Agent SDK (Python package claude-agent-sdk) is not installed in this Python "
                    f"({sys.executable}). Fix: in the agentlib folder run: python -m pip install -e ."]
        exe = "claude.exe" if sys.platform == "win32" else "claude"
        if not (Path(spec.origin).parent / "_bundled" / exe).is_file() and not shutil.which("claude"):
            return ["the Claude Code program was not found (neither the copy bundled with claude-agent-sdk nor "
                    "`claude` on PATH). Fix: python -m pip install --force-reinstall claude-agent-sdk, or install "
                    "Claude Code: https://code.claude.com/docs/en/setup"]
        return []

    def version(self) -> str:
        try:
            v = importlib.metadata.version("claude-agent-sdk")
        except importlib.metadata.PackageNotFoundError:
            return "claude-agent-sdk not installed"
        cli = "?"
        spec = importlib.util.find_spec("claude_agent_sdk")
        if spec and spec.origin:
            f = Path(spec.origin).parent / "_cli_version.py"
            m = re.search(r"__cli_version__\s*=\s*['\"]([^'\"]+)['\"]", f.read_text(encoding="utf-8")) \
                if f.is_file() else None
            cli = m.group(1) if m else "?"
        return f"claude-agent-sdk {v} (bundled Claude Code {cli})"

    def fix_for(self, error: str) -> str | None:
        e = (error or "").lower()
        if "apikeyhelper" in e or "api key helper" in e:
            return ("your apiKeyHelper command failed. Run that command by hand in a terminal: it must print a key. "
                    "See setup/claude-setup.md")
        if any(s in e for s in ("not logged in", "/login", "login expired", "invalid api key", "authentication",
                                "unauthorized", "401", "403", "oauth", "credential", "forbidden")):
            return ("Claude refused the sign-in. Normal login: run `claude` in a terminal and sign in, then retry. "
                    'Company setup in Claude Code\'s settings.json: set auth = "settings-file" in setup/local.toml. '
                    "See setup/claude-setup.md")
        if "not found" in e and ("cli" in e or "claude code" in e):
            return "install Claude Code or reinstall claude-agent-sdk (see setup/claude-setup.md, step 1)"
        if "timed out" in e or "timeout" in e:
            return ("no answer in time. Claude Code retries network errors, so this usually means a wrong gateway "
                    "address (ANTHROPIC_BASE_URL), a proxy, or no network. Try `claude -p hi` in a terminal")
        if "credit" in e or "billing" in e or "quota" in e:
            return "the account has no credit or hit a limit; check billing / usage with whoever runs your account"
        if "model" in e and any(s in e for s in ("not found", "not available", "invalid", "does not exist",
                                                 "not allowed")):
            return "the test model is not available to you; run the check with --model <a model you can use>"
        if "rate" in e and "limit" in e:
            return "rate limited; wait a little and run the check again"
        return None
