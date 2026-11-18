# Hookup checklist

Every name this build assumes about your setup. Walk it top to bottom when installing; each line is a test. Fix a name in one place: `<wiki>/brain-config.json` for config keys (any key from the CONFIG block of `scripts/brain.py`), or the skill text for the names in section 4.

## 1. Environment

- [ ] `python` (3.8 or later) runs from the Bash tool. Skills also use `git -C`, `cp`, `rm -f`, `whoami` and `date +%F` (Git Bash on Windows is fine).
- [ ] `BRAIN_HOME` = the folder holding `scripts/brain.py` and `brain-reference.md` (this folder). Skills find the script only through it.
- [ ] `BRAIN_WIKI` = the wiki root (the folder holding `personal/` and `team/`). Needed because skills run from project folders.
- [ ] Both set in `~/.claude/settings.json` under `"env"` (or as system variables). Check: `python "$BRAIN_HOME/scripts/brain.py" root` prints the wiki root.

## 2. Where things are copied

- [ ] `skills/brain-file`, `brain-ingest`, `brain-promote`, `brain-sight` -> `~/.claude/skills/` (one folder each, holding `SKILL.md`). Check: the four appear when you type `/brain`.
- [ ] `agents/brain-extractor.md`, `brain-filer.md`, `brain-context-analyst.md` -> `~/.claude/agents/`. Check: `/agents` lists all three.
- [ ] `scripts/brain.py` and `brain-reference.md` stay in `BRAIN_HOME`; agents are handed the reference path.
- [ ] `add-to-main-agent.md` pasted into the main agent file.
- [ ] Older brain skills, agents or BrainSight skills with overlapping jobs are removed or renamed (they would compete for the same requests).

## 3. Config keys (`scripts/brain.py` CONFIG; override in `<wiki>/brain-config.json`)

| Key | Default | Check |
|---|---|---|
| `wiki_root` | `""` (use `--wiki`, `$BRAIN_WIKI`, then current folder) | Leave empty when `BRAIN_WIKI` is set |
| `personal_dir` / `team_dir` | `personal` / `team` | Your two page folders |
| `personal_rules` / `team_rules` | `personal/rules.md` / `team/rules.md` | Both files exist |
| `personal_tags` / `team_tags` | `personal/tags.md` / `team/tags.md` | Both exist; lines read `- #tag: meaning` |
| `templates_dir` | `team/templates` | One `.md` per team template |
| `dictionary_patterns` | `*-dictionary.md`, `*.dictionary.md` | Matches every data dictionary you have, and nothing else |
| `raw_dir` | `personal/raw` | Where documents are dropped |
| `session_facts_dir` | `personal/raw/session-facts` | Matches `add-to-main-agent.md` |
| `processed_dir` | `personal/raw/processed` | Created on first `markfiled` |
| `sources_dir` | `personal/sources` | Source records live here; never deleted |
| `work_dir` | `brain-work` | Listed in the wiki's ignore file (below) |
| `skip_folder_names` | `skills`, `agents`, `sql`, `templates`, `sources`, `raw`, `brain-work` | Add any folder that holds non-page markdown |
| `page_line_limit` | `150` | Your page size rule |
| `section_level` | `2` | Page sections are `##` headings |
| `dictionaries_in_sections` | `false` | Keep false: BrainSight never points at dictionaries |
| `doubt_tags` | `#verify`, `#hunch` | The tags you use for guesses and unchecked facts; `promote --show` flags them |

## 4. Names written into the skill text (edit the skills if your config differs)

- [ ] `personal/raw/session-facts/*.md` (brain-file step 5) and `personal/raw/*` (brain-ingest step 5).
- [ ] `personal/sources` (extractor input) and `team/templates/*.md` (brain-promote step 5).
- [ ] Work files in `brain-work/`: `page-list.md`, `candidates.txt`, `sections-team.txt`, `sections-personal.txt`, `sight-existing.txt`, `sight-rows-team.json`, `sight-rows-personal.json`, `brainsight-preview.md`, `packets/`, `brain-log.md`.
- [ ] BrainSight file: `brainsight.md` in the folder the session is opened in.

## 5. Models

- [ ] All three agents use `model: haiku`. Check that this small model name is allowed through your company sign-in; if not, set the smallest allowed model in each agent file. Move only the extractor up one model, and only if it routes badly.

## 6. Sync and ignore file (brain-file, brain-ingest, brain-promote)

- [ ] In: `git -C "<wiki>" pull --ff-only`. Out: `git -C "<wiki>" add -A personal [team] && git -C "<wiki>" commit -m "..." && git -C "<wiki>" push`.
- [ ] The wiki is a git repo you can push to. If it is not, the skills skip sync.
- [ ] `brain-work/` is a line in the wiki's `.gitignore`, so packets, logs and previews are never committed.

## 7. Smoke test (run in order; step 6 on a throwaway copy of `test-wiki/`)

| # | Command | Expected |
|---|---|---|
| 1 | `python "$BRAIN_HOME/scripts/brain.py" root` | The wiki root, absolute |
| 2 | `python "$BRAIN_HOME/scripts/brain.py" pagelist` | `page list: brain-work/page-list.md (N personal, N team; N dictionaries excluded)`, with N dictionaries = your count |
| 3 | `python "$BRAIN_HOME/scripts/brain.py" sections --side team` | One block per team page (`N lines` on the page line), `Heading \| start \| lines` under it, no dictionary |
| 4 | `python "$BRAIN_HOME/scripts/brain.py" summary --status approved` | `no approved records in personal/sources` (or records left from an unfinished run) |
| 5 | In a scratch project folder: `/brain-sight one-line test project` | One yes question with team and personal counts, then `brainsight.md` with `## Team` and `## Personal` tables; `brain-work/brain-log.md` gains two `brain-context-analyst` rows |
| 6 | `python "$BRAIN_HOME/scripts/brain.py" --wiki "<copy>" collect && echo "- x" >> "<copy>/team/pmpm.md" && python "$BRAIN_HOME/scripts/brain.py" --wiki "<copy>" markfiled` | Team-write guard: `error: intake changed team or dictionary files: team/pmpm.md`, nothing filed, exit 1 |
