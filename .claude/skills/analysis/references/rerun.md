# Rerun or change an existing analysis

Read the folder's `README.md` first. The brief and storyline still govern.

| Situation | Do |
| --- | --- |
| Same analysis, new period or threshold | Change `PARAMS` in `config.py`; `python run.py report --refresh`; `python run.py commentary` |
| New version of a handed-over file | Replace it in `inputs/` (same name); `python run.py report`; `python run.py commentary` |
| Change one section | Edit its file; `python run.py s2` to check the figures; `python run.py commentary` |
| Change only how a chart looks | Edit `charts()`; `python run.py build` |
| Look into something new | New section file; `python run.py s5`. Report untouched |
| Add or remove a report section | Storyline in `README.md` first (gate 2 again), then `REPORT` in `config.py` |
| The question changed | New analysis folder. Start at gate 1 |

- Each run writes `output/<folder>_<date>.html`. A second run the same day replaces that day's file.
- New data: commentary written for the old data is hidden until `python run.py commentary` runs.
- Rerun with new data and the answer changed: repeat the cold read.
- Asked for every month: it has become a dashboard. The section files carry over.
