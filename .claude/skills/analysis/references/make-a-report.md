# Start a new report

What this does
1. Creates the report folder: `report.py`, `run.py`, `page.html` and `sections/_shared.py`, by default in
   `reports/<name>/` under the folder you run it from.
2. Fills `report.py` with the title, question, reader and sources, and notes where the design library is.
3. Copies the library's page runtime and, if asked, a theme into `page.html`.
4. With `--map`, adds one line for the new folder to the project map (the `## Map` section in the project's `CLAUDE.md`).

Step 1: agree what to build (one message, one yes)
  The question, who reads it, the answer in a sentence, and one line per section (its point, its visual).
  Told "just do it": skip the yes and list what you assumed when you hand over.

Step 2: create the folder
  The script's path: this page is in `<skill>/references/`; the script is `<skill>/scripts/new_report.py`.
  So if this page is `C:/work/.claude/skills/analysis/references/make-a-report.md`, the script is
  `C:/work/.claude/skills/analysis/scripts/new_report.py`. Run it from the project folder (the report goes in
  `reports/` there):
    python C:/work/.claude/skills/analysis/scripts/new_report.py may-claims --title "Why paid claims rose in May" --question "Why did paid claims rise in May?" --for "the finance lead" --source claims=data/claims.csv

  | Part | Where it comes from |
  | --- | --- |
  | `C:/work/.claude/skills/analysis/scripts/` | this page's folder, with `references` changed to `scripts` |
  | `may-claims` | a short name; put a parent folder before it to choose where (default `reports`) |
  | title, question, reader | the agreed brief |
  | `claims=data/claims.csv` | a name you choose = a file (.csv .tsv .parquet .xlsx .sql); repeat for more |
  | `--map <project>/CLAUDE.md` | only if the project has a map; it may name the reports folder to use |
  | `--theme TH-02` | optional: a theme id from the library's `index/themes.md` |

  A `.sql` source also needs a `run_query(sql)` function in `report.py`; ask how this machine connects and never
  write a password or connection string into the project.

Step 3: see the data (in the new folder)
  python run.py list
  -> each source with its columns, their kinds and ranges: the names you will use when adding sections

Step 4: write the answer and add sections
  In `report.py`: `ANSWER` needs a `headline` (one sentence) and a `basis` (which date, against what, data through
  when). Figures are placeholders like `{section_name.metric:$short}`.
  Then add one section per point: see `add-a-chart.md`.

If a part is missing
  No sections yet: the report still builds as a page shell, with a `check:` line.
  No map: fine; the folder goes in `reports/`.
  A source file not found: the build stops and names the path it tried.

Step 5: build and look
  python run.py report
  python run.py shot
  -> `check:` lines are things to fix; `STOP:` names the file and the fix. Open the screenshot and read the page.
