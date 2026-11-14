# Planner: edit-based revisions

Status: built
Date: 2026-11-13

Adds an edit_plan tool so the planner revises a draft with targeted edits instead of rewriting the whole plan. In a live check this cut the cost of a first draft plus two revisions by almost half.

Moved verbatim from the project's former combined decisions file; headings are the original section headings.

## Planner: edit-based revisions (2026-11-13, user decision)
- New planner tool edit_plan: targeted edits to the current draft (replace an exact passage, rename, set_goal, set_step, add_step, remove_step, move_step); step dependencies are remapped by code; the result is re-validated exactly like write_plan and refused with an actionable message if it would be invalid (nothing changes). Each successful edit is a new revision and sends plan_draft as before
- write_plan stays for the first draft and genuine rewrites; prompt: edit when the change is local; after a draft or edit reply in one or two lines on what changed (no recap: the user sees the plan card)
- Live (conversation B shape): first draft + two revisions $0.143 vs $0.267 this morning (rename $0.015 vs $0.074)
