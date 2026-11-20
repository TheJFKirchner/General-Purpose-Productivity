# Save a visual to the design library

What this does
1. Hands the visual to the `design-librarian` agent, which saves it in the design library as a new item.
2. The item keeps the visual (a chart, table or hero card) with made-up sample values and a note of the data it
   needs, never the project's numbers, names or calculation.
3. The library's index is rebuilt, so the item can be added to any report by its new id.

Step 1: decide what to save
  Save when the person likes a visual or says to save it. One section's visual at a time.
  Note the section file (`sections/sN_<name>.py`, from `python run.py list`) and the report page.

Step 2: find the library and launch the agent
  The library is the first that exists: the folder named on the project map's `Design library:` line;
  `design-library` beside the `.claude` folder; `Toolkit Update/design-library`.
  Launch the `design-librarian` agent with: the section file, the report page, and the library folder.

  | Part | Where it comes from |
  | --- | --- |
  | the section file | the report folder's `sections/` (`python run.py list` names it) |
  | the report page | `<report folder>/<folder name>.html` |
  | the library folder | the lookup above |

  Never copy files into the library by hand: the agent checks names, colours, data notes and sample values.

If a part is missing
  No library found: ask where it is; do not create one.
  The visual is the project's own drawing (`--own`): the agent still saves it, with sample values.
  The person wants only part of a section: say which part when launching the agent.

Step 3: check it
  The agent reports the new item's id. Open the library's `index.html` and find it, or in a report folder run
    python run.py show <new id>
  -> its parts as saved. It can now be added like any other item (see `add-a-chart.md`).
