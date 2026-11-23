"""16 - The process a session runs in: see it, list what it started, end all of it.

Run:  python examples/16_process_control.py          (fake engine + a real stand-in process, free)
      python examples/16_process_control.py --live   (starts Claude Code, sends NO message: zero tokens)

Why: a Claude session runs inside one `claude` process; shell commands the agent runs are its children.
close() and interrupt() only disconnect / stop the turn, so a stuck command can outlive the session.

- s.pid                       the session's OS process (None before connect, after close, or engine cannot tell)
- list_descendants(pid)       what it started: command line, start time, CPU (100 = one core), memory
- await s.kill()              end the process and everything it started (descendants found first), then the
                              session is closed; also mid-turn; a second call is harmless. -> KillResult
- end_process_tree(pid, started_at=...)   the same for leftovers whose session object is gone; the start
                              time guards against a reused pid (a mismatch refuses, nothing is ended)
Capability: process_control (claude, fake: yes; cursor: no -> CapabilityError from s.kill()).
"""
import asyncio
import subprocess
import sys

from agentlib import Agent, end_process_tree, list_descendants, process_started_at

LIVE = "--live" in sys.argv

# A stand-in for "the agent's process running a stuck shell command": a Python parent with a sleeping child.
STAND_IN = ("import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
            "time.sleep(300)\n")


async def main():
    stand_in = None
    if not LIVE:
        from agentlib import fake
        stand_in = subprocess.Popen([sys.executable, "-c", STAND_IN])
        fake.process("worker", stand_in.pid, real=True)    # real=True: kill() really ends this tree

    agent = Agent("worker", instructions="Reply OK.", model="haiku", tools=[], include_ask_user=False,
                  engine="claude" if LIVE else "fake")
    async with agent.session() as s:
        pid = s.pid
        started = process_started_at(pid)                 # keep both if you may clean up later
        print(f"session process: {pid}")
        await asyncio.sleep(1)                            # give the stand-in a moment to start its child
        for p in list_descendants(pid):
            print(f"  started by it: pid {p.pid}, {p.command[:60]!r}, {p.mem_mb} MB, cpu {p.cpu_percent}%")
        res = await s.kill()
        print(f"kill: ok={res.ok}, ended {len(res.ended)} process(es), survivors {res.survivors}")
        print("second kill harmless:", (await s.kill()).ok)
        print("leftover cleanup by pid is harmless now too:", end_process_tree(pid, started_at=started).already_gone)
    if stand_in is not None:
        stand_in.wait(timeout=10)


asyncio.run(main())
