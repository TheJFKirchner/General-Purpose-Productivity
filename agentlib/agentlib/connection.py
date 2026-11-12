"""Is an engine set up for this user, and does it actually answer? Engine-neutral; for settings screens and the
check command (python -m agentlib.check).

- connection_status(engine) -> ConnectionStatus: reads the local setup file and checks the install. Sends
  nothing, costs nothing. Never contains secret values (variable names only)
- await check_connection(engine, model=None, timeout_s=90) / check_connection_sync(...) -> CheckResult: status,
  then (if that is fine) one tiny message on the engine's cheapest model (Claude: haiku, a fraction of a cent).
  Never raises for a failed connection: CheckResult.ok / .error / .fix say what happened; .report() is the
  plain-language text the check command prints
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field

from . import local_setup, prompt_files
from .errors import AgentError
from .engines import get_engine, get_setup

CHECK_AGENT = "agentlib-check"          # agent name the check uses (fake.script(CHECK_AGENT, ...) in tests)


@dataclass
class ConnectionStatus:
    engine: str
    ok: bool                            # set up correctly, as far as can be told without sending anything
    method: str                         # how it signs in, engine-defined ("login", "settings-file", "env", ...)
    summary: str                        # plain language, e.g. "your Claude Code login ..."; names only, no values
    env_names: list[str] = field(default_factory=list)    # variables the local setup adds (values never shown)
    setup_file: str | None = None       # local setup file in use; None = none found (defaults apply)
    setup_doc: str | None = None        # the engine's setup guide
    version: str = ""                   # engine package / program versions, if known
    problems: list[str] = field(default_factory=list)     # what is wrong, each with what to do
    notes: list[str] = field(default_factory=list)        # hints that are not errors

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckResult:
    ok: bool                            # the engine answered
    engine: str
    status: ConnectionStatus
    sent: bool = False                  # a message was sent (False when the setup already had problems)
    model: str | None = None            # model that answered (or was asked)
    reply_text: str = ""
    cost_usd: float = 0.0
    duration_s: float = 0.0
    error: str | None = None
    fix: str | None = None              # plain-language next step when it failed

    def to_dict(self) -> dict:
        return asdict(self)

    def report(self) -> str:
        """Plain-language result, as printed by `python -m agentlib.check`. Contains no secret values."""
        st = self.status
        lines = [f"agentlib connection check: {self.engine}"]
        if st.version:
            lines.append(f"  Installed:   {st.version}")
        lines.append(f"  Local setup: {st.setup_file or 'none found (using the default)'}")
        lines.append(f"  Sign-in:     {st.summary}")
        for n in st.notes:
            lines.append(f"  Note:        {n}")
        if not self.sent and st.ok:                 # status only (check --status)
            lines.append("RESULT: SET UP. Nothing was sent; run the check without --status to test it for real.")
            return "\n".join(lines)
        if self.ok:
            lines.append(f"  Test:        one tiny message on {self.model or 'the default model'}")
            lines.append(f"RESULT: WORKS. {self.engine} answered (model {self.model or '?'}, "
                         f"{self.duration_s:.1f}s, cost ${self.cost_usd:.4f}).")
            return "\n".join(lines)
        if not self.sent:
            lines.append("RESULT: NOT SET UP. Nothing was sent.")
            for p in st.problems:
                lines.append(f"  Problem:     {p}")
        else:
            lines.append(f"  Test:        one tiny message on {self.model or 'the default model'}")
            lines.append(f"RESULT: FAILED. {self.error}")
            if self.fix:
                lines.append(f"  What to do:  {self.fix}")
        if st.setup_doc:
            lines.append(f"  Setup guide: {st.setup_doc}")
        return "\n".join(lines)


def connection_status(engine: str = "claude") -> ConnectionStatus:
    """How `engine` is set up for this user, without sending anything. Unknown engine -> EngineUnavailable."""
    setup = get_setup(engine)
    conn = local_setup.connection(engine)
    path, _, _ = local_setup.read()
    doc = local_setup.doc_path(engine)
    problems = setup.prerequisites() + list(conn.problems)
    if not problems:
        try:
            if not get_engine(engine).capabilities.available:
                problems.append(f"the {engine} engine is not built yet (it cannot run)")
        except ImportError as e:
            problems.append(f"the {engine} engine could not load: {e}")
    return ConnectionStatus(engine=engine, ok=not problems, method=conn.method, summary=conn.summary,
                            env_names=sorted(conn.env), setup_file=str(path) if path else None,
                            setup_doc=str(doc) if doc else None, version=setup.version(),
                            problems=problems, notes=list(conn.notes))


async def check_connection(engine: str = "claude", *, model: str | None = None,
                           timeout_s: float | None = 90) -> CheckResult:
    """Status, then one tiny real message (nothing saved, no tools). model=None -> the engine's cheapest."""
    from .agent import Agent
    st = connection_status(engine)
    setup = get_setup(engine)
    model = model or setup.check_model
    if not st.ok:
        return CheckResult(ok=False, engine=engine, status=st, model=model, error="; ".join(st.problems),
                           fix="fix the problems listed above, then run the check again")
    caps = get_engine(engine).capabilities
    agent = Agent(CHECK_AGENT, engine=engine, model=model, tools=[], include_ask_user=False,
                  permission_mode="never_ask" if caps.never_ask else "default",
                  save_conversation=not caps.unsaved, timeout_s=timeout_s)
    t0 = time.monotonic()
    error, reply = None, None
    try:
        reply = await agent.ask(prompt_files.load("connection_check"))
        if reply.status == "error":
            error = reply.error or "the engine returned an error"
    except AgentError as e:
        error, reply = e.short, e.reply
    duration = round(time.monotonic() - t0, 2)
    if error:
        fix = setup.fix_for(error) or (f"see the setup guide: {st.setup_doc}" if st.setup_doc
                                       else "check how this engine is set up")
        return CheckResult(ok=False, engine=engine, status=st, sent=True, model=model, error=error, fix=fix,
                           duration_s=duration, cost_usd=reply.cost_usd if reply else 0.0)
    return CheckResult(ok=True, engine=engine, status=st, sent=True, model=reply.model or model,
                       reply_text=reply.text, cost_usd=reply.cost_usd, duration_s=duration)


def check_connection_sync(engine: str = "claude", **kw) -> CheckResult:
    """check_connection() for code with no running event loop (uses asyncio.run)."""
    return asyncio.run(check_connection(engine, **kw))
