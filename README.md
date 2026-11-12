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
