"""The only module that talks to a model. Two implementations of one small interface:

    engine = make_engine("claude" | "fake", ...)
    await engine.start(system_prompt)              # opens one conversation
    async for item in engine.send(message):        # str = text delta; the last item is a TurnResult
        ...
    await engine.close()

ClaudeEngine uses the Claude Agent SDK directly (owner-approved for this project instead of agentlib; moving
back is a change to this file only). It opens the leanest session Claude Code allows while keeping the normal
sign-in:
  - system prompt = ours only, from a file (--system-prompt-file; replaces Claude Code's own prompt)
  - no tools (--tools ""), no setting sources (--setting-sources=), no MCP (--strict-mcp-config, none given),
    no skills (--disable-slash-commands), no subagents, nothing saved (--no-session-persistence)
  - lowest effort (--effort low; thinking cannot be switched off on current models)
  - an empty temp working folder; CLAUDE.md, auto memory, git instructions and the background title request
    off by environment variable; 5-minute prompt cache instead of the 1-hour one
  - --setting-sources= also drops the sign-in parts of the user's settings file, so those parts (and only
    those) are passed on: credential helper keys via --settings, provider/gateway variables via the
    process environment. Nothing is stored.
FakeEngine replays scripted replies for tests and demos (zero tokens).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable

TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")

# Environment for the claude process: everything Claude Code would add that is not ours, off.
LEAN_ENV = {
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",          # no CLAUDE.md or memory files
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS": "1",
    "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1",      # skips the background small-model title request
}
# Sign-in parts of a Claude Code settings file that --setting-sources= would otherwise drop.
SIGNIN_SETTINGS_KEYS = ("apiKeyHelper", "awsAuthRefresh", "awsCredentialExport", "gcpAuthRefresh")
SIGNIN_ENV_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_", "AWS_", "GOOGLE_", "CLOUD_ML_", "VERTEX_",
                       "ANTHROPIC_VERTEX_", "AZURE_")
SIGNIN_ENV_NAMES = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "NODE_EXTRA_CA_CERTS",
                    "CLAUDE_CODE_CLIENT_CERT", "CLAUDE_CODE_CLIENT_KEY", "CLAUDE_CODE_CLIENT_KEY_PASSPHRASE")


class EngineError(Exception):
    """The engine could not run a turn (process died, sign-in, network). `result` = partial turn, if any."""

    def __init__(self, message: str, result: "TurnResult | None" = None):
        super().__init__(message)
        self.result = result


@dataclass
class TurnResult:
    text: str = ""
    usage: dict = field(default_factory=lambda: {k: 0 for k in TOKEN_KEYS})
    cost_usd: float | None = 0.0
    model: str | None = None
    api_calls: int = 0
    by_model: dict = field(default_factory=dict)     # model -> {tokens..., cost_usd}: shows side calls
    error: str | None = None                          # the model run ended badly (not an exception)


# ---- Claude --------------------------------------------------------------------------------------------
def signin_from_user_settings() -> tuple[dict, dict]:
    """(env, settings) holding only the sign-in parts of the user's Claude Code settings file."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        data = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    env = {k: str(v) for k, v in (data.get("env") or {}).items()
           if k.startswith(SIGNIN_ENV_PREFIXES) or k in SIGNIN_ENV_NAMES}
    settings = {k: data[k] for k in SIGNIN_SETTINGS_KEYS if k in data}
    return env, settings


class ClaudeEngine:
    name = "claude"

    def __init__(self, model: str | None = None, effort: str | None = "low",
                 max_budget_usd: float | None = None, cache_ttl: str | None = "5m"):
        self.model = model
        self.effort = effort
        self.max_budget_usd = max_budget_usd
        self.cache_ttl = cache_ttl
        self.info: dict = {}
        self._client = None
        self._dir: str | None = None
        self._totals: dict = {}          # running per-model totals reported by the CLI
        self._total_cost = 0.0

    def options(self, prompt_file: str, cwd: str):
        from claude_agent_sdk import ClaudeAgentOptions

        env, settings = signin_from_user_settings()
        env.update(LEAN_ENV)
        if self.cache_ttl:
            env["CLAUDE_CODE_PROMPT_CACHE_TTL"] = self.cache_ttl
        return ClaudeAgentOptions(
            system_prompt={"type": "file", "path": prompt_file},
            tools=[],
            setting_sources=[],
            strict_mcp_config=True,
            model=self.model,
            effort=self.effort,
            max_budget_usd=self.max_budget_usd,
            include_partial_messages=True,
            cwd=cwd,
            env=env,
            settings=json.dumps(settings) if settings else None,
            extra_args={"disable-slash-commands": None, "no-session-persistence": None},
        )

    async def start(self, system_prompt: str) -> None:
        from claude_agent_sdk import ClaudeSDKClient

        self._dir = tempfile.mkdtemp(prefix="whiteboard-agent-")
        prompt_file = os.path.join(self._dir, "..", os.path.basename(self._dir) + "-prompt.md")
        prompt_file = os.path.abspath(prompt_file)   # outside the (empty) working folder
        Path(prompt_file).write_text(system_prompt, encoding="utf-8")
        self._prompt_file = prompt_file
        try:
            self._client = ClaudeSDKClient(self.options(prompt_file, self._dir))
            await self._client.connect()
        except Exception as e:
            await self.close()
            raise EngineError(f"{type(e).__name__}: {e}") from None

    async def send(self, message: str) -> AsyncIterator[str | TurnResult]:
        from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, SystemMessage, TextBlock

        if self._client is None:
            raise EngineError("the session is not open")
        text: list[str] = []
        streamed = False
        try:
            await self._client.query(message)
            async for msg in self._client.receive_response():
                if isinstance(msg, StreamEvent):
                    ev = msg.event or {}
                    delta = ev.get("delta") or {}
                    if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        streamed = True
                        text.append(delta.get("text", ""))
                        yield delta.get("text", "")
                elif isinstance(msg, AssistantMessage) and not streamed:
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text.append(block.text)
                            yield block.text
                elif isinstance(msg, SystemMessage) and msg.subtype == "init":
                    d = msg.data or {}
                    self.info = {"model": d.get("model"), "tools": d.get("tools"),
                                 "mcp_servers": d.get("mcp_servers"), "agents": d.get("agents"),
                                 "skills": d.get("skills"), "slash_commands": d.get("slash_commands"),
                                 "plugins": d.get("plugins"), "cwd": d.get("cwd")}
                elif isinstance(msg, ResultMessage):
                    yield self._result(msg, "".join(text))
        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"{type(e).__name__}: {e}", TurnResult(text="".join(text))) from None

    def _result(self, msg, text: str) -> TurnResult:
        """Per-turn figures. The CLI reports running totals for the session (model_usage, total_cost_usd);
        this turn = the difference from the previous turn."""
        by_model, usage = {}, {k: 0 for k in TOKEN_KEYS}
        names = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
                 "cacheReadInputTokens": "cache_read_tokens", "cacheCreationInputTokens": "cache_write_tokens"}
        for model, mu in (msg.model_usage or {}).items():
            prev = self._totals.get(model, {})
            turn = {ours: int(mu.get(theirs) or 0) - prev.get(ours, 0) for theirs, ours in names.items()}
            turn["cost_usd"] = float(mu.get("costUSD") or 0) - prev.get("cost_usd", 0.0)
            self._totals[model] = {**{ours: int(mu.get(theirs) or 0) for theirs, ours in names.items()},
                                   "cost_usd": float(mu.get("costUSD") or 0)}
            if any(turn[k] for k in TOKEN_KEYS):
                by_model[model] = turn
                for k in TOKEN_KEYS:
                    usage[k] += turn[k]
        if not by_model and msg.usage:  # older CLIs: per-turn usage only
            u = msg.usage
            usage = {"input_tokens": int(u.get("input_tokens") or 0), "output_tokens": int(u.get("output_tokens") or 0),
                     "cache_read_tokens": int(u.get("cache_read_input_tokens") or 0),
                     "cache_write_tokens": int(u.get("cache_creation_input_tokens") or 0)}
        cost = None
        if msg.total_cost_usd is not None:
            cost = float(msg.total_cost_usd) - self._total_cost
            self._total_cost = float(msg.total_cost_usd)
        main = max(by_model, key=lambda m: by_model[m]["output_tokens"], default=None) or self.info.get("model")
        error = None
        if msg.is_error:
            error = "; ".join(msg.errors or []) or msg.result or f"the model run ended with {msg.subtype}"
        return TurnResult(text=text, usage=usage, cost_usd=cost, model=main, api_calls=int(msg.num_turns or 0),
                          by_model=by_model, error=error)

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        if self._dir:
            shutil.rmtree(self._dir, ignore_errors=True)
            try:
                os.remove(self._prompt_file)
            except (OSError, AttributeError):
                pass
            self._dir = None


# ---- Fake ----------------------------------------------------------------------------------------------
Reply = str | Callable[[str], str] | Exception


class FakeEngine:
    """Scripted replies, streamed in small chunks. Usage is estimated from text length (4 chars a token)
    with made-up prices, so the page shows plausible numbers. A script item that is an Exception (or a
    callable returning one) makes that turn fail with EngineError."""

    name = "fake"

    def __init__(self, replies: list[Reply] | Callable[[str], Reply] | None = None):
        self.replies = replies
        self.info = {"model": "fake engine", "tools": [], "mcp_servers": []}
        self.system_prompt = ""
        self.sent: list[str] = []
        self._turn = 0
        self._open = False

    async def start(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self._open = True

    def _next(self, message: str):
        r = self.replies
        if callable(r):
            reply = r(message)
        elif isinstance(r, list) and self._turn < len(r):
            reply = r[self._turn]
        else:
            reply = f"@say (fake) {message.splitlines()[-1][:80]}"
        if callable(reply) and not isinstance(reply, Exception):
            reply = reply(message)
        return reply

    async def send(self, message: str) -> AsyncIterator[str | TurnResult]:
        if not self._open:
            raise EngineError("the session is not open")
        fresh = self._turn == 0
        reply = self._next(message)
        self._turn += 1
        self.sent.append(message)
        if isinstance(reply, Exception):
            raise EngineError(str(reply), TurnResult(text="", usage=self._usage(message, "", fresh)))
        for i in range(0, len(reply), 40):
            yield reply[i:i + 40]
        usage = self._usage(message, reply, fresh)
        cost = (usage["input_tokens"] * 3 + usage["output_tokens"] * 15 + usage["cache_read_tokens"] * 0.3
                + usage["cache_write_tokens"] * 3.75) / 1_000_000
        yield TurnResult(text=reply, usage=usage, cost_usd=cost, model="fake engine", api_calls=1,
                         by_model={"fake engine": {**usage, "cost_usd": cost}})

    def _usage(self, message: str, reply: str, fresh: bool) -> dict:
        prompt = len(self.system_prompt) // 4
        return {"input_tokens": max(1, len(message) // 4), "output_tokens": max(1, len(reply) // 4),
                "cache_read_tokens": 0 if fresh else prompt, "cache_write_tokens": prompt if fresh else 0}

    async def close(self) -> None:
        self._open = False


def make_engine(name: str, **kw):
    if name == "fake":
        return FakeEngine(kw.get("replies"))
    return ClaudeEngine(model=kw.get("model"), effort=kw.get("effort", "low"),
                        max_budget_usd=kw.get("max_budget_usd"), cache_ttl=kw.get("cache_ttl", "5m"))
