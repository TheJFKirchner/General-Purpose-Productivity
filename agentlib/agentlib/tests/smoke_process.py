"""Live check of Session.pid / Session.kill() on the real Claude engine. Sends NO model request (zero tokens):
it only starts the `claude` process (connect), looks at it, and ends it.

    python -m agentlib.tests.smoke_process

Prints how the pid was found ("transport" = from the SDK client, "children" = the fallback), the process's
name and command start, then kills the session and checks the process is gone. Not collected by pytest.
"""
from __future__ import annotations

import asyncio
import time

from agentlib import Agent, describe_process, list_descendants
from agentlib.processes import is_running


async def main() -> int:
    agent = Agent("smoke-process", instructions="Reply OK.", model="haiku", tools=[], include_ask_user=False)
    async with agent.session() as s:
        pid = s.pid
        info = describe_process(pid)
        print(f"pid={pid} source={getattr(s._es, 'pid_source', None)}")
        if info is None:
            print("RESULT: FAILED (no process found)")
            return 1
        print(f"name={info.name} command={info.command[:80]!r} mem_mb={info.mem_mb}")
        print(f"descendants={len(list_descendants(pid))}")
        t0 = time.monotonic()
        res = await s.kill()
        print(f"kill: ok={res.ok} ended={[i.pid for i in res.ended]} survivors={res.survivors} "
              f"in {time.monotonic() - t0:.2f}s")
        gone = not is_running(pid, started_at=info.started_at)
        again = await s.kill()
        print(f"gone={gone} second_kill_ok={again.ok}")
        ok = res.ok and gone and again.ok
    print("RESULT:", "WORKS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
