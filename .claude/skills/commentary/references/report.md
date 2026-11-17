# Report

Worked example: `examples/report_html/` in this skill folder. Everything in `deck.md` applies, with these differences:

- Placement is a report section, not a slide.
- Files: `.html` or `.md` (any text file works).
  - HTML: bullets become `<ul class="commentary">`, a paragraph-style unit becomes `<p class="commentary">`. Text is HTML-escaped.
  - Markdown: `- ` bullets at the placeholder's indentation.
- `format: "paragraph"` suits narrative sections (`bullets: 1`, `max_words` 60–80).
- Next edition of the same report: copy the plan and the shell into the new edition's folder. On generators that should refer back, set `"use_prior": true, "prior_file": "<last edition>/commentary_outputs"` (the newest file there is used).
