# Rebuild a report with new data

What this does
1. Re-reads each source named in `report.py` SOURCES, runs every section's calculation again and rewrites the
   report page `<folder name>.html` in the report folder.
2. Every figure in the words and every visual refills from the new data; the words themselves do not change.
3. A source listed in `KEEP` is read from its saved copy in `data/` unless you ask for a fresh pull.

Step 1: put the new data where the report reads it
  Replace the file a source points at (same name, same columns), or change its path in `report.py` SOURCES.
  Paths are relative to the report folder. A slow query kept in `data/`: add `--refresh` to the build.

Step 2: check the new data and the settings
  python run.py list
  -> each source's rows, columns and date ranges: compare them with the old ones
  If the period or a threshold moved, update `DEFAULTS` in `sections/_shared.py`, or `PARAMS` in `report.py`
  when only this report differs.

  | Part | Where it comes from |
  | --- | --- |
  | the source file | `report.py` SOURCES (name = path) |
  | periods, thresholds | `DEFAULTS` in `sections/_shared.py`; `PARAMS` in `report.py` overrides them |
  | `--refresh` | only for sources listed in `KEEP` |

If a part is missing
  A source file not found: the build stops and names the path it tried; repoint it in SOURCES.
  A column a section uses is gone: that section's calculation stops with its name; fix that one file.
  A section now has no rows: its figures come out empty and its chart blank; check the period or filter.

Step 3: build and look
  python run.py report
  python run.py shot
  -> reread the headline, `basis`, titles and bullets: the numbers updated, the words did not. A section that now
     points the other way means rewriting its words, and maybe `ANSWER` in `report.py`.
  A new question is a new report folder, not a rerun.
