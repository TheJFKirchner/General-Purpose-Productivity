# Explore a question

What this does
1. Answers a question about data in the conversation. No folder, no file, nothing saved.
2. The answer is a small table or a few figures, each with one line on what it shows.
3. When a result looks worth keeping, it says so; the person decides whether to make a report.

Step 1: get the context
  Read the project's `CLAUDE.md` map, if it has one, and any findings it lists that bear on the question.
  Find the data: the files or queries the map names, or ask.

Step 2: test it
  Use Python or SQL in the session: counts, cuts, comparisons. No required format.
  An open question ("why is X high?"): name the few things you will test, likeliest first; ask before chasing
  something off that list.
  Data with several dates (paid, service, received): check the answer on each; say if they disagree.

  | Part | Where it comes from |
  | --- | --- |
  | the data | the project map, or the person |
  | what to test | the question, likeliest causes first |
  | a threshold or period | what the person or the project findings use; say which |

If a part is missing
  No map: ask where the data is.
  A table asked for as a file (Excel, CSV): save it in the project's `exports/` folder and add a map line if the
  project has a map.
  Not enough data to answer: say what is missing instead of guessing.

Step 3: say what you found
  The answer first, then the figures behind it, each with one plain line.
  Any caveat that changes the size or reading of the answer goes with the answer, not in a footnote.
  Offer a report when the result is worth keeping: see `make-a-report.md`.
