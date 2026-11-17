# __TITLE__

Created __DATE__. Built with the `analysis` skill.

## Request

- **Question:** __QUESTION__
- **For whom:**
- **Background:**
- **How it will be used:**
- **Where it fits:**
- **Success:**
- **Scope:**
- **Sources:**
- **Definitions:**
- **Things to test:**
- **Assumptions:**
- **Approved:**

## Storyline

**Answer:**

| Section | Claim it proves | Visual |
| --- | --- | --- |

**Not included:**

**Findings for the project** (only in a project; see the `findings` skill):

| Goal | Finding, one sentence | Section | Filed as |
| --- | --- | --- | --- |

**Approved:**

## Cold read

## Hand-over notes

## Run

Needs Python with `pandas` and `pyarrow`.

| Command | Does |
| --- | --- |
| `python run.py report` | Pull sources if needed, run the report's sections, build the report in `output/` |
| `python run.py report --refresh` | The same, pulling SQL sources again first |
| `python run.py` | Run every section, including ones not in the report, and print the results. No report |
| `python run.py s2` | Run one section and print its results. No report |
| `python run.py commentary` | Write commentary for sections that need it, rebuild |
| `python run.py status` | What exists and what is out of date |

Change `config.py` for a rerun with new dates or files. Edit `sections/` to change the analysis. `REPORT` in `config.py` lists the sections the report uses; other section files are analysis that was kept but not used. Fonts and colours are in `page.html`. Do not edit `_engine/`, `data/`, `commentary/` or `output/`.
