# Planner: start on Sonnet, promote to Opus

Status: built
Date: 2026-11-13

Every planner session starts on Sonnet and may be promoted once to Opus, by the planner itself within the first two turns when the criteria file says so, or by the user at any time. The switch keeps the same conversation and the cost is split by model.

Later changed by: [2026-11-14-code-organisation](2026-11-14-code-organisation.md) (the criteria file is now app/agents/planner/promotion.md)

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Planner: start on Sonnet, promote to Opus (2026-11-13, user decision)
- Every planner session starts on `planner_start_model` (default sonnet; `--planner-start`) and may be promoted once to `planner_top_model` (default opus; `--planner-top`); never twice, never down; same value or `--model X` = promotion off (always one model)
- Criteria in one editable markdown file `app/planner-promotion.md` (setting / `--promotion-criteria` for a replacement); shown in the Crew tab (crew_list planner.promotion)
- The Sonnet planner decides: tool promote_planner(reason), whose description carries the criteria; allowed only in the first `promotion_window_turns` turns (default 2, `--promotion-window`); the tool stays offered all session (so the cached tool list never changes) and refuses after the window. The user can promote by hand any time (planner_promote)
- Mechanics: new agentlib Session.set_model (engine-neutral, capability model_switch, fake engine + tests): same process, same conversation; mid-turn the next model call already uses the new model, so the planner simply continues. Chosen over resume / fork: no second process, no synthetic "continue" message, no lost pending question round
- Cost split: new agentlib Reply.usage_by_model; the planner's one agent_usage entry carries by_model (e.g. Sonnet then Opus)
- Switch cost (live): the new model writes the conversation so far to its own cache once; in conversation B that was 5,194 tokens on Opus ($0.042, of which the ~3.3K prompt / tools prefix any cold Opus start pays too) plus $0.005 of Sonnet before the switch
- Live: small clear request stayed on Sonnet: $0.043 vs $0.096 all-Opus; messy request promoted on turn 1 ("Open-ended goal, unclear scope; needs data and requirements discovery"): $0.312 vs $0.405 all-Opus; Sonnet's first-turn questions on the small request were comparable to Opus's (Opus added more context to each question)
