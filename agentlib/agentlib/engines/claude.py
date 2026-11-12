"""Claude engine: the ONLY module that knows claude-agent-sdk option shapes and message types.

- One ClaudeSDKClient (one `claude` process) per session; a single worker task owns it (the SDK client
  must be used from the task that connected it), so callers can use a Session from any task
- lean setup: setting_sources=[], strict MCP, no slash commands, CLAUDE.md/auto-memory off, only listed tools,
  custom system prompt (long prompts go through a temp file: Windows ~32K argv limit)
- project setup: claude_code system prompt preset (+ instructions appended), user/project/local settings,
  native skills, all built-ins unless tools narrows them
- Permissions: listed tools are pre-approved; anything else -> agent.on_permission, or denied if none
- ask_user / ends_turn: a PostToolUse hook returns continue=False after a successful call (no further API call)
- Lean skills: Read is added if missing, and a PreToolUse hook limits it to the listed skill folders
- Cost: ResultMessage.total_cost_usd is cumulative per conversation -> per-turn cost is the delta
- After a failure/timeout the process is dropped; the next turn reconnects with resume=session_id. The raised
  AgentError carries .reply: the partial turn (text/tool calls so far, usage summed from the assistant
  messages seen, cost_usd 0 because cost only arrives with the final ResultMessage)
- Session.info comes from the CLI's init SystemMessage (tools offered, MCP servers, model)
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
import tempfile
import uuid
import warnings
from pathlib import Path

import claude_agent_sdk as sdk
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, HookMatcher,
                              PermissionResultAllow, PermissionResultDeny, PermissionUpdate, RateLimitEvent,
                              ResultMessage, StreamEvent, SystemMessage, TextBlock, ToolResultBlock, ToolUseBlock,
                              UserMessage, create_sdk_mcp_server)
from claude_agent_sdk import tool as sdk_tool
from claude_agent_sdk.types import PermissionRuleValue

from .. import skills as skills_mod
from ..errors import AgentError, ConversationMissing
from ..events import Done, RateLimit, Text, TextDelta, ToolCall, ToolResult
from ..permissions import PermissionRequest, normalize
from ..reply import Reply, Usage
from ..session import SessionInfo
from ..tools import full_name, short_name
from .base import Capabilities, Engine, EngineSession, TurnState

ARGV_PROMPT_LIMIT = 30_000          # chars; above this the system prompt goes through a file
LEAN_ENV = {
    "ENABLE_TOOL_SEARCH": "false",              # few tools: load them all up front
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
}
_END = object()
# Pre-approved tools skipping can_use_tool is the design (only unlisted tools reach on_permission)
warnings.filterwarnings("ignore", category=sdk.CanUseToolShadowedWarning)


def sdk_version() -> str:
    try:
        from claude_agent_sdk._cli_version import __cli_version__
    except Exception:  # noqa: BLE001
        __cli_version__ = "?"
    return f"claude-agent-sdk {sdk.__version__} (bundled Claude Code {__cli_version__})"


def _num(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def normalize_usage(u: dict | None) -> Usage:
    u = u or {}
    cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    return Usage(input_tokens=_num(u.get("input_tokens")), output_tokens=_num(u.get("output_tokens")),
                 cache_read_tokens=_num(u.get("cache_read_input_tokens")),
                 cache_write_tokens=_num(u.get("cache_creation_input_tokens")),
                 cache_write_5m_tokens=_num(cc.get("ephemeral_5m_input_tokens")),
                 cache_write_1h_tokens=_num(cc.get("ephemeral_1h_input_tokens")))


def error_text(e: BaseException) -> str:
    if isinstance(e, sdk.CLINotFoundError):
        return f"Claude Code CLI not found ({e})"
    s = str(e).strip()
    return s.splitlines()[0][:300] if s else type(e).__name__


def _content_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    for c in content:
        if isinstance(c, dict):
            parts.append(str(c.get("text", "")) if c.get("type") == "text" else f"[{c.get('type', 'content')}]")
        else:
            parts.append(str(c))
    return "\n".join(p for p in parts if p)


def _server_config(cfg: dict | str, base: Path | None) -> dict:
    """External MCP server: a config dict as-is, or a path to a Python server file."""
    if isinstance(cfg, dict):
        return cfg
    p = Path(cfg)
    if not p.is_absolute() and base:
        p = base / p
    return {"type": "stdio", "command": sys.executable, "args": [str(p)]}


class ClaudeEngine(Engine):
    name = "claude"
    capabilities = Capabilities(fork=True, permission_hook=True)

    def open(self, agent, *, resume, fork, cost_base) -> "ClaudeSession":
        return ClaudeSession(agent, resume=resume, fork=fork, cost_base=cost_base)


class ClaudeSession(EngineSession):
    def __init__(self, agent, *, resume: str | None, fork: bool, cost_base: float):
        self.agent = agent
        self.server = agent.tool_server
        self.resolved = agent.resolved_tools()
        lean = agent.setup == "lean"
        self.skills = [skills_mod.find_skill(n, agent.cwd) for n in agent.skills] if lean else []
        self._skill_dirs = [s.folder for s in self.skills]
        self._read_for_skills_only = bool(self.skills) and "Read" not in self.resolved.builtin_names \
            and not self.resolved.all_builtins
        self.session_id = resume or str(uuid.uuid4())
        self._resuming = resume is not None
        self._fork = fork
        self._turns_done = 0
        self._cost_base = float(cost_base or 0.0)
        self._client: ClaudeSDKClient | None = None
        self._ops: asyncio.Queue | None = None
        self._worker: asyncio.Task | None = None
        self._state: TurnState | None = None
        self._prompt_file: str | None = None
        self.model: str | None = agent.model
        self.init_info: dict = {}            # the CLI's init message: tools offered, MCP servers, model, ...

    @property
    def info(self) -> SessionInfo:
        d = self.init_info
        servers = {}
        for s in d.get("mcp_servers") or []:
            if isinstance(s, dict) and s.get("name"):
                servers[str(s["name"])] = str(s.get("status", ""))
        return SessionInfo(tools=[short_name(str(t), self.server) for t in d.get("tools") or []],
                           mcp_servers=servers, model=d.get("model"))

    # ------------------------------------------------------------------ options
    def _system_prompt(self):
        text = self.agent.instructions.strip()
        if self.skills:
            text = (text + "\n\n" + skills_mod.index_text(self.skills)).strip()
        if self.agent.setup == "project":
            if len(text) > ARGV_PROMPT_LIMIT:
                raise AgentError("instructions too long for project setup (Windows ~32K command-line limit)")
            sp = {"type": "preset", "preset": "claude_code"}
            return {**sp, "append": text} if text else sp
        if len(text) <= ARGV_PROMPT_LIMIT:
            return text
        if self._prompt_file is None:
            fd, self._prompt_file = tempfile.mkstemp(prefix="agentlib-prompt-", suffix=".md")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
        return {"type": "file", "path": self._prompt_file}

    def _build_server(self):
        def make(t):
            ann = None
            if t.read_only:
                from mcp.types import ToolAnnotations
                ann = ToolAnnotations(readOnlyHint=True)

            @sdk_tool(t.name, t.description, t.schema, annotations=ann)
            async def handler(args):
                state = self._state
                if state is None:
                    text, err = "error: no active turn", True
                else:
                    text, err = await state.run_tool(t.name, dict(args or {}))
                out = {"content": [{"type": "text", "text": text}]}
                if err:
                    out["is_error"] = True
                return out
            return handler

        server = create_sdk_mcp_server(self.server, "1.0.0", [make(t) for t in self.resolved.custom])
        server["alwaysLoad"] = True          # CLI mcp-config field: never defer these behind tool search
        return server

    def options(self, *, resume: str | None) -> ClaudeAgentOptions:
        a, r = self.agent, self.resolved
        lean = a.setup == "lean"
        allowed = list(r.builtin_rules) + [full_name(t.name, self.server) for t in r.custom] + list(r.mcp_rules)
        mcp: dict = {}
        if r.custom:
            mcp[self.server] = self._build_server()
        for name, cfg in a.mcp_servers.items():
            mcp[name] = _server_config(cfg, a.cwd)
            allowed.append(f"mcp__{name}__*")

        if r.all_builtins:
            tools = {"type": "preset", "preset": "claude_code"}
        else:
            tools = r.builtin_names
            if self._read_for_skills_only:
                tools = tools + ["Read"]
            if not lean and a.skills and "Skill" not in tools:
                tools = tools + ["Skill"]

        hooks: dict = {}
        stoppers = [full_name(t.name, self.server) for t in r.custom if t.ends_turn]
        if stoppers:
            hooks["PostToolUse"] = [HookMatcher(matcher="|".join(stoppers), hooks=[self._stop_hook])]
        if self._read_for_skills_only:
            hooks["PreToolUse"] = [HookMatcher(matcher="Read", hooks=[self._skill_read_hook])]

        add_dirs = [str(Path(d)) for d in a.add_dirs] + [str(d) for d in self._skill_dirs]
        kw = dict(
            tools=tools, allowed_tools=allowed, system_prompt=self._system_prompt(), mcp_servers=mcp,
            permission_mode="default", can_use_tool=self._can_use_tool, hooks=hooks or None,
            include_partial_messages=True, add_dirs=add_dirs, model=a.model, max_turns=a.max_turns,
            disallowed_tools=list(a.disallowed_tools),
            env={**(LEAN_ENV if lean else {}), **a.env},
        )
        if a.cwd:
            kw["cwd"] = str(a.cwd)
        if a.effort:
            kw["effort"] = a.effort
        if lean:
            kw.update(setting_sources=[], strict_mcp_config=True, extra_args={"disable-slash-commands": None})
        else:
            kw.update(setting_sources=["user", "project", "local"])
            if a.skills:
                kw["skills"] = list(a.skills)
        if resume:
            kw["resume"] = resume
            if self._fork and self._turns_done == 0:
                kw["fork_session"] = True
        else:
            kw["session_id"] = self.session_id
        return ClaudeAgentOptions(**kw)

    # ------------------------------------------------------------------ hooks / permissions
    async def _stop_hook(self, inp, tool_use_id, ctx):
        if self._state is not None and self._state.stop_requested:
            return {"continue_": False, "stopReason": "waiting for the user"}
        return {}

    def _abs(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else Path(self.agent.cwd or os.getcwd()) / path

    async def _skill_read_hook(self, inp, tool_use_id, ctx):
        target = ((inp or {}).get("tool_input") or {}).get("file_path") or ""
        ok = bool(target) and skills_mod.inside(self._abs(target), self._skill_dirs)
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow" if ok else "deny",
            "permissionDecisionReason": "" if ok else "This agent may only read files inside its skill folders.",
        }}

    async def _can_use_tool(self, tool_name: str, inp: dict, ctx):
        hook = self.agent.on_permission
        if hook is None:
            return PermissionResultDeny(message=f"{tool_name} is not allowed for this agent.")
        req = PermissionRequest(agent=self.agent.name, tool=short_name(tool_name, self.server), input=dict(inp or {}),
                                reason=getattr(ctx, "decision_reason", None))
        decision = hook(req)
        if inspect.isawaitable(decision):
            decision = await decision
        decision = normalize(decision)
        if decision == "allow":
            return PermissionResultAllow()
        if decision == "always_allow":
            return PermissionResultAllow(updated_permissions=[PermissionUpdate(
                type="addRules", rules=[PermissionRuleValue(tool_name=tool_name)], behavior="allow",
                destination="session")])
        return PermissionResultDeny(message=f"The user denied {tool_name}.")

    # ------------------------------------------------------------------ public (any task)
    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._ops = asyncio.Queue()
            self._worker = asyncio.get_running_loop().create_task(self._run(), name=f"agentlib-{self.agent.name}")

    async def start(self) -> None:
        self._ensure_worker()
        fut = asyncio.get_running_loop().create_future()
        await self._ops.put(("connect", None, fut))
        await fut

    async def turn(self, message: str):
        self._ensure_worker()
        q: asyncio.Queue = asyncio.Queue()
        await self._ops.put(("turn", message, q))
        while True:
            item = await q.get()
            if item is _END:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    async def interrupt(self) -> None:
        if self._client is not None:
            try:
                await self._client.interrupt()
            except Exception:  # noqa: BLE001
                pass

    async def close(self) -> None:
        if self._worker is not None and not self._worker.done():
            fut = asyncio.get_running_loop().create_future()
            await self._ops.put(("close", None, fut))
            try:
                await asyncio.wait_for(asyncio.shield(fut), 15)
            except Exception:  # noqa: BLE001
                self._worker.cancel()
        if self._prompt_file:
            try:
                os.remove(self._prompt_file)
            except OSError:
                pass
            self._prompt_file = None

    # ------------------------------------------------------------------ worker task (owns the client)
    async def _run(self) -> None:
        while True:
            op, arg, out = await self._ops.get()
            if op == "close":
                await self._disconnect()
                out.set_result(None)
                return
            if op == "connect":
                try:
                    if self._client is None:
                        await self._connect()
                    out.set_result(None)
                except BaseException as e:  # noqa: BLE001
                    out.set_exception(e)
                continue
            try:
                await self._turn(arg, out)
            except asyncio.CancelledError:
                await self._disconnect()
                raise
            except BaseException as e:  # noqa: BLE001
                await out.put(e)
            await out.put(_END)

    async def _connect(self) -> None:
        resume = self.session_id if (self._resuming or self._turns_done) else None
        client = ClaudeSDKClient(self.options(resume=resume))
        try:
            await client.connect()
        except Exception as e:  # noqa: BLE001
            if "No conversation found" in str(e):
                raise ConversationMissing(f"no saved conversation {self.session_id} (same cwd?)") from e
            raise AgentError(f"could not start Claude: {error_text(e)}", repr(e)) from e
        self._client = client

    async def _disconnect(self, failed: bool = False) -> None:
        c, self._client = self._client, None
        if c is not None:
            try:
                await c.disconnect()
            except Exception:  # noqa: BLE001
                pass
        if failed and not self._resuming and self._turns_done == 0:
            self.session_id = str(uuid.uuid4())     # a failed first turn may have claimed the id

    async def _turn(self, message: str, q: asyncio.Queue) -> None:
        if self._client is None:
            await self._connect()
        state = TurnState("claude", self.resolved.custom)
        self._state = state
        res: ResultMessage | None = None
        try:
            async with asyncio.timeout(self.agent.timeout_s):
                await self._client.query(message)
                async for m in self._client.receive_response():
                    for ev in self._map(m, state):
                        await q.put(ev)
                    if isinstance(m, ResultMessage):
                        res = m
        except TimeoutError:
            await self.interrupt()
            await self._disconnect(failed=True)
            msg = f"turn timed out after {self.agent.timeout_s}s"
            raise AgentError(msg, reply=self._failed_reply(state, msg)) from None
        except AgentError as e:
            await self._disconnect(failed=True)
            if e.reply is None:
                e.reply = self._failed_reply(state, e.short)
            raise
        except Exception as e:  # noqa: BLE001 -- process died; next turn reconnects with resume
            await self._disconnect(failed=True)
            msg = f"Claude call failed: {error_text(e)}"
            raise AgentError(msg, repr(e), reply=self._failed_reply(state, msg)) from e
        finally:
            self._state = None
        if res is None:
            await self._disconnect(failed=True)
            msg = "Claude stream ended without a result"
            raise AgentError(msg, reply=self._failed_reply(state, msg))

        total = float(res.total_cost_usd or 0.0)
        cost = total - self._cost_base if total >= self._cost_base else total
        self._cost_base = total
        if res.session_id:
            self.session_id = res.session_id
        self._turns_done += 1
        error = None
        if res.is_error and not state.stop_requested:
            error = res.result or "; ".join(res.errors or []) or res.subtype or "error"
        await q.put(Done(state.reply(session_id=self.session_id, usage=normalize_usage(res.usage), cost_usd=cost,
                                     total_cost_usd=total, model=self.model, stop_reason=res.stop_reason,
                                     error=error, api_calls=len(state.message_ids) or res.num_turns)))

    def _failed_reply(self, state: TurnState, error: str) -> Reply:
        """The partial turn for AgentError.reply: what was seen so far; cost unknown (no ResultMessage)."""
        return state.reply(session_id=self.session_id, usage=state.usage_so_far(), cost_usd=0.0,
                           total_cost_usd=self._cost_base, model=self.model, error=error)

    def _map(self, m, state: TurnState) -> list:
        if isinstance(m, StreamEvent):
            e = m.event or {}
            d = e.get("delta") or {}
            if not m.parent_tool_use_id and e.get("type") == "content_block_delta" and d.get("type") == "text_delta":
                return [TextDelta(d.get("text", ""))]
            return []
        if isinstance(m, AssistantMessage):
            if m.parent_tool_use_id:
                return []
            if m.message_id:
                state.message_ids.add(m.message_id)
                if isinstance(m.usage, dict):    # one message may arrive per content block: keep the latest
                    state.usage_by_message[m.message_id] = normalize_usage(m.usage)
            if m.model:
                self.model = m.model
            out = []
            for b in m.content:
                if isinstance(b, TextBlock) and b.text.strip():
                    state.record_text(b.text)
                    out.append(Text(b.text))
                elif isinstance(b, ToolUseBlock):
                    name = short_name(b.name, self.server)
                    state.record_call(b.id, name, b.input)
                    out.append(ToolCall(b.id, name, dict(b.input or {})))
            return out
        if isinstance(m, UserMessage):
            if m.parent_tool_use_id or not isinstance(m.content, list):
                return []
            out = []
            for b in m.content:
                if isinstance(b, ToolResultBlock):
                    text = _content_text(b.content)
                    name = state.record_result(b.tool_use_id, text, bool(b.is_error))
                    out.append(ToolResult(b.tool_use_id, name, text, bool(b.is_error)))
            return out
        if isinstance(m, RateLimitEvent):
            i = m.rate_limit_info
            return [RateLimit(status=str(i.status), resets_at=i.resets_at, utilization=i.utilization,
                              limit_type=i.rate_limit_type)]
        if isinstance(m, SystemMessage) and m.subtype == "init":
            self.init_info = dict(m.data or {})
            if self.init_info.get("session_id"):
                self.session_id = self.init_info["session_id"]
        return []
