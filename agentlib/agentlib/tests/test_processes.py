"""processes.py with REAL processes: a small Python parent that starts a sleeping child (no tokens).

Every test ends whatever it started (the fixture kills leftovers even when an assertion fails).
"""
import os
import subprocess
import sys
import time

import psutil
import pytest

from agentlib import processes
from agentlib.processes import (describe_process, end_process_tree, is_running, list_descendants,
                                process_started_at)

PARENT = (
    "import subprocess, sys, time\n"
    "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "print(c.pid, flush=True)\n"
    "time.sleep(120)\n"
)


def _wait_for(cond, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


@pytest.fixture
def tree():
    """(parent Popen, child pid). The child pid is the parent's direct child; on some installs (e.g. the Windows
    Store Python launcher) more processes sit in between or below, so tests compare whole descendant lists."""
    started: list[int] = []
    parent = subprocess.Popen([sys.executable, "-c", PARENT], stdout=subprocess.PIPE, text=True)
    started.append(parent.pid)
    try:
        child = int(parent.stdout.readline().strip())
        started.append(child)
        assert _wait_for(lambda: is_running(child))
        yield parent, child
    finally:
        everyone = set(started)
        for pid in started:
            try:
                everyone |= {c.pid for c in psutil.Process(pid).children(recursive=True)}
            except psutil.Error:
                pass
        for pid in everyone:
            try:
                psutil.Process(pid).kill()
            except psutil.Error:
                pass
        try:
            parent.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        if parent.stdout:
            parent.stdout.close()


def test_lists_descendants_with_details(tree):
    parent, child = tree
    found = list_descendants(parent.pid, started_at=process_started_at(parent.pid))
    pids = {p.pid for p in found}
    assert child in pids
    info = next(p for p in found if p.pid == child)
    assert "sleep(120)" in info.command and info.started_at > 0 and info.mem_mb > 0
    assert info.parent_pid is not None and info.status
    assert set(info.to_dict()) == {"pid", "parent_pid", "name", "command", "started_at", "cpu_percent", "mem_mb",
                                   "status"}
    me = describe_process(parent.pid)
    assert me is not None and me.pid == parent.pid


def test_end_process_tree_ends_parent_and_child_and_twice_is_harmless(tree):
    parent, child = tree
    started = process_started_at(parent.pid)
    before = {p.pid for p in list_descendants(parent.pid)} | {parent.pid}
    res = end_process_tree(parent.pid, started_at=started, timeout_s=3)
    assert res.ok and not res.refused and not res.survivors and not res.already_gone
    assert {p.pid for p in res.ended} >= {parent.pid, child}
    assert _wait_for(lambda: not any(is_running(p) for p in before), timeout=5)
    parent.wait(timeout=5)
    again = end_process_tree(parent.pid, started_at=started)
    assert again.ok and again.already_gone and not again.ended


def test_wrong_start_time_refuses_and_kills_nothing(tree):
    parent, child = tree
    res = end_process_tree(parent.pid, started_at=process_started_at(parent.pid) - 3600)
    assert not res.ok and "start time" in res.refused and not res.ended
    assert is_running(parent.pid) and is_running(child)
    assert list_descendants(parent.pid, started_at=1.0) == []        # same guard when listing
    assert describe_process(parent.pid, started_at=1.0) is None


BAD_STARTS = [float("nan"), float("inf"), float("-inf"), "1700000000", "nan", True, False, -5.0, 0, [1.0]]


def test_bad_start_times_never_kill_and_never_raise(tree):
    parent, child = tree
    for bad in BAD_STARTS:                                  # one batch: none may raise, none may kill
        res = end_process_tree(parent.pid, started_at=bad)
        assert not res.ok and res.refused and "start time" in res.refused and not res.ended, bad
        assert list_descendants(parent.pid, started_at=bad) == []
        assert describe_process(parent.pid, started_at=bad) is None
        assert is_running(parent.pid, started_at=bad) is False
        assert processes.bad_start_time(bad)
    assert is_running(parent.pid) and is_running(child)
    assert processes.bad_start_time(process_started_at(parent.pid)) is None


def test_bad_pids_are_refused_not_raised(tree):
    parent, child = tree
    for bad in [str(parent.pid), True, float(parent.pid), -3]:
        res = end_process_tree(bad)
        assert not res.ok and res.refused and not res.ended, bad
        assert list_descendants(bad) == [] and describe_process(bad) is None and not is_running(bad)
    assert is_running(parent.pid) and is_running(child)


def test_include_root_false_ends_only_the_descendants(tree):
    parent, child = tree
    res = end_process_tree(parent.pid, include_root=False)
    assert res.ok and child in {p.pid for p in res.ended} and parent.pid not in {p.pid for p in res.ended}
    assert _wait_for(lambda: not is_running(child), timeout=5)
    assert is_running(parent.pid)


def test_refuses_this_program_its_parents_and_system():
    assert "itself" in end_process_tree(os.getpid()).refused
    ppid = psutil.Process().ppid()
    if ppid:
        assert end_process_tree(ppid).refused
    assert "operating system" in end_process_tree(0).refused


def test_gone_and_none_are_harmless():
    assert end_process_tree(None).already_gone
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait(timeout=30)
    assert process_started_at(dead.pid) is None or not is_running(dead.pid, started_at=1.0)
    assert list_descendants(None) == [] and describe_process(None) is None


def test_new_child_picks_the_one_new_child():
    before = processes.child_pids()
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert processes.new_child(before) == p.pid
        q = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            assert processes.new_child(before) is None                # two new ones: cannot tell
        finally:
            end_process_tree(q.pid)
            q.wait(timeout=10)
    finally:
        end_process_tree(p.pid)
        p.wait(timeout=10)
