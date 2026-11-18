# Features

Every request made for Front-End-Design-Plus, oldest first. Newer requests override older ones where they conflict.

| # | Request | Summary |
|---|---|---|
| 1 | [Front-end design plus](2026-11-18-front-end-design-plus.md) | A user-invoked skill opens a local whiteboard page where an agent that sees only column names and sample rows draws ID'd charts and tables on the real data, in one of six browser charting libraries. Saved visuals are written as small recipe files to a temp folder for the main conversation to merge into the deliverable. |
| 2 | [Rounds, usage bar and current visual](2026-11-18-rounds-usage-current-visual.md) | After each message the whiteboard hides earlier cards behind a "Show earlier cards" control, keeping saved cards and the current visual in view, and a bar shows the model, tokens used and an estimated cost. When the visual already exists, the skill always passes it in and the whiteboard opens showing it as it looks today. |
| 3 | [No resume between sessions](2026-11-18-no-resume.md) | Every launch of the whiteboard is now a fresh board in a new output folder, and only the visuals the user saved are kept. A saved visual is reloaded only when the user points the skill at it, when it opens as the current visual. |
| 4 | [Lean agent on Claude Code](2026-11-18-lean-agent.md) | The whiteboard agent was moved off agentlib onto Claude Code directly and stripped to one model call per turn with no tools and only its own instructions, cutting a typical turn from about 24,000 tokens to about 6,300. This is an owner-approved exception to the workspace rule and makes the whiteboard Claude-only until its one engine file is moved back. |
