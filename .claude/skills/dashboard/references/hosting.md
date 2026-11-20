# Hosting

- `npm run build`, then `npm run serve -- --host 0.0.0.0 --port <port>` serves the page and the analysis API from
  one Python process. The Python command comes from `"python"` in `dashboard.config.json`.
- Refresh data with `npm run pipeline` on a schedule. It keeps slow filter values readers picked; add
  `-- --defaults` to always go back to the defaults (e.g. always the latest month).
- All data reading is in `Analysis/Shared/tables.py`: the one place to change to read from a warehouse instead.
- Fast filters are per reader. A slow filter changes the data for everyone at once; with many users, make it fast
  if the data allows, or keep one dashboard copy per value.
- Sign-in is the host's job.
- For people who only need a file, an offline report may be enough (`exports.md`).
