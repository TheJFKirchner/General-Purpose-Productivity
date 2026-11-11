---
name: smart-html-editor
description: "View and edit any HTML file in dev mode: opens it in an interactive editor window where the user types over text in place, clicks any part to restyle it (text, colors, fonts, theme), and asks a built-in assistant for changes. Neither the assistant nor Claude Code ever sees the page's data. Use when the user asks to open, view, preview or edit an .html file in dev mode, make quick edits to an HTML report, or change its wording, colors or theme. Also use instead of reading a large HTML file: its outline/find/edit commands work on the page without its data."
---

# Smart HTML Editor

An editor for any HTML file, especially big report pages full of data. It runs locally:

- **Type in place:** double-click any text on the page and type. Enter keeps it, Esc cancels.
- **Click to change:** click part of the page to select it. Use the quick controls (text color, fill, size,
  bold, italic, align, hide), step out to the element around it, or ask the assistant
  ("make this heading teal", "use a darker theme", "bold the region name").
- **Theme:** the Theme tab lists the page's theme colors and fonts (CSS variables) with color pickers.
- **Every change** shows at once. **Save** writes the file and keeps a backup of the original. Undo and
  Discard are there too.
- **No data seen:**
  - The assistant gets a redacted outline: scripts, charts, embedded files and data-table cells are
    summarized, and numbers in text become `{#1}`, `{#2}` tokens.
  - It gets no screenshots and can't type numbers the user didn't type.
  - **Hide data** blurs tables, charts, images and numbers for the person too, e.g. when sharing a screen.

## When the user asks to view or edit an HTML file in dev mode
1. **Setup, once per machine.** Python 3.10+, then `pip install -r <skill>/editor/requirements.txt`.
   - Without the SDK, typing, the controls, the theme and saving all still work; only the assistant is off.
   - The assistant signs in with the Claude Code login. If someone else will use it, flag that API keys are
     expected.
2. **Start it in the background** (it keeps running):
   `python <skill>/editor/she.py open "<path to file.html>"`
   - It prints the address (default `http://127.0.0.1:8790/`) and opens a browser window.
   - Tell the user the address, and that Ctrl+C in that window, or closing it, stops the editor.
   - Unsaved changes are lost when it stops.
3. **Outside Claude Code**, the user can drag an HTML file onto `Open in Smart HTML Editor.cmd` (Windows) or
   run `open-editor.sh <file>` (Mac/Linux).

## Never read the HTML file itself
The editor exists so the data never has to be seen. **Don't use Read, cat, grep, head or a browser
screenshot on the page.** Use these instead (run them, they print the answer):

| Command | Gives |
|---|---|
| `python <skill>/editor/she.py outline <file> [--node n12] [--depth 3]` | The page without its data: element ids (`n12`), text ids (`t45`), tags, classes, short attributes |
| `python <skill>/editor/she.py find <file> "some words"` | Where visible text is (`t45 in n12 <h2> ...`) |
| `python <skill>/editor/she.py theme <file>` | Theme variables (`v1 :root --accent: #2563eb`) and page rules |
| `python <skill>/editor/she.py edit <file> '<json ops>' [--dry-run]` | Applies edits, backs up, saves |

Edit ops (a JSON list, applied in order; each one is checked):
```json
[{"op": "set_text", "id": "t21", "text": "Sales rose {#1} this quarter", "old": "optional part to replace"},
 {"op": "set_style", "node": "n8", "styles": {"color": "#0f766e", "font-size": ""}},
 {"op": "set_attr", "node": "n9", "name": "class", "value": "subtitle lead"},
 {"op": "set_theme_var", "var": "v1", "value": "#dc2626"},
 {"op": "set_page_rule", "selector": ".card h2", "declarations": "color: teal"},
 {"op": "replace_markup", "node": "n13", "html": "<b>New</b> text {#1}"}]
```
- **Numbers:** keep a `{#k}` token to keep its number, or drop it to remove the number. A new number goes
  in only if the user gave it.
- **Ids:** `replace_markup` renumbers the elements after it, so run `outline` again before using their ids.
- **Close the editor first.** Don't run `edit` while the editor has the same file open: the editor would see
  the file change on disk and ask to reload.

## Data, charts and scripts
- **Neither the assistant nor `she.py` changes them.** That means numbers, chart contents, scripts, data tables
  and embedded files.
- **If the user asks for one of these:** say it means reading part of the data. Ask before opening only the
  part named by `outline` (for example one `<script>` by its position), never the whole file.

## Answering "can I view and edit it without seeing the data?"
Yes:
- **The assistant (and Claude Code through `she.py`)** works from the redacted outline only.
- **The person** sees the real page, and can turn on **Hide data** to blur tables, charts, images and numbers
  while editing.
- **Very large pages:** a 48 MB page with 1.5 million elements takes about 10 seconds to open, and each
  edit about a second.

## Changing the editor itself
Read `README.md` (maintainer notes: design, lockdown, files, tests). Don't weaken the assistant's lockdown or
the redaction without the user.
