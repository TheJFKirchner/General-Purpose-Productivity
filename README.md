# General-Purpose-Productivity

Skills for Claude Code. Copy a skill folder into your skills folder (for example `~/.claude/skills/`) to use it.

| Skill | What it does |
|---|---|
| [Smart-HTML-Editor](Smart-HTML-Editor/SKILL.md) | Opens any HTML file in an interactive editor: type over text in place, click any part to restyle it, recolor the theme, or ask a built-in assistant. Neither the assistant nor Claude Code ever sees the page's data. |
| [Front-End-Design-Plus](Front-End-Design-Plus/SKILL.md) | Opens a local whiteboard page for designing charts and tables on real data: chat with an agent that sees only column names and a few sample rows, get several ID'd visuals drawn on the full table, iterate and save the ones you like, and Claude Code merges them into the deliverable. Works in ECharts, Plotly, Chart.js, Vega-Lite, D3 or plain HTML, offline. User-invoked only; needs the Claude Agent SDK and a signed-in Claude Code (an approved exception to the `agentlib` rule). Start with its [README](Front-End-Design-Plus/README.md). |
| [james-themes](james-themes/SKILL.md) | Dashboard themes and ready-made components for building or restyling dashboards, report pages and charts. Four themes (Cigna Light/Dark, Evernorth Light/Dark) plus React + ECharts cards, charts, tables, controls and layout pieces, with working example pages and design rules. |

## Libraries

| Library | What it does |
|---|---|
| [agentlib](agentlib/README.md) | Python library for building agents once and running them on more than one engine. It wraps the Claude Agent SDK behind engine-neutral functions (a Cursor engine is planned), with a zero-token fake engine for tests. Install with `pip install -e agentlib` from this repo's folder, then do the one-time sign-in setup in [agentlib/setup/claude-setup.md](agentlib/setup/claude-setup.md) and confirm the connection with `python -m agentlib.check`. |

## Apps

| App | What it does |
|---|---|
| [wiki-app](wiki-app/README.md) | Obsidian-style desktop app for folders of Markdown notes. AI captures your notes and Claude Code sessions into a personal wiki, lets you review them, and promotes the good ones to a team wiki. It runs on `agentlib`, so download the app and `agentlib` together from this repo (keep them side by side) and complete the one-time sign-in setup in [agentlib/setup/claude-setup.md](agentlib/setup/claude-setup.md) first. Start with its README. |
| [Launchpad](Launchpad/README.md) | Local desktop app for planning and running work with AI agents. Chat with a planner, approve its plan, and an orchestrator hands each step to a builder agent and writes a report, and a Usage screen shows what it spends. It runs on `agentlib`, so keep Launchpad and `agentlib` side by side in this repo. You only need Python to run it. Start with its README. |
| [brain-intake](brain-intake/README.md) | Claude Code skills, sub-agents and one Python script for getting facts from your sessions and documents into a team or personal Markdown wiki, and for working out what to read (BrainCite, skill `brain-cite`): give it an ask and it lists the team and personal wiki sections or whole pages worth reading, with a reason for each. Nothing runs by itself and nothing is filed without your yes. Start with its README. |

## Claude Code setup (`.claude/`)

The repo's [.claude](.claude) folder holds skills and agents that load automatically in Claude Code sessions opened on this repo, including cloud and mobile sessions.

- **Skills** ([.claude/skills](.claude/skills)): factory-mode (plan a feature, then have agents build it) and grilling (stress-test a plan with pointed questions), plus the analysis toolbox below.
- **Agents** ([.claude/agents](.claude/agents)): factory-builder, factory-reader, factory-ui-reviewer, security-review and git-shipper, the helpers that factory-mode and git work hand tasks to, commentary-generator, used by the commentary skill, design-librarian, which saves visuals the user likes into the design library (following the library's `ITEM-SHAPE.md`), and graphic-designer, which suggests library items for a report, deck or dashboard being planned.

### Analysis toolbox

Six optional skills for analysis work. They share one vocabulary, one look, and one way to find files: the "## Map" in each project's `CLAUDE.md`. The analysis, presentation and dashboard skills each have a short overview `SKILL.md` and one page per action in `references/` (add, change, make your own, theme); each tool has a `show <id>` step to preview a library item before adding it.

| Skill or folder | What it does |
|---|---|
| [toolbox](.claude/skills/toolbox/SKILL.md) | Starts a new project: asks what is being made, agrees the fewest folders, writes the map and a project plan. |
| [analysis](.claude/skills/analysis/SKILL.md) | Explore data in the conversation, or build a short HTML report when asked: each section adds a chart, table or hero card from the design library by id, then you edit its file. Needs Python with `pandas`, and Edge or Chrome for screenshots. |
| [findings](.claude/skills/findings/SKILL.md) | Keeps `findings.md`, cited results against the plan. Reports and decks take their bullets from it. |
| [commentary](.claude/skills/commentary/SKILL.md) | Writes `commentary.json` for dashboards that need text across many filters or refreshes. |
| [dashboard](.claude/skills/dashboard/SKILL.md) | Makes a dashboard (tabs, filters, ECharts on live data) from a copied-in starter, or changes one: add a section from the design library by id, then edit its file; also theme, spacing, new data, porting, offline reports. Settings live in `dashboard.config.json`. Needs Node.js and Python 3.10+ with fastapi, uvicorn, duckdb, pyarrow, pandas. |
| [presentation](.claude/skills/presentation/SKILL.md) | Builds a reveal.js deck with ECharts charts: add a slide, chart, table or card from the design library by id (real data can go in), then edit its slide file; also theme, layout, build and check. Needs Node.js, internet when a deck is opened, and Edge or Chrome for screenshots. Parts adapted from the MIT-licensed ryanbbrown/revealjs-skill. |
| [Toolkit Update/design-library/](Toolkit%20Update/design-library/CLAUDE.md) | The design library: shared slides, charts, tables, hero cards, animations, layout pieces and themes, one self-contained file each; `index.html` shows them all in any theme, and `index/` lists each type with the data each item needs. `item.js` prints one item (or fills it with real columns) for the skills to add. Reports and decks also add animations by id, and `sweep-add.js` tests that every item adds to a report, deck and dashboard. Its only copy, edited in place. Saved by the `design-librarian` agent; `ITEM-SHAPE.md` is its reference page. |
| [Toolkit Update/cosmo-overview/](Toolkit%20Update/cosmo-overview/README.md) | A small static website introducing Cosmo (deliverables, brain, orchestration). Open `index.html` in a browser; no server needed. Its only copy, edited in place. |
| [Toolkit Update/](Toolkit%20Update/README.md) | The six skills, their three agents and brain-intake copied into one folder with the design library, ready to add to another workspace, with two pages to paste: [add-to-main-agent.md](Toolkit%20Update/add-to-main-agent.md) for the main agent file and [add-to-claude-md.md](Toolkit%20Update/add-to-claude-md.md) for the workspace CLAUDE.md. The skills, agents and brain-intake there are copies: refresh them after editing the originals. |

## Working from desktop and phone

The root [CLAUDE.md](CLAUDE.md) tells Claude Code how to behave here: cloud and phone sessions finish their work as a pull request for you to review, and desktop sessions keep the repo level with GitHub. When a branch starting with `claude/` is pushed, a [GitHub workflow](.github/workflows/claude-branch-pr.yml) opens a pull request automatically. It never merges anything.
