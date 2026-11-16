# General-Purpose-Productivity

Skills for Claude Code. Copy a skill folder into your skills folder (for example `~/.claude/skills/`) to use it.

| Skill | What it does |
|---|---|
| [Smart-HTML-Editor](Smart-HTML-Editor/SKILL.md) | Opens any HTML file in an interactive editor: type over text in place, click any part to restyle it, recolor the theme, or ask a built-in assistant. Neither the assistant nor Claude Code ever sees the page's data. |
| [james-themes](james-themes/SKILL.md) | Dashboard themes and ready-made components for building or restyling dashboards, report pages and charts. Four themes (Cigna Light/Dark, Evernorth Light/Dark) plus React + ECharts cards, charts, tables, controls and layout pieces, with working example pages and design rules. |

## Libraries

| Library | What it does |
|---|---|
| [agentlib](agentlib/README.md) | Python library for building agents once and running them on more than one engine. It wraps the Claude Agent SDK behind engine-neutral functions (a Cursor engine is planned), with a zero-token fake engine for tests. Install with `pip install -e agentlib` from this repo's folder, then do the one-time sign-in setup in [agentlib/setup/claude-setup.md](agentlib/setup/claude-setup.md) and confirm the connection with `python -m agentlib.check`. |

## Apps

| App | What it does |
|---|---|
| [wiki-app](wiki-app/README.md) | Obsidian-style desktop app for folders of Markdown notes. AI captures your notes and Claude Code sessions into a personal wiki, lets you review them, and promotes the good ones to a team wiki. It runs on `agentlib`, so download the app and `agentlib` together from this repo (keep them side by side) and complete the one-time sign-in setup in [agentlib/setup/claude-setup.md](agentlib/setup/claude-setup.md) first. Start with its README. |
| [Launchpad](Launchpad/README.md) | Local desktop app for planning and running work with AI agents. Chat with a planner, approve its plan, and an orchestrator hands each step to a builder agent and writes a report. It runs on `agentlib`, so keep Launchpad and `agentlib` side by side in this repo. You only need Python to run it. Start with its README. |

## Claude Code setup (`.claude/`)

The repo's [.claude](.claude) folder holds skills and agents that load automatically in Claude Code sessions opened on this repo, including cloud and mobile sessions.

- **Skills** ([.claude/skills](.claude/skills)): factory-mode (plan a feature, then have agents build it), grilling (stress-test a plan with pointed questions), and presentation (build a slide deck from an existing analysis or dashboard: interview with the grilling skill, agree a brief and storyboard, then build reveal.js slides with ECharts charts from a library of 47 sample slides; needs Node.js, and internet when a deck is opened; parts adapted from the MIT-licensed ryanbbrown/revealjs-skill).
- **Agents** ([.claude/agents](.claude/agents)): factory-builder, factory-reader, factory-ui-reviewer, security-review and git-shipper, the helpers that factory-mode and git work hand tasks to.

## Working from desktop and phone

The root [CLAUDE.md](CLAUDE.md) tells Claude Code how to behave here: cloud and phone sessions finish their work as a pull request for you to review, and desktop sessions keep the repo level with GitHub. When a branch starting with `claude/` is pushed, a [GitHub workflow](.github/workflows/claude-branch-pr.yml) opens a pull request automatically. It never merges anything.
