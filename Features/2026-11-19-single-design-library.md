# One design library, inside Toolkit Update

Status: built
Date: 2026-11-19

The repo held two copies of the design library: a working copy at the top level and a copy inside `Toolkit Update/`. The top-level copy is removed. `Toolkit Update/design-library/` is now the only design library and the place it is edited.

## Decisions

- **One copy, and it is the one in `Toolkit Update/`.** The owner's instruction. Two copies had to be kept in step by hand. Rejected: keeping the top-level copy and making the bundle point at it, since the bundle has to be carried to another workspace whole.
- **Only the library changed.** The skills, the subagents and brain keep their working copies (`.claude/skills`, `.claude/agents`, `brain-intake/`) with copies in `Toolkit Update/claude/`, because skills only load in sessions on this repo from `.claude/`. They are still refreshed into the bundle with the commands in its README; the library no longer has a refresh step.
- **How the skills find the library**, in order: the "Design library:" line in a project's map; the library beside the skills folder (true for the bundle copy and for a workspace it was installed into); `Toolkit Update/design-library` (true for this repo's working copy).
- **The library is edited in place** and its index rebuilt with `node build-index.js` in `Toolkit Update/design-library/`. `design-librarian` is given that folder by whichever skill launches it.

## Checked

- Before deleting, the two copies were compared file by file: 131 files identical, none differing, nothing only in the copy being removed.
- The working presentation skill inserts a library slide into a scratch deck through the third lookup; the bundle copy does so through the second; a scratch workspace installed from the bundle works with this repo out of reach.
- The index rebuilds from the new location with 122 items.
- Working and bundle copies of every skill and agent file are byte-identical.

## Note on older records

Request files written before this one refer to a top-level `design-library/` folder. That folder no longer exists; read those paths as `Toolkit Update/design-library/`.
