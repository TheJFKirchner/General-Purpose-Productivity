# Make a new dashboard

What this does
1. Copies the starter dashboard into a new, empty folder.
2. Takes the theme you name from the design library and writes it to `Themes/<TH id>/`.
3. Writes `dashboard.config.json` (title, theme, a free server port, the Python to use, the library's folder).
4. Installs the page's packages (`npm install`, a minute or two) and runs the first check.

Step 1: agree the plan (one message, one yes)
  Who uses it, the questions it answers, the tabs, each section (the claim it makes, the library item that shows
  it), the filters. Told "just do it": go ahead and list what you assumed.

Step 2: pick the folder
  Default: a `dashboard` folder inside the project's folder.
  The project is in OneDrive or another synced folder: never build there. Use the workspace's dashboards folder,
  `<dashboards folder>/<project name>/` (ask where it is if not known).
  The project's `CLAUDE.md` map (its `## Map` section) has a `dashboard/` row naming a folder: use that one.

Step 3: make it
  python <this skill>/tools/setup.py C:/work/claims/dashboard --title "Claims watch" --theme TH-01
  -> ends with "check: check OK" and three next steps

  | Part | Where it comes from |
  | --- | --- |
  | `<this skill>` | the folder holding this skill's `SKILL.md`; this page sits in `<this skill>/references/`, so the
    script is one folder up: `<this skill>/tools/setup.py` (a full path, e.g. C:/.../skills/dashboard/tools/setup.py) |
  | `C:/work/claims/dashboard` | step 2; it must be new or empty |
  | `--title` | what readers call it, from the plan |
  | `--theme TH-01` | a theme id from the library's `index/themes.md`; TH-01 when unsure |

If something is missing
  - No Node, or no Python 3.10+ with fastapi, uvicorn, duckdb, pyarrow, pandas: setup says which; tell the user.
  - Library not found: setup says so; run it again with `--library <the design-library folder>`.
  - The folder is not empty: setup changes nothing; pick another folder.
  - The folder is inside OneDrive, Dropbox or another synced folder: setup refuses; use the dashboards folder (step 2).

Step 4: write the plan down
  Create `PLAN.md` in the dashboard folder:
  ```
  # Plan: Claims watch
  For: finance leads. Questions: is paid cost rising, where, which providers drive it.
  | Tab | Section | Claim | Item | Table |
  | Overview | Paid by month | Paid rose in spring | CT-35 | claims |
  | Filters: Line of business (whole dashboard, column line_of_business) |
  ```

Step 5: add a row to the project's map
  In the project's `CLAUDE.md` `## Map`: `| dashboard/ | Claims watch for finance. Data: inputs/claims.csv. Refresh: replace it, npm run pipeline, npm run check. |`

Step 6: check and look
  In the new dashboard folder:
  npm run check   -> "check OK" (warnings about no sections and no data yet are expected)
  npm run shot    -> a picture of the empty page in Data/.shots/; open it: it says to load the data first.
Next: load the data (`add-data-and-filters.md`), then add sections (`add-a-section.md`).
