# Builder write / shell guard: known limits

Status: decided
Date: 2026-11-13

Writes down what the builder's write check and shell deny list do not catch: the check covers the file tools only, and the deny list is pattern matching, not a sandbox. It lists the known gaps and the ways to close them later, strongest first.

Later changed by: [2026-11-13-builder-permissions-autopilot](2026-11-13-builder-permissions-autopilot.md) (writes outside the project or into .launchpad/ now raise a card instead of being refused)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Builder write / shell guard: known limits (2026-11-13)
- "Inside the project" = inside the folder the user picks at launch (`--cwd`, default the current folder); launching on a broad folder (home, a drive root) makes nearly everything "inside"
- `.launchpad/` (session records) sits inside that folder: Write/Edit into it are refused, but Bash can still write there
- Path checks cover the file tools only (Write, Edit; NotebookEdit / MultiEdit if ever offered): path resolved (incl. `..` and symlinks) before the check
- The Bash deny list is best-effort pattern matching, not a sandbox. Still possible without a card:
  - redirection / tee: `echo x > ../file`, `cat notes >> C:/Users/x/file`, `tee ../file`
  - interpreters and scripts: `python -c "open('../x','w').write('x')"`, a script the builder writes inside the project and then runs, `node -e ...`, PowerShell `Set-Content` / `Out-File`
  - copies / moves out: `cp file ../`, `mv file ~/`, `Copy-Item`, `robocopy`
  - deletes the list does not know: `find .. -delete`, `git clean` aimed elsewhere, `python -c "import shutil; shutil.rmtree(...)"`
  - installs it does not know (e.g. `pipx install`, `go install`)
- Closing the gap later (pick one, in order of strength): run builders' shell in an OS sandbox (Claude Code's `sandbox` option, to be added to agentlib engine-neutrally) or a container / separate user / scratch worktree; switch Bash from a deny list to an allow list of rules (`Bash(npm test:*)`) with everything else as a card; after each step, diff file timestamps outside the project (detects, does not prevent)
