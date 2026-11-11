# Smart HTML Editor: maintainer notes

For changing the editor itself. To use it, see `SKILL.md`.

An interactive editor for any HTML file, built for big report pages full of data. The page opens in a local
browser window:
- double-click text to type over it;
- click any part to select it, then restyle it with quick controls or ask the assistant;
- recolor the theme from the page's CSS variables.

The assistant is one Claude agent (Haiku by default), modeled on the dashboard agent in
ViteReact-Dashboarding-Skills. **Neither the assistant nor Claude Code ever sees the page's data.**

## How it works (agreed design; don't change without the user)
- **One server, standard library only.** `editor/server.py` serves the editor UI and the page. The Claude
  Agent SDK is imported only when the assistant runs, so everything else works without it.
- **The page in a frame.**
  - `/doc/<file>` serves the page with `data-she-id="nX"` on every element (and `data-she-mask` on
    data-bearing ones). These attributes exist only in what is served, never in the file.
  - Files next to the page (images, CSS, scripts) are served from its folder, so relative links work.
- **Exact positions, minimal edits.**
  - `editor/htmldoc.py` tokenizes the file and builds a tree in which every element and text run knows its
    exact character span.
  - Every edit is one splice of those characters. The rest of the file stays byte for byte as it was:
    encoding, BOM, line endings, entities, formatting.
- **Ids.**
  - `n12` is an element, `t45` a text run, `v3` a theme variable (a CSS custom property in a `<style>` block).
  - Element ids are document order. They stay put through every edit except `replace_markup` and undoing one,
    which renumber what follows.
- **Redaction.** This is everything the assistant (or `she.py outline/find`) can see:
  - `<script>`, `<style>`, `<svg>`, `<canvas>`, `<iframe>`, `<template>`, `<noscript>`, media, drop-downs
    and text boxes become one summary line each ("data block, 155 KB hidden", "graphic, 2 shapes hidden").
  - Data tables become "data table: 4 columns × 2,001 rows; headers ...; cell values hidden". A table counts
    as data if it has more than 25 rows, `<th>` headers and more than 2 rows, or at least 30% numeric cells.
  - Cells show no text except the one cell the person clicked.
  - Numbers in text become `{#1}`, `{#2}` tokens (also in `title`, `alt`, `aria-label`, `placeholder`, `value`).
    Tokens are restored on write. A digit the model types is refused unless it is in the user's own message.
  - `data-*` attributes are hidden, `on*` attributes show as `[script]`, `data:` URLs show their size only,
    and attributes over 200 characters are hidden.
  - More than 12 siblings with the same tag are shown as 3, then "… N more".
  - There are no screenshots. Looks come from the page's computed styles and matching CSS rules (colors,
    fonts, borders, spacing; `url()` redacted), never its text.
- **Typing in place.** The person types the real text in the browser; it is never sent to a model.
  1. A double-click maps the element's DOM text nodes to the source runs (`/api/runs`) and checks they match.
  2. The element becomes `contenteditable="plaintext-only"`. Enter keeps the text, Esc cancels, paste
     becomes plain text.
  3. On commit, the editor checks that only text changed. If structure changed, it reloads the page and says
     why.
  4. The server checks the old text before writing.
- **Step out / look around.** The click is context only. The assistant starts at the selection and, when the
  thing isn't there, looks around:
  - `around`: parent and siblings;
  - `styles`: computed looks of the element and its parents, and the rules that apply;
  - `outline` and `find_text`.

  It then `select`s the element that really holds the thing (the person sees the highlight move) and edits
  there. The step-out button and the breadcrumbs do the same by hand.
- **Changes are live; Save writes.**
  - Each edit applies to an in-memory working copy, and the page reloads, keeping its scroll position.
  - **Undo** reverses one change at a time: in place for simple edits, by reparsing for structural ones.
  - **Discard** drops every unsaved change.
  - **Save** writes the file atomically. The first save of a session copies the original to
    `<page folder>/.smart-html-editor/backups/`.
  - Save refuses if the file changed on disk since it was opened, and the editor shows a reload banner.
- **Page rules** are one `<style id="she-custom">` block placed just before `</body>`. Being last, they win
  at equal specificity, and new elements get the highest ids, so nothing is renumbered. The Theme tab lists
  them, each with a remove button.

## Routing (assistant prompt)
| Request | Tool |
|---|---|
| Words | `set_text` (whole text, or `old_text` → `new_text` within it; long texts need `old_text`) |
| One element's color, background, font, size, spacing, border, alignment, hide | `set_style` |
| class, title, alt, aria-label, href, target, rel, hidden, lang, dir, role | `set_attr` |
| Theme colors/fonts | `set_theme_var` when the page has variables, else `set_page_rule` |
| Many elements alike | `set_page_rule` |
| Bold a word, add a subtitle or bullet | `view_markup` then `replace_markup` (small, data-free elements only) |
| Data, numbers, charts, scripts, adding/removing tables | Refuses: "a Claude Code job" + why |

## Lockdown (enforced in code)
- **SDK options:**
  - `tools=[]` (no built-ins: no file reading or shell);
  - `permission_mode="dontAsk"`;
  - only the 12 `mcp__page__*` tools are allowed;
  - `strict_mcp_config=True`, `setting_sources=[]`, `skills=[]`;
  - memory, connectors and tool search are off;
  - `cwd` is an empty folder in `~/.smart-html-editor/workspace`.
- **Tools:** `outline`, `around`, `select`, `styles`, `find_text`, `view_markup` (read); `set_text`,
  `set_style`, `set_attr`, `set_theme_var`, `set_page_rule`, `replace_markup` (edit).
- **Every edit is checked:**
  - Known ids only. Nothing inside hidden parts. No edits to `<html>` or `<head>`.
  - **CSS values:** at most 300 characters; no `; { } < >`, `url()`, `expression()`, `javascript:`,
    `@import` or backslashes. Property names must look like CSS properties.
  - **`set_attr`:** allowlisted names only. Links can't be `javascript:`, `vbscript:` or `data:` URLs.
  - **Page rules:** the selector is at most 200 characters, with no `{ } < > ; @` or backslashes.
  - **`replace_markup`:**
    - only elements that have an end tag, are at most 6,000 characters, and hold no hidden parts, tables,
      forms, images, comments, or `data-`/`on` attributes;
    - new markup uses only allowlisted text tags and attributes, and its tokens are restored.
  - **Text:** typed digits are refused unless they appear in the user's message, and number tokens must exist.
- **Limits:** 10 turns and 90 seconds per request; 4 refused edits per request.

## Files
- `SKILL.md`: what Claude Code follows.
- `Open in Smart HTML Editor.cmd`: Windows drag-and-drop launcher. `open-editor.sh`: Mac/Linux.
- `editor/she.py`: command line (`open`, `outline`, `find`, `theme`, `edit`).
- `editor/server.py`: HTTP server and routes.
- `editor/workspace.py`: the open file (encoding detection, save, backup), selection, and look requests to
  the page.
- `editor/htmldoc.py`: tokenizer, tree, redacted views, edits, undo, served HTML.
- `editor/assistant.py`: the agent (prompt, tools, SDK options, cost estimate).
- `editor/fake_model.py`: scripted model for tests (`--fake` / `SHE_FAKE=1`).
- `editor/ui/`: `editor.html`, `editor.css`, `editor.js`: frame, selection, typing, quick controls, theme,
  chat, polling.
- `editor/requirements.txt`: `claude-agent-sdk`.
- `tests/`: `make_sample.py` (a big fake report), `test_htmldoc.py` (redaction, edits, undo, parsing),
  `e2e.mjs` (the editor in a real browser).

## Config
- **Env:**
  - `SHE_MODEL` (default `claude-haiku-5-5`) and `SHE_EFFORT` (default `low`);
  - `SHE_PORT` (default 8790; the next free port is used if it's taken);
  - `SHE_FAKE=1`;
  - `SHE_PRICE_IN` / `SHE_PRICE_OUT` (USD per million tokens, for the cost line).
- **Cost line per reply:** an estimate from token usage × pricing, not a bill.
- **Sign-in:** the Claude Code login (no API keys needed for your own use). If others will use it, API keys
  are expected.

## Performance
- **A 335 KB report with 10k elements:** opens in under 0.1 s.
- **A 48 MB page with 1.5M elements** (a 300k-row HTML table):
  - opens in about 11 s;
  - each typed or styled change takes about 1.3 s, and undo of one about the same;
  - outlines are instant.
- **Pages whose bulk is a JSON or script blob** are fast, because a script is one token.

## Limits
- **Content drawn by a page's script** (charts, tables built from JSON) has no source element. Clicking it
  selects the element that holds it. Its contents aren't editable here.
- **Tree building follows HTML's common rules** (implied `</p>`, `</li>`, `</td>`, `</tr>`, ...), not every
  edge case. Typing checks the DOM against the source and refuses where they differ.
- **Hide data is best effort:** cells, charts, images and elements whose own text has numbers are blurred.
- **One file per editor.** Run a second editor on another port for a second file.

## Testing
- **Unit:** `python tests/test_htmldoc.py` (or `pytest tests`). It checks that no data value reaches anything
  the model can see.
- **Browser (no tokens):**
  ```
  python editor/she.py open <copy of tests/sample_report.html> --no-open --fake --port 8790
  node tests/e2e.mjs http://127.0.0.1:8790/ <that copy> [screenshot.png]
  ```
  The suite covers select, type, Hide data, quick color, looks from the page, step out and edit, number
  tokens, theme, page rule, undo, save and backup.
- **Scripted model:** send `FAKE: [steps]` in the chat; see `editor/fake_model.py`.
- **Never run the real model in tests.** For a live check, ask the user first.
