# Plan Pal extraction (D50)

Paths are relative to `Planning Chatbot/interviewer_sdk/`. Reference only; V1 is a fresh build.

## 1. Reuse almost as-is
- **`engine/sdk.py` `base_options()`, `normalize_usage()`, `error_text()`** → step 2, `agentlib/engines/claude.py`. These lean-session flags were checked live: `setting_sources=[]`, `strict_mcp_config`, `dontAsk`, tool search off, slash commands off. Usage is split into 5m and 1h cache writes.
- **`engine/opus.py` `OpusAgent`** (`_run`, `_connect`, `_turn`, `_stop_hook`, `ConversationMissing`) → the persistent planner session (D46, D50a). One task owns the client. It takes the per-turn cost delta, and a timeout interrupts and then resumes.
- **`engine/tools.py` `build_server()`, `STOP_TOOLS`** → step 5, the MCP server. Handler errors become `is_error`, and `alwaysLoad` is set.
- **`engine/haiku.py` `read_decision()`, `filter_grep_output()`, `HaikuRunner._guard`/`_grep_filter`, `ResearchJob`** → the reader (D26–D30b, step 7). It has a secrets/5 MB guard, progress from tool calls, timeout and `FAILED:` lines, and writes `research/<id>.md`. `add_dirs` gives D30b's extra folders.
- **`engine/costs.py` `_rates()`, `_write_kind()`, plus `config/pricing.json`** → D17. Prices were checked against the CLI's `total_cost_usd`, which answers §8's open "price table values".
- **`engine/nowindow.py`** → stops the CLI and ripgrep from popping up console windows under pythonw.
- **`engine/settings.py` `write_json_atomic()`** → retries `os.replace` because OneDrive briefly locks files.
- **`app.py` `_make_loop()`, `start_server()`, pythonw stdout fallback** → step 3. Windows needs a ProactorEventLoop or SDK subprocesses fail.
- **`engine/taskbar.py`** (optional) → gives the window its own taskbar icon.

## 2. Reuse the idea, rewrite the code
- **`Session.stop_requested()`**: the turn ends only after a valid call, and an `is_error` reply lets Opus retry. This is how D49's `write_plan` validation should work.
- **`Session._rebrief()`** → D41 resume: goal, rendered state, research ids already used, then the pending message.
- **`render_tree_md()`, `display_notes()`, node model in `docs/contracts.md`** → scoreboard schema and interview-notes writer.
- **`Session.handle_answer()`** compact answers (`- id: ACCEPT | ANSWER — x | DISAGREE — x | SKIPPED`), which keep cached history short. It flags skipped questions automatically (D33).
- **`_sections()`** (one pickup point for research), **`_maybe_auto_continue()`**, **`_fallback_plan()`**, **`launch.py` `missing_packages()`**.
- **`docs.py` `parse()`/`render()`** (a small header format, D42) and **`review.py`** (a fresh-context checklist grader for D37, could run on Haiku).

## 3. Prompts worth carrying over
- **`prompts/interviewer.md`**:
  - "Each turn": question ≤15 words worded so "yes" accepts it; recommendation ≤12 words.
  - "Rounds: frontier only" (= D31).
  - "The user's answers": DISAGREE → re-ask with a new recommendation; SKIPPED → ask again.
  - "Review, then done": "Have we reached a shared understanding?"
  - "Facts vs decisions".
  - "Altitude: plan, not brief" (= D30 tiers).
  - Add D35's "no pushback on taste". Drop the tree and submit_round wording.
- **`prompts/brief.md`**: "Altitude: brief, not plan" and "Plan edits (limited)" → D30's "changes to the project plan" list.
- **`prompts/researcher.md`** → reader brief: cite `path:line`, say "not found" plus where it looked, read-only, no preamble. Raise the cap to 300 words, one bullet per question (D28).
- **`prompts/checklist_plan.md`** → more items for the done checklist. **`prompts/brief_template.md`** → starting brief format.

## 4. Lessons and gotchas
- **Subscription login works with no API key.** `total_cost_usd` is a list-price estimate, not a bill.
- **`total_cost_usd` is cumulative per conversation, even after resume**, so take a delta each turn. `usage` is already per turn.
- **There is one `AssistantMessage` per content block**, and `num_turns` miscounts. Count distinct `message_id`s instead.
- **Without `strict_mcp_config` the claude.ai connectors get attached.**
- **The system prompt goes on argv**, and Windows caps it at about 32K chars.
- **Use the client only from the task that connected it.**
- **Resume needs the same `cwd`.** A failed first turn may persist its session id, so retry on a new uuid.
- **Every measured cache write was 1h** (priced 2× input), yet Plan Pal hard-coded a 5-min TTL.
- **A Grep with its own glob returned `.env` lines**, so it needs the PostToolUse filter as well as the deny.
- **Real numbers:** a 5-round interview cost about $0.25. Opus context was about 11k tokens at the end; the base prompt is about 4.1k. Each Haiku job cost about $0.002. Each tool schema adds about 430 tokens.

## 5. Don't reuse
- `submit_round` mega-tool: V1 uses 4 tools.
- `ui/tree.js`: D6 is a grouped list.
- `engine/ttl.py` auto-finalize: it ends interviews on a clock, with the wrong TTL.
- The "regular Claude Code" counterfactual and `calibration.json`: not needed.
- `search_brain` / `profile_data`: D25 and D30a.
- Uploads, the Prompts editor, `knowledge.json`: D45 replaces them.
- `Docs/` + `.planpal/` layout: D42/D44 replace it.
- `explain` / ELABORATE: D34 covers it.
- `_retired/`.

## 6. Conflicts with v1plan.md
1. **Gateway wording.** D14, D16, D17, D50a and §9 still assume the LiteLLM gateway; rewrite them for subscription login. The cost shown is notional.
2. **D24 `ask_user` "returns immediately".** Without a PostToolUse `continue:false` hook, Opus makes another API call and keeps talking. Plan Pal measured 0 calls after the stop. Have `save_note` calls go in the same response as `ask_user`.
3. **D27 quiet pickup can stall.** If only research-blocked items remain, the user has nothing to answer, so an empty round needs auto-continue.
4. **D48.** Tool schemas always come before the system prompt, so that order can't be controlled. Playbook plus wiki file may break the 32K argv limit; move a large wiki file into the first user message.
5. **D3 hand-back is missing.** A detached launch can't return anything; Plan Pal relied on the user saying "done". Make `launch.py` block and print the path and summary, with the skill running it in the background, or use a result file.
6. **D8 and the price table.** They need 1h-write pricing and per-turn deltas.
7. **D11–D13.** Plan Pal had no access code or origin check; build them fresh.
8. **D9.** Plan Pal saved on close instead of asking. Asking needs pywebview's `closing` event, which was never verified.
