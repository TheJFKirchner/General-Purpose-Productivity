# psutil

Used in `agentlib/processes.py` (the only module that imports it) for `Session.pid` / `Session.kill()` and the
standalone helpers `end_process_tree`, `list_descendants`, `describe_process`, `process_started_at`.
Dependency: `psutil>=5.9` (tested with 7.2.2).

## Links
- Docs (moved from psutil.readthedocs.io to https://psutil.io/ in 2026; the old recipe URLs now 404)
- Recipes ("kill process tree"): https://psutil.readthedocs.io/latest/recipes.html (search result; page moved)
- The installed docstrings were the source used for the details below (`Process.children`, `wait_procs`,
  `terminate`, `kill`, `is_running`)

## What matters here
- `Process.children(recursive=True)` walks by parent pid. If a middle process X has already died, its children
  are no longer listed (the link is lost). So: list descendants BEFORE ending anything.
- `terminate()` is SIGTERM on POSIX; on Windows it is an alias for `kill()` (TerminateProcess): no graceful
  stop and no process-group signal, so each process in the tree is ended one by one.
- `terminate()` / `kill()` / `children()` check for pid reuse against the Process object's own start time.
  Across calls (a pid stored by a caller) agentlib compares `create_time()` with the caller's `started_at`
  (1 s tolerance, so a rounded value still matches).
- `wait_procs()` calls `Process.wait()`, which reaps (waitpid) a child of the current process. That would steal
  the exit status from asyncio / anyio, which own the `claude` process, so agentlib polls `is_running()` and
  treats `STATUS_ZOMBIE` as gone instead.
- `cpu_percent(interval=None)` compares with the previous call on the SAME Process object; the first call
  returns 0.0. agentlib keeps Process objects by (pid, create_time) so repeated listings give real figures.
  100 = one full core.
- `oneshot()` speeds up reading several attributes at once.
- Exceptions: `NoSuchProcess` (gone), `ZombieProcess` (subclass of NoSuchProcess on POSIX), `AccessDenied`
  (another user's / protected process: cmdline and memory may be unreadable).
