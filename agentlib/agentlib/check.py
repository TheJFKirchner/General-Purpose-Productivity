"""Check that agentlib can reach your AI engine.

    python -m agentlib.check                 # Claude: checks the install + your setup, sends one tiny message
    python -m agentlib.check --status        # setup only, sends nothing (free)
    python -m agentlib.check --model sonnet  # test another model
    python -m agentlib.check --engine NAME   # another registered engine

Prints in plain language what works or what to fix (never secret values). Exit code 0 = works, 1 = not.
From Python: agentlib.check_connection_sync() / connection_status() (connection.py).
"""
from __future__ import annotations

import argparse
import sys

from .connection import CheckResult, check_connection_sync, connection_status
from .errors import AgentError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m agentlib.check", description="Check that agentlib can reach your "
                                "AI engine (sends one tiny message unless --status).")
    p.add_argument("--engine", default="claude", help="engine to check (default: claude)")
    p.add_argument("--model", default=None, help="model for the test message (default: the engine's cheapest)")
    p.add_argument("--status", action="store_true", help="only show the setup; send nothing")
    p.add_argument("--timeout", type=float, default=90, help="seconds to wait for the answer (default 90)")
    a = p.parse_args(argv)
    try:                                          # engine messages may hold characters a Windows console lacks
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    try:
        if a.status:
            st = connection_status(a.engine)
            print(CheckResult(ok=st.ok, engine=a.engine, status=st).report())
            return 0 if st.ok else 1
        result = check_connection_sync(a.engine, model=a.model, timeout_s=a.timeout)
    except AgentError as e:                       # unknown engine name and similar
        print(f"agentlib connection check: {a.engine}\nRESULT: FAILED. {e.short}")
        return 1
    print(result.report())
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
