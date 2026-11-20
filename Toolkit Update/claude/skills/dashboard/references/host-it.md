# Put it on a server

What this does
1. `npm run build` checks the dashboard and builds the page into `Dist/`.
2. `npm run serve` starts one Python process that serves that page and the numbers behind it (the analysis API).
3. A scheduled `npm run pipeline` refreshes the data; the running page picks up the new data by itself.
Run commands in the dashboard folder on the server.

Step 1: build
  npm run build
  -> "check OK", then the build output; the page is in `Dist/`

Step 2: serve
  npm run serve -- --host 0.0.0.0 --port 8080
  | Part | Where it comes from |
  | --- | --- |
  | `--host 0.0.0.0` | listen to other machines; leave it out for this machine only |
  | `--port 8080` | a free port the server's firewall allows |
  The Python it runs is `"python"` in `dashboard.config.json` (a command or a full path).

Step 3: refresh on a schedule
  npm run pipeline                -> run by the server's scheduler (Task Scheduler, cron), e.g. each morning
  npm run pipeline -- --defaults  -> the same, but slow filters go back to their defaults (e.g. always the latest month)
  It keeps the old data if any script fails.

Things to know
  - Fast filters are per reader. A slow filter (`parameters`) changes the data for everyone at once; with many
    readers make it fast if the data allows, or run one copy of the dashboard per value.
  - All data reading is in `Analysis/Shared/tables.py`: the one place to change to read from a warehouse instead
    of files.
  - Sign-in is the host's job (a reverse proxy or the company portal), not the dashboard's.
  - People who only need to read it may be better served by an offline file: `export-an-offline-report.md`.

If something is missing
  - "check FAILED" on build: fix what it names (`change-a-section.md`), then build again.
  - The port is busy: pick another `--port`.

Step 4: check
  Open http://<server>:8080 from another machine: the page loads, a filter changes the sections, "Data as of" shows
  the latest data.
