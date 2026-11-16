# Explorer (role `astronaut`)

- What: read-only file finder. Answers one question about the project with a short list of file links (path, line, one or two sentence answer). Writes nothing itself: code adds its links to the session's flight log and its routing notes to operations-manual.md.
- Model: `haiku` (from the file).
- Tools: `Read`, `Grep`, `Glob`; structured output `ASTRONAUT_SCHEMA` (links only, capped and checked in code; links outside the project or to missing files are dropped).
- Files:
  - `agent.md`: definition (front-matter name `launchpad-astronaut`)
  - `astronaut.py`: `explore(ls, question)`, `ASTRONAUT_SCHEMA`
- Called by: the Planner's `explore` tool (`app/agents/planner/planner.py`). One Explorer meter per session.
