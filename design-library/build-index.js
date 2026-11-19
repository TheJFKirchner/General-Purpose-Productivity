#!/usr/bin/env node

/**
 * Rebuilds index.md (for planning) and index.html (for browsing) from the items themselves.
 * The item files are the only source; never edit the two index files by hand. No dependencies.
 *
 *   Slides: COMPONENT comments in slides/<group>/slides.html
 *   Other types: an item header in each file of charts/, dashboard-sections/, report-blocks/, themes/
 *     "# CT-01 · name" (Markdown heading) or "ITEM: TH-01 · name" (inside a code comment),
 *     then "Looks like: ...", "Good for: a; b", and optionally "Related: ..." and "Files: ...".
 *
 * Usage: node build-index.js
 */

const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const SLIDE_ORDER = ['FR', 'EX', 'LV', 'CH', 'CP', 'BD', 'UN', 'DE', 'BK'];
const TYPES = [
  { folder: 'charts', title: 'Charts', prefix: 'CT', blurb: 'ECharts option recipes on the theme tokens. Copy the option and replace the data.' },
  { folder: 'dashboard-sections', title: 'Dashboard sections', prefix: 'DS', blurb: 'Reusable sections for a dashboard page.' },
  { folder: 'report-blocks', title: 'Report blocks', prefix: 'RB', blurb: 'Reusable blocks for a written analysis report.' },
  { folder: 'themes', title: 'Themes', prefix: 'TH', blurb: 'The shared look. Every template carries the same tokens.' },
];

const GROUP_RE = /<!-- GROUP: (\w+) · (.*?) · (.*?) -->/;
const COMPONENT_RE = /<!-- COMPONENT: ([A-Z]+-\d+) · ([\w-]+)\s+Looks like: (.*?)\s+Good for: (.*?)\s+Related: (.*?) -->\s*<section\b([^>]*)>/gs;
const ITEM_RE = /^(?:\s*#+\s*|.*?ITEM:\s*)([A-Z]{2}-\d+) · ([\w-]+)\s*$/m;

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const splitRelated = text => !text || text.trim() === 'none' ? [] : text.split(',').map(s => s.trim().split(/\s+/)[0]).filter(Boolean);
const field = (text, name) => { const m = text.match(new RegExp('^[\\s*/#-]*' + name + ':\\s*(.+?)\\s*(?:-->|\\*/)?\\s*$', 'm')); return m ? m[1].trim() : ''; };

function readSlides(problems) {
  const dir = path.join(ROOT, 'slides');
  const groups = [];
  if (!fs.existsSync(dir)) return groups;
  fs.readdirSync(dir, { withFileTypes: true }).filter(d => d.isDirectory()).forEach(d => {
    const file = path.join(dir, d.name, 'slides.html');
    if (!fs.existsSync(file)) return;
    const html = fs.readFileSync(file, 'utf8');
    const slides = html.slice(html.indexOf('<!-- SLIDES:START -->'), html.indexOf('<!-- SLIDES:END -->'));
    const g = slides.match(GROUP_RE);
    if (!g) { problems.push(`slides/${d.name}: no <!-- GROUP: ... --> comment`); return; }
    const group = { folder: d.name, prefix: g[1], title: g[2], blurb: g[3], items: [] };
    for (const m of slides.matchAll(COMPONENT_RE)) {
      const [, code, name, look, good, related, attrs] = m;
      const id = (attrs.match(/\bid="([^"]+)"/) || [])[1];
      const attrCode = (attrs.match(/data-component="([^"]+)"/) || [])[1];
      if (id !== name) problems.push(`${code}: comment names "${name}" but the section id is "${id}"`);
      if (attrCode !== code) problems.push(`${code}: data-component is "${attrCode}"`);
      if (!code.startsWith(group.prefix + '-')) problems.push(`${code}: prefix does not match its group (${group.prefix})`);
      group.items.push({ code, name, look: look.trim(), goodFor: good.split(';').map(s => s.trim()).filter(Boolean),
        related: splitRelated(related), link: `slides/${d.name}/slides.html#/${name}` });
    }
    const sections = (slides.match(/<section\b/g) || []).length;
    if (sections !== group.items.length) problems.push(`slides/${d.name}: ${sections} slides but ${group.items.length} COMPONENT comments`);
    groups.push(group);
  });
  groups.sort((a, b) => (SLIDE_ORDER.indexOf(a.prefix) + 99) % 99 - (SLIDE_ORDER.indexOf(b.prefix) + 99) % 99 || a.prefix.localeCompare(b.prefix));
  return groups;
}

function readType(type, problems) {
  const dir = path.join(ROOT, type.folder);
  const items = [];
  if (!fs.existsSync(dir)) return items;
  fs.readdirSync(dir).filter(f => f.toLowerCase() !== 'readme.md').sort().forEach(f => {
    const full = path.join(dir, f);
    if (!fs.statSync(full).isFile()) return;
    const text = fs.readFileSync(full, 'utf8');
    const m = text.match(ITEM_RE);
    if (!m) return; // a supporting file (data, a second theme file), named under its item's "Files:"
    const [, code, name] = m;
    if (!code.startsWith(type.prefix + '-')) problems.push(`${type.folder}/${f}: code ${code} should start ${type.prefix}-`);
    const look = field(text, 'Looks like');
    const goodFor = field(text, 'Good for').split(';').map(s => s.trim()).filter(Boolean);
    if (!look) problems.push(`${code}: no "Looks like:" line`);
    const files = field(text, 'Files');
    items.push({ code, name, look, goodFor, related: splitRelated(field(text, 'Related')),
      link: `${type.folder}/${f}`, files: files ? files.split(',').map(s => s.trim()) : [] });
  });
  items.sort((a, b) => a.code.localeCompare(b.code, 'en', { numeric: true }));
  return items;
}

function main() {
  const problems = [];
  const groups = readSlides(problems);
  const types = TYPES.map(t => ({ ...t, items: readType(t, problems) }));

  const all = [...groups.flatMap(g => g.items), ...types.flatMap(t => t.items)];
  const byCode = {};
  const names = {};
  all.forEach(c => {
    if (byCode[c.code]) problems.push(`${c.code}: used twice`);
    byCode[c.code] = c;
    if (c.goodFor.length < 2 || c.goodFor.length > 3) problems.push(`${c.code}: "Good for" needs 2 or 3 items, has ${c.goodFor.length}`);
  });
  groups.flatMap(g => g.items).forEach(c => {
    if (names[c.name]) problems.push(`"${c.name}": slide name used by ${names[c.name]} and ${c.code}`);
    names[c.name] = c.code;
  });
  all.forEach(c => c.related.forEach(r => { if (!byCode[r]) problems.push(`${c.code}: related item ${r} does not exist`); }));

  // One stylesheet: the sample slides and the presentation skill's base theme must stay identical
  const skillCss = path.join(ROOT, '..', '.claude', 'skills', 'presentation', 'references', 'base-styles.css');
  const libCss = path.join(ROOT, 'slides', 'styles.css');
  if (fs.existsSync(skillCss) && fs.existsSync(libCss) && fs.readFileSync(skillCss, 'utf8') !== fs.readFileSync(libCss, 'utf8'))
    problems.push('slides/styles.css differs from references/base-styles.css in the presentation skill; copy the skill file over it');

  const row = c => `| ${c.code} | \`${c.name}\` | ${c.look} | ${c.goodFor.map(x => '• ' + x).join('<br>')} |`;
  const head = ['| Code | Name | Looks like | Good for |', '| --- | --- | --- | --- |'];
  const empty = t => `None yet. To add one: [README.md](README.md), "Adding an item". Codes start \`${t.prefix}-\`.`;

  // index.md
  const md = ['# Design library index', '',
    'Reusable design items by type. Descriptions only: plan from this page, and let the builder or design subagent open only the items it names.', '',
    '- Pick by "Good for", not by subject. Sample subject matter is placeholder.',
    '- Path to a slide: its group folder plus its name: `CP-01 slides/compare/slides.html#/paired-bars-commentary`. Other items: `<folder>/<name>.md` (themes: `themes/look.css`).',
    '- Browse: open `index.html`. Add an item: `README.md`.',
    '- Generated by `build-index.js` from the item files. Do not edit by hand.', '',
    '## Slides', '', 'One sample slide per component, grouped by what the slide has to do. Look: `slides/styles.css`.', ''];
  groups.forEach(g => {
    md.push(`### ${g.title}`, '', `${g.blurb} Folder: \`slides/${g.folder}\``, '', ...head);
    g.items.forEach(c => md.push(row(c)));
    md.push('');
  });
  types.forEach(t => {
    md.push(`## ${t.title}`, '', t.items.length ? t.blurb : empty(t), '');
    if (t.items.length) { md.push(...head); t.items.forEach(c => md.push(row(c))); md.push(''); }
  });
  fs.writeFileSync(path.join(ROOT, 'index.md'), md.join('\n'));

  // index.html
  const card = c => {
    const related = c.related.filter(r => byCode[r]).map(r => `<a href="#${esc(byCode[r].code)}">${esc(r)}</a>`).join(' ');
    return `<div class="item" id="${esc(c.code)}"><a class="open" href="${esc(c.link)}"><span class="code">${esc(c.code)}</span><h3>${esc(c.name)}</h3></a>` +
      `<p class="look">${esc(c.look)}</p><ul>${c.goodFor.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` +
      (related ? `<p class="related">Related: ${related}</p>` : '') + '</div>';
  };
  const slideHtml = groups.map(g => `<h3 class="group" id="${esc(g.folder)}">${esc(g.title)}</h3><p class="blurb">${esc(g.blurb)}</p><div class="grid">${g.items.map(card).join('\n')}</div>`).join('\n');
  const typeHtml = types.map(t => `<h2 id="${esc(t.folder)}">${esc(t.title)}</h2>` +
    (t.items.length ? `<p class="blurb">${esc(t.blurb)}</p><div class="grid">${t.items.map(card).join('\n')}</div>`
      : `<p class="blurb">None yet. To add one, see README.md, "Adding an item".</p>`)).join('\n');
  const nav = ['<a href="#slides"><b>Slides</b></a>', ...groups.map(g => `<a href="#${esc(g.folder)}">${esc(g.title)}</a>`),
    ...types.map(t => `<a href="#${esc(t.folder)}"><b>${esc(t.title)}</b></a>`)].join('');
  fs.writeFileSync(path.join(ROOT, 'index.html'), `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design library</title>
<style>
  :root { --blue: #0170BC; --navy: #002D72; --ink: #1F2A37; --muted: #5B6770; --rule: #D9E2EA; --wash: #F4F8FB; --paper: #FFFFFF; }
  html { scroll-behavior: smooth; scroll-padding-top: 70px; }
  body { font-family: "Segoe UI", system-ui, sans-serif; color: var(--ink); background: var(--wash); margin: 0; }
  nav { position: sticky; top: 0; background: var(--paper); border-bottom: 1px solid var(--rule); padding: 12px 28px; display: flex; flex-wrap: wrap; gap: 6px 18px; z-index: 2; }
  nav a { font-size: 13px; color: var(--muted); text-decoration: none; } nav a b { color: var(--navy); font-weight: 600; } nav a:hover { color: var(--blue); }
  main { max-width: 1180px; margin: 0 auto; padding: 32px 28px 80px; }
  h1 { font-size: 30px; margin: 0 0 6px; color: var(--navy); } .intro { color: var(--muted); margin: 0 0 8px; max-width: 780px; }
  h2 { font-size: 22px; margin: 48px 0 2px; padding-top: 22px; border-top: 2px solid var(--navy); color: var(--navy); }
  h3.group { font-size: 17px; margin: 30px 0 2px; color: var(--navy); } .blurb { color: var(--muted); margin: 0 0 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 14px; }
  .item { background: var(--paper); border: 1px solid var(--rule); border-radius: 2px; padding: 18px 20px; transition: border-color 0.15s ease; }
  .item:hover { border-color: var(--blue); } .item:target { border-color: var(--blue); box-shadow: inset 4px 0 0 var(--blue); }
  .open { display: flex; align-items: baseline; gap: 10px; text-decoration: none; } .open:hover h3 { text-decoration: underline; }
  .code { font: 600 12px Consolas, monospace; color: var(--paper); background: var(--blue); padding: 3px 8px; border-radius: 2px; white-space: nowrap; }
  .item h3 { font-size: 15px; margin: 0 0 8px; color: var(--navy); font-weight: 600; }
  .look { font-size: 14px; margin: 0 0 10px; } ul { margin: 0; padding-left: 18px; } li { font-size: 14px; margin-bottom: 4px; }
  .related { font-size: 12.5px; color: var(--muted); margin: 12px 0 0; } .related a { font-family: Consolas, monospace; color: var(--blue); text-decoration: none; margin-left: 4px; }
</style></head><body>
<nav>${nav}</nav>
<main>
<h1>Design library</h1>
<p class="intro">${all.length} reusable design items by type. Click a name to open it; on a sample slide, "Library index" brings you back here. Subject matter in the samples is placeholder; the pattern is what gets reused.</p>
<h2 id="slides">Slides</h2>
${slideHtml}
${typeHtml}
</main></body></html>
`);

  const counts = [`${groups.reduce((n, g) => n + g.items.length, 0)} slides in ${groups.length} groups`, ...types.map(t => `${t.items.length} ${t.title.toLowerCase()}`)];
  console.log(`${counts.join(', ')}. Wrote index.md and index.html.`);
  if (problems.length) {
    console.log(`\n${problems.length} to fix:`);
    problems.forEach(p => console.log('  - ' + p));
    process.exit(1);
  }
}

main();
