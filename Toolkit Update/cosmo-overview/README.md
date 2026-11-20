# Cosmo overview site

A small static website that introduces Cosmo to colleagues. Open `index.html` in any browser. It needs no internet, no server and no install, so it can sit on a shared drive.

## Files

| File | What it is |
| --- | --- |
| `index.html` | Home page: what Cosmo is, the three ideas, who it is for, and placeholder cards for the skills |
| `deliverables.html`, `brain.html`, `orchestration.html` | One page per idea |
| `cosmo.css` | The whole look: colours, fonts, layout, light and dark, phone width, printing |
| `_components.html` | Every component, shown once with the markup to copy |
| `_template.html` | An empty page with the header, title band, sections and footer in place |

The colours and fonts are the design library's default themes (light TH-01, dark TH-02). The site follows the computer's light or dark setting.

## Add a page

1. Copy `_template.html` and rename it, for example `skills.html`.
2. Change the `<title>`, the title band and the sections. Build the content from `_components.html`.
3. In the header, put `aria-current="page"` on the new page's link.

## Add or switch on a nav entry

The nav is in the header of every page (the `<nav class="nav">` block), so change it on every page.

- New link: add `<a href="skills.html">Skills</a>` before `<span class="nav-gap">`.
- A "coming soon" entry: `<span class="soon" title="Coming soon">Name</span>` after `nav-gap`.
- When a "coming soon" page exists: change its span to a link and move it before `nav-gap`.
- Add the link to the footer's `<ul class="foot-links">` too.

## Change the name or its long form

- Long form ("Claude / Cursor Orchestration and Shared Memory Operating system"): edit the `--expansion` line at the top of `cosmo.css`. It shows on every page from there.
- Short name ("Cosmo"): find and replace `Cosmo` across the `.html` files.

## Fill in a skill card

On the home page, each skill is a placeholder card (`card ph`). Change the name and the line. When it is written, remove ` ph` and the "To be written" tag. To add a skill, copy a whole card.
