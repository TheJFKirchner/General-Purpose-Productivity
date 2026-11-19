# General-Purpose-Productivity

Instructions for Claude sessions working in this repo. The [README](README.md) says what each folder is.

This repo is worked on from two places: Claude Code on the desktop computer, and cloud sessions started from the phone or the web. GitHub is the meeting point. The rules below keep the two from drifting apart.

## Cloud and phone sessions: finish with a pull request

A cloud session works on its own `claude/...` branch. Work is not finished until it is on GitHub with a pull request James can approve from his phone.

When the work is done:

1. Run the `security-review` agent (in `.claude/agents/`) on the changes. If it reports BLOCK, fix the findings first.
2. Make sure the root `README.md` still describes the repo correctly.
3. Commit and push the branch. Pushing a `claude/...` branch opens a pull request automatically (`.github/workflows/claude-branch-pr.yml`), with a first description built from the commit messages.
4. Replace that description with a proper one, and set a clear title. If no pull request appeared within a minute or so, open one yourself against `main`. The description is what James reads on his phone before approving, so write it for someone who has not seen the session:
   - **What changed**, in plain language, a few lines.
   - **Why**, tied to what James asked for.
   - **How it was checked**: tests run and their result, or a plain statement that it was not tested.
   - **Not done or worth a look**: anything left unfinished, any decision made on his behalf, any security-review warning.
5. Stop there. Do not merge the pull request and do not push to `main`. James approves and merges it himself.

Write good commit messages as you go: the automatic description is built from them, and it is what James sees if the session ends early.

## Desktop sessions

- A hook on the desktop fetches this repo when a session starts. If the local copy is clean and only behind, it pulls. Otherwise it reports the state, and that goes to James before any work starts.
- Desktop work is committed and pushed straight to `main` when James asks, after the security review.
- Uncommitted or unpushed work is invisible to phone sessions. When James finishes on the desktop, say what is still not on GitHub.

## Skills and agents live here

`.claude/skills/` and `.claude/agents/` in this repo are the only copies of the factory-mode skill and the factory, security-review and git-shipper agents. On the desktop, the user-level folders are links to these, so edit them here and nowhere else.

- The analysis toolbox skills, the `commentary-generator` and `design-librarian` agents, `design-library/` and `brain-intake/` are edited in those working locations, never in `Toolkit Update/`.
- `Toolkit Update/` is a copy for installing elsewhere. After any such edit, refresh it with the commands in [its README](Toolkit%20Update/README.md).
