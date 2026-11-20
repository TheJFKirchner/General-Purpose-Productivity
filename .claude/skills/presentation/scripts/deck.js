#!/usr/bin/env node
/**
 * deck.js: a slide deck made of design-library items, one file per slide. No dependencies.
 *
 *   node deck.js new <name or folder> --title "..." [--theme TH-02]      a plain name goes in decks/<name>
 *   node deck.js show <id> [<deck>] [--data <file> | --from "<report>::<section>::<table>"]
 *       an item's parts (spots or data slots); with data, the columns that fit and a ready add command
 *   node deck.js add <deck> <id> [<item id>] [--after <slide>] [--id <name>] [--section <name>] [--headline "..."]
 *       [--data <file.csv|.json> | --from "<report folder>::<section>[::<table>]"] [--slot <name>=<col>[,<col>]] ...
 *       [--format $short|short|$,|,|%|none] [--agg sum|mean] [--spot chart-2]
 *   node deck.js animate <deck> [<slide>] <AN id> [--spot chart] [--data ... | --from ...] [--slot ...] [and add's options]
 *       an animation as a slide of its own, or into the spot of an existing slide that holds what it moves
 *   node deck.js own <deck> [--after <slide>] [--id <name>] [--section <name>] [--headline "..."]
 *   node deck.js list <deck>
 *   node deck.js refill <deck> [<slide>]
 *   node deck.js theme <deck> <TH id>
 *   node deck.js place <deck> <slide> left|right|full
 *   node deck.js build <deck>
 *   node deck.js check <deck> [--browser <path>]
 *
 * <deck> is the deck folder (or its presentation.html). Each slide is slides/NN-<name>.html; the number orders them.
 * presentation.html is built from those files. Copied items follow the design library's AUTHORING.md,
 * "Adding an item to a project". Engine adapted from github.com/ryanbbrown/revealjs-skill (MIT).
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');

const SKILL = path.join(__dirname, '..');
const BASE_CSS = path.join(SKILL, 'references', 'base-styles.css');
const SLIDE_ID = /^(FR|EX|LV|CH|CP|BD|UN|DE|BK)-\d{2,}$/;
const ITEM_ID = /^(CT|TB|HC)-\d{2,}$/;
const PERIOD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(\s*'?\d{2,4})?$|^\d{4}[-/]\d{1,2}(-\d{1,2})?$|^q[1-4]\s*'?\d{2,4}$|^\d{4}\s*q[1-4]$|^\d{4}$/i;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}/;
const SAMPLE = /Sample values|Heading: what|Caption: the|What is measured, the period and the basis|"(Group|Measure|Part|Item) [A-Z]"/;
const VALUE_FLAGS = new Set(['title', 'theme', 'after', 'id', 'section', 'headline', 'data', 'from', 'slot', 'format', 'agg', 'spot', 'library', 'browser', 'by', 'top']);
const BROWSERS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge',
];
const ME = `node "${__filename}"`;

function stop(msg) { console.error('STOP: ' + msg); process.exit(1); }
const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escA = t => esc(t).replace(/"/g, '&quot;');
const unesc = t => String(t).replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const pretty = c => String(c).replace(/[_]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/^./, x => x.toUpperCase());
const slug = t => String(t).toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, ' ').trim().split(' ')
  .filter(w => !/^(the|a|an|of|in|by|and|to|for|on|is|was|at|word)$/.test(w)).slice(0, 4).join('-') || 'slide';
const rel = (from, to) => path.relative(from, to).split(path.sep).join('/') || '.';

/* ---------------------------------------------------------------- arguments */
/* Git Bash paths (/c/Users/...) as Windows paths. */
const fixPath = p => (process.platform === 'win32' && typeof p === 'string' ? p.replace(/^\/([a-zA-Z])(?=\/|$)/, (m, d) => `${d.toUpperCase()}:`) : p);
function parseArgs(argv) {
  const pos = [], opt = {}, slots = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) { pos.push(fixPath(a)); continue; }
    const k = a.slice(2);
    if (!VALUE_FLAGS.has(k)) { opt[k] = true; continue; }
    if (argv[i + 1] === undefined) stop(`--${k} needs a value`);
    if (k === 'slot') slots.push(argv[++i]); else opt[k] = fixPath(argv[++i]);
  }
  return { pos, opt, slots };
}

/* ---------------------------------------------------------------- a small HTML tree (as in the library's item.js) */
const VOID = /^(area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)$/i;
function parse(html) {
  const root = { tag: '#root', children: [] }, stack = [root];
  const re = /<!--[\s\S]*?-->|<(\/?)([a-zA-Z][\w-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g;
  let last = 0, m;
  const top = () => stack[stack.length - 1];
  while ((m = re.exec(html))) {
    if (m.index > last) top().children.push(html.slice(last, m.index));
    last = re.lastIndex;
    if (m[0].startsWith('<!--')) { top().children.push({ comment: m[0] }); continue; }
    const tag = m[2].toLowerCase();
    if (m[1]) { const i = stack.map(n => n.tag).lastIndexOf(tag); if (i > 0) stack.length = i; continue; }
    const node = { tag, attrs: attrsOf(m[3].replace(/\/\s*$/, '')), children: [] };
    top().children.push(node);
    if (tag === 'script' || tag === 'style') {
      const end = html.toLowerCase().indexOf(`</${tag}`, last);
      node.raw = html.slice(last, end === -1 ? html.length : end);
      last = end === -1 ? html.length : html.indexOf('>', end) + 1;
      re.lastIndex = last;
    } else if (!VOID.test(tag) && !/\/\s*$/.test(m[3])) stack.push(node);
  }
  if (last < html.length) top().children.push(html.slice(last));
  return root;
}
function attrsOf(s) {
  const out = [];
  for (const a of s.matchAll(/([^\s=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"']+))?/g)) out.push([a[1], a[2] === undefined ? null : a[2].replace(/^["']|["']$/g, '')]);
  return out;
}
const attr = (n, k) => { const a = n.attrs && n.attrs.find(x => x[0] === k); return a ? (a[1] === null ? '' : a[1]) : null; };
function setAttr(n, k, v) { const a = n.attrs.find(x => x[0] === k); if (v === null) n.attrs = n.attrs.filter(x => x[0] !== k); else if (a) a[1] = v; else n.attrs.push([k, v]); }
function serialize(n) {
  if (typeof n === 'string') return n;
  if (n.comment) return n.comment;
  const inner = n.raw !== undefined ? n.raw : n.children.map(serialize).join('');
  if (n.tag === '#root') return inner;
  const open = `<${n.tag}${n.attrs.map(([k, v]) => (v === null ? ` ${k}` : ` ${k}="${v}"`)).join('')}>`;
  return VOID.test(n.tag) ? open : `${open}${inner}</${n.tag}>`;
}
function walk(n, fn, parent) { if (typeof n !== 'object' || n.comment) return; if (fn(n, parent) === false) return; (n.children || []).forEach(c => walk(c, fn, n)); }
const elements = n => (n.children || []).filter(c => typeof c === 'object' && !c.comment);
const textOf = n => (typeof n === 'string' ? n : n.comment || n.raw !== undefined ? '' : (n.children || []).map(textOf).join(''));
/* pre before the own text of every element inside n that has some (a quote and its cite both get it) */
function prefixAll(n, pre, skipEl) {
  let any = false;
  walk(n, x => {
    if (x.raw !== undefined || (skipEl && x !== n && skipEl(x))) return false;
    const i = (x.children || []).findIndex(c => typeof c === 'string' && c.trim());
    if (i !== -1 && !x.children[i].trim().startsWith(pre.trim())) { x.children[i] = x.children[i].replace(/^(\s*)/, `$1${pre}`); any = true; }
  });
  return any;
}
function prefixText(n, pre) {   // put pre before the first visible text inside n
  for (let i = 0; i < n.children.length; i++) {
    const c = n.children[i];
    if (typeof c === 'string') { if (c.trim()) { n.children[i] = c.replace(/^(\s*)/, `$1${pre}`); return true; } }
    else if (!c.comment && c.raw === undefined && prefixText(c, pre)) return true;
  }
  return false;
}

/* ---------------------------------------------------------------- the deck folder */
/* Where decks go. Default: decks/ beside the project's CLAUDE.md (the nearest one above), else decks/ here.
   The project map can override it: a "Decks: <folder>" line, or a map row whose "Holds" cell starts with "Decks"
   (or an older per-deck row "Deck: ...", whose parent folder is used). */
function decksHome(from) {
  for (let d = path.resolve(from), i = 0; i < 10; i++, d = path.dirname(d)) {
    const md = path.join(d, 'CLAUDE.md');
    if (fs.existsSync(md)) {
      const t = fs.readFileSync(md, 'utf8');
      const line = t.match(/^\s*Decks:\s*`?([^`\n]+?)`?\s*$/m), row = t.match(/^\|\s*`?([^`|]+?)`?\s*\|\s*Decks\b[^|]*\|/m), old = t.match(/^\|\s*`?([^`|]+?)`?\s*\|\s*Deck:[^|]*\|/m);
      if (line || row) return { folder: path.resolve(d, (line || row)[1].trim()), why: `set by the project map in ${md}` };
      if (old) return { folder: path.dirname(path.resolve(d, old[1].trim().replace(/[\\/]+$/, ''))), why: `where the project map's deck rows are (${md})` };
      return { folder: path.join(d, 'decks'), why: 'the default: decks/ beside the project\'s CLAUDE.md' };
    }
    if (d === path.dirname(d)) break;
  }
  return { folder: path.resolve(from, 'decks'), why: 'the default: decks/ in this folder (no project CLAUDE.md found above it)' };
}
const plainName = p => !/[\\/]/.test(p) && !/^[a-zA-Z]:/.test(p) && !/\.html?$/i.test(p);
function resolveDeck(p) {
  let d = path.resolve(p);
  if (/\.html?$/i.test(d)) d = path.dirname(d);
  if (fs.existsSync(d)) return d;
  if (plainName(p)) { const h = path.join(decksHome(process.cwd()).folder, p); if (fs.existsSync(h)) return h; }
  return null;
}
function deckOf(p) {
  if (!p) stop('give the deck: its folder, or its name when it is in the decks folder');
  const d = resolveDeck(p);
  if (!d) stop(`no deck "${p}" (looked for ${path.resolve(p)}${plainName(p) ? ` and ${path.join(decksHome(process.cwd()).folder, p)}` : ''})`);
  return d;
}
function fileKey(f) { const m = f.match(/^(\d+)([a-z]?)-/i); return [Number(m[1]), m[2].toLowerCase(), f]; }
function slideFiles(dir) {
  const s = path.join(dir, 'slides');
  if (!fs.existsSync(s)) {
    if (fs.existsSync(path.join(dir, 'presentation.html'))) stop(`${dir} is a deck made by the old scripts (no slides/ folder). It still opens; edit its slides by hand in presentation.html between SLIDES:START and SLIDES:END. check, theme and screenshot work on it; add, own, place, refill and build do not.`);
    stop(`no slides/ folder in ${dir}. Make a deck first: ${ME} new <folder> --title "..."`);
  }
  return fs.readdirSync(s).filter(f => /^\d+[a-z]?-[^.]+\.html$/i.test(f)).sort((a, b) => {
    const x = fileKey(a), y = fileKey(b); return x[0] - y[0] || x[1].localeCompare(y[1]) || x[2].localeCompare(y[2]);
  });
}
function readSlide(dir, f) {
  const text = fs.readFileSync(path.join(dir, 'slides', f), 'utf8');
  const open = text.match(/<section\b([^>]*)>/);
  return { file: f, text, id: open ? (open[1].match(/\bid="([^"]*)"/) || [])[1] || '' : '', attrs: open ? open[1] : '' };
}
function findSlide(dir, files, key) {
  if (key === undefined) stop('say which slide: its number, its id or its file name (deck.js list shows them)');
  const k = String(key);
  let i = /^\d+$/.test(k) ? Number(k) - 1 : files.findIndex(f => f === k || f.replace(/\.html$/, '') === k);
  if (i < 0) i = files.findIndex(f => readSlide(dir, f).id === k || f.replace(/^\d+[a-z]?-/, '').replace(/\.html$/, '') === k);
  if (i < 0 || i >= files.length) stop(`no slide "${k}". ${ME} list "${dir}" shows them`);
  return i;
}
function titleOf(dir) {
  const p = path.join(dir, 'presentation.html');
  const t = fs.existsSync(p) ? (fs.readFileSync(p, 'utf8').match(/<title>([\s\S]*?)<\/title>/) || [])[1] : null;
  return t ? unesc(t) : path.basename(dir);
}
/* Renumber the slide files 01, 02 ... in the given order (names after the number kept). */
function renumber(dir, order) {
  const s = path.join(dir, 'slides'), w = String(order.length).length > 2 ? 3 : 2;
  const named = order.map((f, i) => ({ from: f, to: `${String(i + 1).padStart(w, '0')}-${f.replace(/^\d+[a-z]?-/, '')}` }));
  named.forEach((n, i) => { if (n.from !== n.to && fs.existsSync(path.join(s, n.from))) fs.renameSync(path.join(s, n.from), path.join(s, `~${i}.tmp`)); });
  named.forEach((n, i) => { if (n.from !== n.to && fs.existsSync(path.join(s, `~${i}.tmp`))) fs.renameSync(path.join(s, `~${i}.tmp`), path.join(s, n.to)); });
  return named.map(n => n.to);
}

/* ---------------------------------------------------------------- the design library */
function findLibrary(dir, given, quiet) {
  const cands = [];
  if (given) cands.push(path.resolve(given));
  for (let d = path.resolve(dir), i = 0; i < 10; i++, d = path.dirname(d)) {
    const md = path.join(d, 'CLAUDE.md');
    if (fs.existsSync(md)) {
      const m = fs.readFileSync(md, 'utf8').match(/Design library:\**\s*`?([^`\n|]+?)`?\s*(?:\||$)/m);
      if (m) { const p = m[1].trim().replace(/^\[[^\]]*\]\(([^)]+)\)$/, '$1').replace(/^~(?=[\\/])/, os.homedir()); cands.push(path.resolve(d, p)); }
    }
    if (d === path.dirname(d)) break;
  }
  const home = path.resolve(SKILL, '..', '..', '..');   // the folder holding .claude
  cands.push(path.join(home, 'design-library'), path.join(home, 'Toolkit Update', 'design-library'));
  for (let d = path.resolve(dir); ; d = path.dirname(d)) {
    cands.push(path.join(d, 'design-library'), path.join(d, 'Toolkit Update', 'design-library'));
    if (d === path.dirname(d)) break;
  }
  const hit = cands.find(c => fs.existsSync(path.join(c, 'item.js')));
  if (!hit && quiet) return null;
  if (!hit) stop(`design library not found (no item.js). Looked in:\n  ${[...new Set(cands)].slice(0, 6).join('\n  ')}\nAdd --library <folder>, or a "Design library: <path>" line to the project's CLAUDE.md.`);
  return hit;
}
let ITEM = null;
function lib(dir, given) { if (!ITEM) { const l = findLibrary(dir, given); ITEM = require(path.join(l, 'item.js')); ITEM.folder = l; } return ITEM; }
function themeFrom(libFolder, id) {
  if (!/^TH-\d{2,}$/.test(id || '')) stop('a theme is a library id such as TH-02 (the library\'s index/themes.md lists them)');
  const r = spawnSync(process.execPath, [path.join(libFolder, 'item.js'), 'theme', id, '--json', '--fonts'], { cwd: libFolder, encoding: 'utf8' });
  if (r.status) stop((r.stderr || r.stdout).trim().replace(/^STOP: /, ''));
  return JSON.parse(r.stdout);
}
function themeBlock(t) {
  return `/* THEME:START ${t.id} ${t.name}: written by deck.js theme; do not edit */\n:root {\n` +
    Object.entries(t.css).map(([k, v]) => `  ${k}: ${v};`).join('\n') + `\n  --series: ${t.series.join(' ')};\n}\n` +
    (t.fonts ? t.fonts.trim() + '\n' : '') + '/* THEME:END */';
}
function applyTheme(dir, libFolder, id) {
  const t = themeFrom(libFolder, id), f = path.join(dir, 'styles.css');
  if (!fs.existsSync(f)) stop(`no styles.css in ${dir}`);
  let css = fs.readFileSync(f, 'utf8');
  const block = themeBlock(t);
  if (/\/\* THEME:START[\s\S]*?\/\* THEME:END \*\//.test(css)) css = css.replace(/\/\* THEME:START[\s\S]*?\/\* THEME:END \*\//, () => block);
  else {   // a deck from the old scripts: its tokens sit in the first :root block; the theme goes after it and wins
    const m = css.match(/^:root \{[\s\S]*?^\}/m);
    css = m ? css.slice(0, m.index + m[0].length) + '\n\n' + block + css.slice(m.index + m[0].length) : block + '\n\n' + css;
  }
  fs.writeFileSync(f, css);
  const keep = t.licence ? path.basename(t.licence) : null;
  fs.readdirSync(dir).filter(x => /-OFL\.txt$/i.test(x) && x !== keep).forEach(x => { fs.rmSync(path.join(dir, x)); t.removed = (t.removed || []).concat(x); });   // the font left with the theme that brought it
  if (t.licence && fs.existsSync(path.join(libFolder, t.licence))) fs.copyFileSync(path.join(libFolder, t.licence), path.join(dir, keep));
  return t;
}

/* ---------------------------------------------------------------- styles.css and the built page */
const SETTINGS = `/* Deck look. Change the settings below for spacing and sizes, then open presentation.html again.
   Theme colours and fonts: deck.js theme <deck> <TH id> rewrites the THEME block. */
:root {
  /* Spacing */
  --slide-padding: 72px;         /* left and right edges of every slide */
  --slide-padding-top: 48px;
  --slide-padding-bottom: 84px;  /* leaves room for the section bar */
  --content-gap: 26px;           /* between the headline and the body */
  --split-gap: 40px;             /* between a chart and its commentary */

  /* Sizes (pt on the fixed 1280 x 720 slide) */
  --base-font-size: 32px;
  --text-size: 16pt;
  --h1-size: 46pt;
  --h2-size: 28pt;
  --h3-size: 18pt;
  --footnote-size: 10pt;
  --box-radius: 2px;

  /* Title and divider slides */
  --section-divider-bg: var(--paper);
  --divider-text: var(--navy);
}`;
const DECK_EXTRA = `/* ---- library items on a slide (deck.js) ---- */
.reveal .slides [data-item] { min-height: 0; min-width: 0; }
.reveal .slides [data-item] .chart[data-echart] { height: auto; flex: 1 1 0; min-height: 0; }
.reveal .slides [data-item] .lib-cards { gap: 16px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.reveal .lib-table { margin: 0; width: 100%; }
.reveal .lib-table th, .reveal .lib-table td { padding: 9px 12px; text-align: right; border-bottom: 1px solid var(--rule); font-size: 13pt; color: var(--ink); }
.reveal .lib-table th { font-size: 9.5pt; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); border-bottom: 2px solid var(--navy); }
.reveal .lib-table .left, .reveal .lib-table th.left { text-align: left; }
.reveal .lib-table tfoot td { font-weight: 700; border-top: 2px solid var(--navy); border-bottom: none; }
.reveal .lib-panel h2 { font-size: 15pt; max-width: none; }
/* where the chart sits (deck.js place): full width puts the commentary under it, bullets side by side */
.reveal [data-place="full"] > .commentary { justify-content: flex-start; }
.reveal [data-place="full"] > .commentary ul { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: var(--split-gap); }
.reveal [data-place="full"] > .commentary ul li { margin-bottom: 0; }`;

function baseRest() {
  const base = fs.readFileSync(BASE_CSS, 'utf8').replace(/\r\n/g, '\n');
  const m = base.match(/^:root \{[\s\S]*?^\}/m);
  return (m ? base.slice(m.index + m[0].length) : base).trim();
}
function stylesCss(theme, hostCss) {
  return `${SETTINGS}\n\n${themeBlock(theme)}\n\n/* ---- base look (from the presentation skill; adapted from github.com/ryanbbrown/revealjs-skill, MIT) ---- */\n${baseRest()}\n\n` +
    `/* ---- host.css, copied from the design library ---- */\n${hostCss.trim()}\n\n${DECK_EXTRA}\n`;
}

const ENGINE = `(function () {
      if (location.search.indexOf('export') !== -1) document.documentElement.classList.add('is-export');
      var isExport = document.documentElement.classList.contains('is-export');
      Reveal.initialize({ width: 1280, height: 720, margin: 0, controls: false, progress: false, slideNumber: false, hash: true,
        transition: isExport ? 'none' : 'slide', backgroundTransition: 'fade', center: false });
      /* Bottom section bar, built from data-section on the slides. A slide with no data-section continues the
         previous one; data-section="" ends the sections. */
      var bar = document.querySelector('.section-bar'), slides = [], sections = [], count;
      function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
      function buildBar() {
        slides = Reveal.getSlides(); sections = []; var last = '';
        slides.forEach(function (s) {
          if (s.dataset.section !== undefined) last = s.dataset.section;
          s._sec = -1; if (!last) return;
          var top = sections[sections.length - 1];
          if (!top || top.name !== last) { top = { name: last, first: s, count: 0 }; sections.push(top); }
          top.count++; s._sec = sections.length - 1; s._pos = top.count;
        });
        bar.innerHTML = ''; bar.appendChild(el('div', 'bar-title', document.title));
        var list = el('div', 'bar-list');
        sections.forEach(function (sec) {
          var li = el('div', 'bar-item'); li.title = sec.name; li.appendChild(el('span', 'bar-name', sec.name));
          var track = el('span', 'bar-track'); sec.fill = el('i'); track.appendChild(sec.fill); li.appendChild(track);
          li.addEventListener('click', function () { var i = Reveal.getIndices(sec.first); Reveal.slide(i.h, i.v); });
          list.appendChild(li); sec.li = li;
        });
        bar.appendChild(list); count = el('div', 'bar-count'); bar.appendChild(count);
      }
      function updateBar() {
        var cur = Reveal.getCurrentSlide(); if (!cur || !count) return;
        sections.forEach(function (sec, k) {
          sec.fill.style.width = (k < cur._sec ? 100 : k === cur._sec ? Math.round(100 * cur._pos / sec.count) : 0) + '%';
          sec.li.classList.toggle('is-current', k === cur._sec); sec.li.classList.toggle('is-done', cur._sec > k);
        });
        count.textContent = (slides.indexOf(cur) + 1) + ' / ' + slides.length;
        bar.classList.toggle('is-hidden', cur._sec === -1 || cur.dataset.bar === 'hide' || !sections.length);
      }
      function placeBar() {
        var s = Reveal.getScale(), box = document.querySelector('.reveal');
        bar.style.setProperty('--deck-scale', s); bar.style.width = (1280 * s) + 'px';
        bar.style.left = Math.max(0, (box.offsetWidth - 1280 * s) / 2) + 'px';
        bar.style.bottom = Math.max(0, (box.offsetHeight - 720 * s) / 2) + 'px';
      }
      /* Library animations on a slide (data-trigger="manual") play each time their slide shows; host-motion.js keeps
         them in their end state until then, and in export and print. */
      function playMotion(slide) {
        if (!window.ItemMotion || !slide) return;
        Array.prototype.forEach.call(slide.querySelectorAll('[data-item^="AN-"][data-trigger="manual"]'), function (el) { window.ItemMotion.play(el); });
      }
      Reveal.on('ready', function () { placeBar(); buildBar(); updateBar(); if (window.ItemHost) window.ItemHost.draw(); playMotion(Reveal.getCurrentSlide()); });
      Reveal.on('slidechanged', function (e) { updateBar(); playMotion(e.currentSlide); });
      Reveal.on('resize', placeBar);
    })();`;

function shell(o) {
  return `<!doctype html>
<!-- Built by deck.js from the files in slides/. Edit those, then run deck.js build: changes made here are lost. -->
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${esc(o.title)}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reset.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">
  <link rel="stylesheet" href="styles.css">
${o.css ? `  <style id="item-css">\n${o.css}\n  </style>\n` : ''}  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
</head>
<body>
  <div class="reveal">
    <div class="slides">
<!-- SLIDES:START -->
${o.slides}
<!-- SLIDES:END -->
    </div>
    <div class="section-bar is-hidden" aria-label="Progress"></div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
  <script id="deck-engine">
    ${ENGINE}
  </script>
${o.motion ? `  <script id="host-motion">\n${o.motion}\n  </script>\n` : ''}${o.js.map(j => `  <script class="item-js">\n${j}\n  </script>\n`).join('')}  <script id="host-runtime">
${o.runtime}
  </script>
</body>
</html>
`;
}

/* A slide file: the <section>, then any <style> and <script> of its own. */
function splitSlide(text, file) {
  const a = text.indexOf('<section'), b = text.lastIndexOf('</section>');
  if (a === -1 || b === -1) return { file, section: '', styles: [], scripts: [], bad: 'no <section> ... </section>' };
  const outside = text.slice(0, a) + text.slice(b + 10);
  const styles = [...outside.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1].trim()).filter(Boolean);
  const scripts = [...outside.matchAll(/<script(?![^>]*application\/json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1].trim()).filter(Boolean);
  return { file, section: text.slice(a, b + 10), styles, scripts, offset: (text.slice(0, a).match(/\n/g) || []).length };
}

/* The library's host files, kept current in the deck when the library is found (the deck keeps its copies otherwise):
   host-runtime.js and host-motion.js beside the deck, host.css inside styles.css. */
function refreshHost(dir) {
  const l = findLibrary(dir, null, true);
  if (!l) return;
  ['host-runtime.js', 'host-motion.js'].forEach(f => { const s = path.join(l, f); if (fs.existsSync(s)) { const t = fs.readFileSync(s, 'utf8'), d = path.join(dir, f); if (!fs.existsSync(d) || fs.readFileSync(d, 'utf8') !== t) fs.writeFileSync(d, t); } });
  const css = path.join(dir, 'styles.css'), host = path.join(l, 'host.css');
  if (!fs.existsSync(css) || !fs.existsSync(host)) return;
  const text = fs.readFileSync(css, 'utf8'), mark = '/* ---- host.css, copied from the design library ---- */', end = '/* ---- library items on a slide (deck.js) ---- */';
  const a = text.indexOf(mark), b = text.indexOf(end);
  if (a === -1 || b === -1) return;
  const next = text.slice(0, a + mark.length) + '\n' + fs.readFileSync(host, 'utf8').trim() + '\n\n' + text.slice(b);
  if (next !== text) fs.writeFileSync(css, next);
}
function build(dir, quiet) {
  const files = slideFiles(dir);
  refreshHost(dir);
  const rt = path.join(dir, 'host-runtime.js'), mo = path.join(dir, 'host-motion.js');
  if (!fs.existsSync(rt)) stop(`${rt} is missing and no design library was found to copy it from`);
  const parts = files.map(f => splitSlide(fs.readFileSync(path.join(dir, 'slides', f), 'utf8'), f));
  const uniq = a => [...new Set(a)];
  const moving = parts.some(p => /data-item="AN-/.test(p.section));
  if (moving && !fs.existsSync(mo)) stop(`${mo} is missing and no design library was found to copy it from`);
  const html = shell({
    title: titleOf(dir),
    css: uniq(parts.flatMap(p => p.styles)).join('\n'),
    js: uniq(parts.flatMap(p => p.scripts)),
    motion: moving ? fs.readFileSync(mo, 'utf8').trim() : '',
    runtime: fs.readFileSync(rt, 'utf8').trim(),
    slides: parts.map(p => `<!-- slides/${p.file} -->\n${p.section}`).join('\n\n'),
  });
  fs.writeFileSync(path.join(dir, 'presentation.html'), html);
  const problems = checkStatic(dir, parts);
  if (quiet) return problems;
  console.log(`Built ${path.join(dir, 'presentation.html')}: ${files.length} slide${files.length === 1 ? '' : 's'}.`);
  if (problems.length) console.log(`\n${problems.length} to fix (file:line):\n${problems.map(p => '  ' + p).join('\n')}`);
  else console.log('Static checks: nothing to fix.');
  console.log(`\nNext: ${ME} check "${dir}"   then   node "${path.join(__dirname, 'screenshot.js')}" "${dir}"`);
  return problems;
}

/* ---------------------------------------------------------------- checks without a browser */
function checkChart(o) {
  const out = [];
  const series = [].concat(o.series || []);
  if (!series.length) return ['chart has no series yet'];
  const cat = [].concat(o.xAxis || [], o.yAxis || []).find(a => a && a.type === 'category' && Array.isArray(a.data));
  const isTime = cat && cat.data.length && cat.data.filter(d => PERIOD.test(String(d && d.value !== undefined ? d.value : d))).length >= cat.data.length / 2;
  if (series.length > 4 && !series.every(s => s.stack)) out.push(`${series.length} series; a slide reads 4 at most`);
  series.forEach((s, i) => {
    if (!s.type) out.push(`series ${i + 1} has no "type"`);
    if (!Array.isArray(s.data) || !s.data.length) { if (!(s.itemStyle && s.itemStyle.opacity === 0)) out.push(`series ${i + 1}${s.name ? ' (' + s.name + ')' : ''} has no data`); return; }
    const limit = s.type === 'pie' ? 5 : isTime ? 24 : 12;
    if (s.type !== 'heatmap' && s.data.length > limit) out.push(`series ${i + 1} has ${s.data.length} ${isTime ? 'periods' : 'points'}; a slide reads ${limit} (${isTime ? 'use quarters' : 'group the rest as Other'})`);
  });
  if (o.tooltip && o.tooltip.show !== false && !o.tooltip.formatter) out.push('"tooltip" is set by the deck; remove it from the chart');
  if (o.toolbox || o.dataZoom || o.timeline || o.brush) out.push('toolbox, dataZoom, timeline and brush are for exploring; remove them');
  const nums = series.flatMap(s => (s.data || []).map(d => (d && typeof d === 'object' && !Array.isArray(d) ? d.value : d)).flat()).filter(v => typeof v === 'number');
  const big = nums.some(v => Math.abs(v) >= 10000);
  [].concat(o.xAxis || [], o.yAxis || []).forEach(a => {
    if (a && a.type === 'value' && a.show !== false && big && !(a.axisLabel && a.axisLabel.formatter)) out.push('value axis shows raw numbers: give its axisLabel a formatter ("${value:short}", "{value:comma}", "{value}%")');
  });
  series.forEach((s, i) => { if (s.label && s.label.show && big && !s.label.formatter && !(s.data || []).every(d => d && d.label && d.label.formatter)) out.push(`series ${i + 1} labels show raw numbers: give its label a formatter ("\${c:short}", "{c:comma}")`); });
  /* label formats that do not suit their values: a token the deck cannot read (printed as typed), a % on values in the thousands */
  const formatters = [];
  const look = (x, where) => { if (x && typeof x === 'object') { if (typeof x.formatter === 'string') formatters.push({ f: x.formatter, where }); } };
  series.forEach((s, i) => { look(s.label, i); look(s.endLabel, i); (s.data || []).forEach(d => d && typeof d === 'object' && !Array.isArray(d) && look(d.label, i)); if (s.markLine) look(s.markLine.label, -1); });
  ['xAxis', 'yAxis'].forEach(k => [].concat(o[k] || []).forEach((a, i) => a && look(a.axisLabel, { axis: k, i })));
  const valuesOf = (i, k) => (series[i] ? (series[i].data || []).map(d => { const v = d && typeof d === 'object' && !Array.isArray(d) ? d.value : d; return Array.isArray(v) ? v[k === undefined ? v.length - 1 : k] : v; }) : nums).filter(v => typeof v === 'number');
  const axisValues = w => series.map((s, i) => ((s[`${w.axis}Index`] || 0) === w.i && s.type !== 'scatter' ? valuesOf(i) : [])).flat();
  formatters.forEach(({ f, where }) => {
    for (const m of f.matchAll(/\{(c|value|a|b|@\[\d+\])(?::([^}]*))?\}/g)) if (m[2] !== undefined && !/^(short|comma)$/.test(m[2])) out.push(`label format "${f}" prints "${m[0]}" as typed: use {c:short}, {c:comma}, {c} or {value}`);
    const pct = f.match(/\{(c|value|@\[(\d+)\])(?::\w+)?\}\s*%/);
    if (pct) {
      const vs = where && where.axis ? axisValues(where) : where === -1 ? nums : valuesOf(where, pct[2] !== undefined ? +pct[2] : undefined);
      if (vs.some(v => Math.abs(v) >= 1000)) out.push(`label format "${f}" puts % after values in the thousands: give it a format that suits them ("\${c:short}", "{c:comma}")`);
    }
  });
  const ends = series.filter(s => s.type === 'line' && s.endLabel && s.endLabel.show);
  const right = o.grid && !Array.isArray(o.grid) ? o.grid.right : undefined;
  if (ends.length && !(typeof right === 'number' && right >= 60)) out.push('line end labels need room: set "grid": {"right": 130, ...}');
  return out;
}
function lineAt(text, idx) { return (text.slice(0, idx).match(/\n/g) || []).length + 1; }
/* The visible wording of a library item (slide, chart, table, card, animation): every element's own text. */
const normText = t => unesc(String(t).replace(/&middot;/g, '·').replace(/&nbsp;/g, ' ').replace(/&#\d+;/g, ' ')).replace(/^\s*WORD:\s*/, '').replace(/\s+/g, ' ').trim();
const SAMPLE_CACHE = {};
function sampleTexts(libFolder, id) {
  if (SAMPLE_CACHE[id]) return SAMPLE_CACHE[id];
  const set = new Set();
  try {
    const I = require(path.join(libFolder, 'item.js'));
    walk(parse(I.copyOf(I.get(id)).html), n => {
      if (n.raw !== undefined) return false;
      const t = normText((n.children || []).filter(c => typeof c === 'string').join(' '));
      if (t.length >= 4 && /[a-z]{3}/i.test(t)) set.add(t);
    });
  } catch (e) { /* not in this library */ }
  return (SAMPLE_CACHE[id] = set);
}
function sampleWording(libFolder, text) {
  const ids = [...new Set([...text.matchAll(/data-(?:from|item)="([^"]+)"/g)].flatMap(m => m[1].split(/\s+/)).filter(x => /^[A-Z]{2}-\d{2,}$/.test(x)))];
  const samples = new Set(ids.flatMap(i => [...sampleTexts(libFolder, i)]));
  const out = [], seen = new Set();
  if (!samples.size) return out;
  walk(parse(text), n => {
    if (n.raw !== undefined || attr(n, 'data-rows') !== null || attr(n, 'data-spot') === 'kicker') return false;   // scripts and data rows hold data; the kicker is the section name
    const own = (n.children || []).filter(c => typeof c === 'string').join(' '), t = normText(own);
    if (t && samples.has(t) && !seen.has(t) && !/^\s*WORD:/.test(own.trim())) { seen.add(t); out.push(t); }
  });
  return out;
}
function checkStatic(dir, parts) {
  const out = [], ids = {}, libFolder = findLibrary(dir, null, true);
  parts.forEach(p => {
    const f = `slides/${p.file}`;
    if (p.bad) { out.push(`${f}: ${p.bad}`); return; }
    const text = fs.readFileSync(path.join(dir, 'slides', p.file), 'utf8');
    const id = (p.section.match(/<section\b[^>]*\bid="([^"]*)"/) || [])[1];
    if (!id) out.push(`${f}: the <section> has no id`);
    else if (ids[id]) out.push(`${f}: id "${id}" is also used by slides/${ids[id]}`); else ids[id] = p.file;
    const manual = new Set();
    const routes = s => `name a column (change "MANUAL ${s}" to it) and run ${ME} refill "${dir}" ${id}; or type the figures and change data-manual="${s}" to data-typed="${s}" (add-a-slide.md, "Acting on a MANUAL line")`;
    for (const m of text.matchAll(/data-manual="([^"]*)"/g)) m[1].split(/\s+/).filter(Boolean).forEach(s => { manual.add(s); out.push(`${f}:${lineAt(text, m.index)} MANUAL: ${s} is not filled from data yet - ${routes(s)}`); });
    const typedSlots = new Set([...text.matchAll(/data-typed="([^"]*)"/g)].flatMap(m => m[1].split(/\s+/)));
    text.split('\n').forEach((l, i) => {
      for (const m of l.matchAll(/MANUAL ([a-z][a-z0-9-]*)/g)) if (!manual.has(m[1])) { manual.add(m[1]); out.push(`${f}:${i + 1} MANUAL: ${m[1]} is on placeholder data${typedSlots.has(m[1]) ? ' (marked data-typed, but "MANUAL ' + m[1] + '" is still there)' : ''} - ${routes(m[1])}`); }
      if (/WORD/.test(l)) out.push(`${f}:${i + 1} to reword: ${l.trim().slice(0, 110)}`);
      else if (/\bdata-sample\b/.test(l)) out.push(`${f}:${i + 1} sample values from the library: fill it (add with a chart id and --data) or edit its data, then delete data-sample`);
      else if (SAMPLE.test(l) && !/application\/json|^\s*[{"]/.test(l)) out.push(`${f}:${i + 1} library sample text: ${l.trim().slice(0, 90)}`);
    });
    if (libFolder) sampleWording(libFolder, p.section).forEach(t => {
      const i = text.split('\n').findIndex(l => normText(l.replace(/<[^>]+>/g, ' ')).includes(t.slice(0, 40)));
      out.push(`${f}${i >= 0 ? ':' + (i + 1) : ''} still the library sample's wording: "${t.slice(0, 80)}${t.length > 80 ? '...' : ''}"`);
    });
    for (const m of text.matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) {
      const at = lineAt(text, m.index);
      let o;
      try { o = JSON.parse(m[1]); } catch (e) { out.push(`${f}:${at} chart JSON is not valid: ${e.message}`); continue; }
      if (SAMPLE.test(m[1])) out.push(`${f}:${at} chart still holds library sample labels (Group A, Measure A ...)`);
      checkChart(o).forEach(w => out.push(`${f}:${at} ${w}`));
    }
    let still = p.section;   // an animation's own buttons belong to it; everything else on a slide is fixed
    for (const m of [...p.section.matchAll(/<div\b[^>]*\bdata-item="AN-[^"]*"[^>]*>/g)].reverse()) { const e = elementEnd(p.section, m.index); if (e !== -1) still = still.slice(0, m.index) + still.slice(e); }
    for (const m of still.matchAll(/<(select|input|button|details|iframe|textarea)\b/g)) out.push(`${f}:${lineAt(text, text.indexOf(m[0]))} <${m[1]}> on a slide: a slide shows one fixed cut, no controls`);
    const h = p.section.match(/data-spot="headline"[^>]*>([\s\S]*?)<\/h[12]>/);
    if (h && h[1].replace(/<[^>]+>/g, '').trim().length > 120) out.push(`${f}: headline over 2 lines (120 characters)`);
    for (const m of text.matchAll(/data-source="([^"]+)"/g)) { const s = unesc(m[1]); const where = s.split('::')[0]; if (!fs.existsSync(path.resolve(dir, where))) out.push(`${f}:${lineAt(text, m.index)} data-source "${s}" not found from the deck folder`); }
  });
  return out;
}

/* ---------------------------------------------------------------- data */
const toNum = v => (typeof v === 'string' && /^\s*-?\d+(\.\d+)?([eE][-+]?\d+)?\s*$/.test(v) ? Number(v) : v);
function readTable(file) {
  const t = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  let rows;
  if (/\.json$/i.test(file)) {
    rows = JSON.parse(t);
    if (!Array.isArray(rows)) rows = rows && Array.isArray(rows.rows) ? rows.rows : stop(`${file} is not a list of rows`);
  } else {
    const lines = t.split(/\r?\n/).filter(l => l.trim());
    const cells = l => { const out = []; let cur = '', q = false; for (let i = 0; i < l.length; i++) { const ch = l[i]; if (q) { if (ch === '"' && l[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; } else if (ch === '"') q = true; else if (ch === ',') { out.push(cur); cur = ''; } else cur += ch; } out.push(cur); return out; };
    const head = cells(lines[0] || '').map(h => h.trim());
    rows = lines.slice(1).map(l => { const c = cells(l), r = {}; head.forEach((h, i) => { r[h] = c[i] === undefined ? '' : c[i]; }); return r; });
  }
  return rows.map(r => { const o = {}; Object.keys(r).forEach(k => { o[k] = toNum(r[k]); }); return o; });
}
function runReport(folder, analytic, table) {
  const go = a => {
    const cmd = ['run.py', 'data', a, ...(table ? [table] : []), '--json'];
    let r = spawnSync('python', cmd, { cwd: folder, encoding: 'utf8' });
    if (r.error) r = spawnSync('python3', cmd, { cwd: folder, encoding: 'utf8' });
    const s = r.stdout || '', at = Math.min(...['[', '{'].map(c => { const i = s.indexOf(c); return i === -1 ? 1e9 : i; }));
    try { r.rows = at < 1e9 ? JSON.parse(s.slice(at)) : null; } catch (e) { r.rows = null; }
    return r;
  };
  let r = go(analytic);
  if ((r.status || !Array.isArray(r.rows)) && /^s\d+_/.test(analytic)) r = go(analytic.replace(/^s\d+_/, ''));
  if (r.status || !Array.isArray(r.rows)) {
    const said = ((r.stderr || '') + (r.stdout || '')).trim().split(/\r?\n/).filter(l => /STOP|Error|It has/i.test(l)).slice(-2).join(' / ');
    stop(`python run.py data ${analytic}${table ? ' ' + table : ''} failed in ${folder}: ${said || 'no rows'}\nSee what it offers: ${ME} add <deck> CT-34 --from "${folder}"`);
  }
  return r.rows.map(x => { const o = {}; Object.keys(x).forEach(k => { o[k] = toNum(x[k]); }); return o; });
}
/* A report folder as typed: from here, the deck folder, or the project root (nearest folder above with a CLAUDE.md). */
function reportFolder(given, dir) {
  const g = given.trim().replace(/^["']|["']$/g, '').replace(/[\\/]+$/, '') || '.';
  let root = dir;
  for (let d = dir, i = 0; i < 8; i++, d = path.dirname(d)) if (fs.existsSync(path.join(d, 'CLAUDE.md'))) { root = d; break; }
  const tried = [...new Set([path.resolve(g), path.resolve(dir, g), path.resolve(root, g)])];
  const hit = tried.find(d => fs.existsSync(path.join(d, 'run.py')));
  if (!hit) stop(`no report folder (run.py) for "${given}". Looked in:\n  ${tried.join('\n  ')}`);
  return hit;
}
/* Every section's tables and columns, with the section's title and description when the report's list gives them. */
function catalog(folder) {
  const py = args => { let r = spawnSync('python', ['run.py', ...args], { cwd: folder, encoding: 'utf8' }); if (r.error) r = spawnSync('python3', ['run.py', ...args], { cwd: folder, encoding: 'utf8' }); return ((r.stdout || '') + '\n' + (r.stderr || '')).split(/\r?\n/); };
  const lines = [];
  const read = (src, withTitles) => {
    let about = '';
    src.forEach(l => {
      const s = l.match(/^\s*\d+\.\s+(\S+?)(?:\.py)?\s+\S+\s+(.*?)\s+\|\s+(.*)$/);
      if (s) { about = `${s[1]}: "${s[2].trim()}" | ${s[3].trim()}`; return; }
      const m = l.match(/^\s*(\w+)\(\): (.*)$/);
      if (!m) return;
      [...m[2].matchAll(/table (\S+) \[([^\]]*)\]/g)].forEach(t => lines.push(`  ${m[1]}::${t[1]}   columns: ${t[2]}${withTitles && about ? `\n      ${about}` : ''}`));
      about = '';
    });
  };
  read(py(['list']), true);
  if (!lines.length) read(py(['data']), false);
  return lines.length ? lines.join('\n') : '  (run.py listed nothing; run python run.py list there)';
}
/* The source a slide records: a file path, or "<report folder>::<section>[::<table>]", relative to the deck folder. */
function loadSource(src, dir) {
  if (src.includes('::')) {
    const [f, a, t] = src.split('::').map(s => s.trim());
    const folder = path.resolve(dir, f);
    if (!fs.existsSync(path.join(folder, 'run.py'))) stop(`report folder ${folder} not found (data-source "${src}")`);
    return { rows: runReport(folder, a, t), label: `${path.basename(folder)} report, ${a.replace(/^s\d+_/, '')}${t ? ' ' + t : ''}` };
  }
  const file = path.resolve(dir, src);
  if (!fs.existsSync(file)) stop(`data file ${file} not found (data-source "${src}" is read from the deck folder)`);
  return { rows: readTable(file), label: path.basename(file) };
}
function parseShape(s) {
  if (!s) return null;
  const o = {};
  s.split(';').map(x => x.trim()).filter(Boolean).forEach(x => { const [k, v] = x.split('='); o[k.trim()] = v === undefined ? true : v.trim(); });
  return o.by || o.top || o.order ? o : null;
}
const shapeText = sh => [sh.by ? `agg=${sh.agg}` : '', sh.by ? `by=${sh.by}` : '', sh.month ? 'month' : '', sh.split ? `split=${sh.split}` : '', sh.split ? `value=${sh.value}` : '',
  sh.order ? `order=${sh.order}` : '', sh.top ? `top=${sh.top}` : ''].filter(Boolean).join('; ');
/* Raw rows: summed (or averaged) by one column, days as months when asked; with split, one column per group of
   another column (value is the column summed); then the first `top` rows. */
function applyShape(rows, sh) {
  if (!sh) return rows;
  let out = rows;
  if (sh.by) {
    [sh.by, sh.split, sh.value].filter(Boolean).forEach(c => { if (rows.length && !(c in rows[0])) stop(`the data has no column "${c}" (data-shape); columns: ${Object.keys(rows[0]).join(', ')}`); });
    const key = r => { let v = r[sh.by]; if (sh.month && typeof v === 'string' && ISO_DAY.test(v)) v = v.slice(0, 7); return v; };
    const empty = v => v === undefined || v === null || v === '';
    const groups = new Map();
    rows.forEach(r => { const k = key(r); if (empty(k)) return; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); });
    const agg = vs => { const s = vs.reduce((a, b) => a + b, 0); return sh.agg === 'mean' ? s / (vs.length || 1) : s; };
    if (sh.split) {
      const tot = new Map();
      rows.forEach(r => { const g = r[sh.split]; if (!empty(g) && typeof r[sh.value] === 'number') tot.set(String(g), (tot.get(String(g)) || 0) + r[sh.value]); });
      const parts = [...tot].sort((a, b) => b[1] - a[1]).map(x => x[0]);
      out = [...groups].map(([k, rs]) => { const o = { [sh.by]: k }; parts.forEach(p => { o[p] = agg(rs.filter(r => String(r[sh.split]) === p).map(r => r[sh.value]).filter(v => typeof v === 'number')); }); return o; });
      out.parts = parts;
    } else {
      const nums = Object.keys(rows[0] || {}).filter(c => c !== sh.by && rows.some(r => typeof r[c] === 'number'));
      out = [...groups].map(([k, rs]) => { const o = { [sh.by]: k, count: rs.length }; nums.forEach(c => { o[c] = agg(rs.map(r => r[c]).filter(v => typeof v === 'number')); }); return o; });
    }
    const parts = out.parts;
    if (sh.order === 'label') out.sort((a, b) => String(a[sh.by]).localeCompare(String(b[sh.by])));
    else if (sh.order) out.sort((a, b) => (Number(b[sh.order]) || 0) - (Number(a[sh.order]) || 0));
    out.parts = parts;
  }
  if (!sh.by && sh.order && sh.order !== 'label') out = out.slice().sort((a, b) => (toNumber(b[sh.order]) || 0) - (toNumber(a[sh.order]) || 0));   // largest first, no grouping
  if (sh.top && out.length > Number(sh.top)) { const parts = out.parts; out = out.slice(0, Number(sh.top)); out.parts = parts; }
  return out;
}
/* Numbers: % turns fractions into percents; whole formats round to whole numbers, $short and short too once
   values reach 100 (so $499 sits beside $1.2K, never $499.22); the rest keep two decimals. */
const WHOLE = f => f === '$0' || f === '0';
function tidy(rows, cols, fmt) {
  cols.forEach(c => {
    const vs = rows.map(r => r[c]).filter(v => typeof v === 'number');
    const pct = fmt === '%' && vs.length && vs.every(v => Math.abs(v) <= 1.5);
    const whole = WHOLE(fmt) || (/short/.test(fmt || '') && vs.some(v => Math.abs(v) >= 100));
    const k = pct ? 10 : whole ? 1 : 100;
    rows.forEach(r => { if (typeof r[c] === 'number') r[c] = Math.round((pct ? r[c] * 100 : r[c]) * k) / k; });
  });
  return rows;
}
function short(v) {
  const a = Math.abs(v), u = a >= 1e9 ? ['B', 1e9] : a >= 1e6 ? ['M', 1e6] : a >= 1e3 ? ['K', 1e3] : ['', 1], n = v / u[1];
  return n.toLocaleString('en-US', { maximumFractionDigits: u[1] === 1 ? (a >= 100 ? 0 : 2) : Math.abs(n) < 10 ? 1 : 0 }) + u[0];
}
function fmtNum(v, f) {
  if (typeof v !== 'number') return v;
  const s = v < 0 ? '-' : '', a = Math.abs(v), comma = (x, d = 2) => x.toLocaleString('en-US', { maximumFractionDigits: d });
  if (f === '$short') return s + '$' + short(a);
  if (f === 'short') return s + short(a);
  if (f === '$0') return s + '$' + comma(Math.round(a), 0);
  if (f === '0') return s + comma(Math.round(a), 0);
  if (f === '$,') return s + '$' + comma(a);
  if (f === '%') return s + comma(Math.round(a * 10) / 10) + '%';
  return s + comma(a);
}
const FORMATS = {
  '$short': { c: '${c:short}', value: '${value:short}' }, short: { c: '{c:short}', value: '{value:short}' },
  '$0': { c: '${c:comma}', value: '${value:comma}' }, '0': { c: '{c:comma}', value: '{value:comma}' },
  '$,': { c: '${c:comma}', value: '${value:comma}' }, ',': { c: '{c:comma}', value: '{value:comma}' }, '%': { c: '{c}%', value: '{value}%' },
};
const FORMAT_NAMES = '$short, short, $0 (whole dollars), 0 (whole numbers), $, , , %, none';
function guessFormat(col, rows) {
  const vs = rows.map(r => r[col]).filter(v => typeof v === 'number');
  if (/paid|cost|amount|revenue|spend|premium|price|dollar|billed|allowed|charge/i.test(col)) return vs.some(v => Math.abs(v) >= 10000) ? '$short' : '$0';
  if (/rate|share|pct|percent|ratio/i.test(col)) return '%';
  return vs.some(v => Math.abs(v) >= 10000) ? 'short' : vs.some(v => Math.abs(v) >= 100) ? '0' : ',';
}

/* ---------------------------------------------------------------- charts: fill marks with "col", refill keeps edits */
function colsOfChart(o) { const out = []; const go = x => { if (Array.isArray(x)) return x.forEach(go); if (!x || typeof x !== 'object') return; if (typeof x.col === 'string') out.push(...x.col.split(',')); Object.values(x).forEach(go); }; go(o); return out; }
/* After the library's fill: write on each data object which column it holds, and give series readable names. */
function annotate(I, o, map, rows) {
  const count = {}, has = c => rows.length && c in rows[0];
  I.marks(o).forEach(m => {
    const spec = m.obj.slot, names = I.slotNames(spec);
    if (spec.includes(':')) { const c = (map[names[0]] || [])[0]; if (c !== undefined && has(c)) m.obj.col = c; return; }
    if (names.length > 1) { m.obj.col = names.map(n => (map[n] || [])[0]).join(','); return; }
    const cols = map[names[0]] || [];
    if (/^(category|value|time|log)$/.test(m.obj.type || '')) { if (cols[0] !== undefined) m.obj.col = cols[0]; return; }
    const k = count[names[0]] = (count[names[0]] || 0) + 1;
    if (cols[k - 1] !== undefined) { m.obj.col = cols[k - 1]; if (m.obj.type && m.obj.type !== 'value') m.obj.name = pretty(cols[k - 1]); }
  });
}
/* Axis names and titles hold the library sample's subject: scatter axes take their columns' names, the rest are marked to reword. */
function nameAxes(I, o, map) {
  const axes = k => [].concat(o[k] || []).filter(a => a && typeof a === 'object');
  const xy = ['xAxis', 'yAxis'].every(k => axes(k).length && axes(k).every(a => a.type === 'value'));   // a scatter of two measures: its axes take the columns' names
  const tuple = xy ? I.marks(o).map(m => I.slotNames(m.obj.slot)).find(n => n.length > 1) : null;
  ['xAxis', 'yAxis'].forEach((k, i) => axes(k).forEach(a => {
    if (typeof a.name !== 'string' || !a.name.trim() || a.show === false) return;
    const col = tuple && tuple[i] && (map[tuple[i]] || [])[0];
    a.name = col && !/^MANUAL /.test(col) ? pretty(col) : `WORD: ${a.name}`;
  }));
  [].concat(o.title || []).forEach(t => { if (t && typeof t.text === 'string' && t.text.trim()) t.text = `WORD: ${t.text}`; });
}
/* Number formats on labels and value axes. pct: columns that are percents whatever the item's format (a worked-out share);
   an axis used only by those series reads in %. */
function formatChart(o, f, pct) {
  pct = pct || new Set();
  const series = [].concat(o.series || []);
  const fmtOf = s => FORMATS[typeof s.col === 'string' && pct.has(s.col) ? '%' : f];
  series.forEach(s => {
    const F = fmtOf(s);
    if (!F || typeof s.col !== 'string' || s.col.includes(',')) return;
    if (s.label && s.label.show) s.label.formatter = F.c;
    if (s.endLabel && s.endLabel.show && typeof s.endLabel.formatter === 'string' && s.endLabel.formatter.includes('{c}')) s.endLabel.formatter = s.endLabel.formatter.replace(/\$?\{c\}%?/g, F.c);
  });
  ['xAxis', 'yAxis'].forEach(k => [].concat(o[k] || []).forEach((a, i) => {
    if (!a || a.type !== 'value' || a.show === false) return;
    const users = series.filter(s => (s[`${k}Index`] || 0) === i && typeof s.col === 'string');
    const F = users.length && users.every(s => pct.has(s.col)) ? FORMATS['%'] : FORMATS[f];
    if (F) a.axisLabel = Object.assign({}, a.axisLabel, { formatter: F.value });
  }));
}
function keepStyle(old, v) {
  if (!old || typeof old !== 'object' || Array.isArray(old) || !('value' in old)) return v;
  const o = JSON.parse(JSON.stringify(old)); o.value = v;
  if (o.label && typeof o.label.formatter === 'string' && !/\{/.test(o.label.formatter)) { delete o.label.formatter; if (!Object.keys(o.label).length) delete o.label; }
  return o;
}
/* Only the data of objects marked "col" changes: names, styles, axis ranges and formats stay as edited.
   An object with "col" and "figure" (first, sum, mean, max, min) takes that one number: a markLine entry's
   yAxis or xAxis, or the property named by "set". A series with "highlight" (a category name or a list)
   gets var(--blue) on those categories, whatever their position. */
const FIGURES = { first: v => v[0], sum: v => v.reduce((a, b) => a + b, 0), mean: v => v.reduce((a, b) => a + b, 0) / (v.length || 1), max: v => Math.max(...v), min: v => Math.min(...v) };
function highlightSeries(o) {
  const cat = [].concat(o.xAxis || [], o.yAxis || []).find(a => a && a.type === 'category' && Array.isArray(a.data));
  if (!cat) return;
  [].concat(o.series || []).forEach(s => {
    if (!s || s.highlight === undefined || !Array.isArray(s.data)) return;
    const want = [].concat(s.highlight).map(String);
    s.data = s.data.map((d, k) => {
      const v = d && typeof d === 'object' && !Array.isArray(d) ? d.value : d;
      return want.includes(String(cat.data[k])) ? { value: v, itemStyle: { color: s.highlightColor || 'var(--blue)' } } : v;
    });
  });
}
function refillChart(o, rows, fmt) {
  const has = c => rows.length && c in rows[0];
  const col = c => { const v = rows.map(r => (r[c] === '' || r[c] === undefined ? null : r[c])); while (v.length && v[v.length - 1] === null) v.pop(); return v; };
  const missing = new Set();
  const go = x => {
    if (Array.isArray(x)) return x.forEach(go);
    if (!x || typeof x !== 'object') return;
    if (typeof x.col === 'string' && typeof x.figure === 'string') {
      if (!has(x.col)) missing.add(x.col);
      else {
        const vs = col(x.col).filter(v => typeof v === 'number'), f = FIGURES[x.figure] || FIGURES.first;
        const prop = x.set || ('yAxis' in x ? 'yAxis' : 'xAxis' in x ? 'xAxis' : 'value');
        const k = WHOLE(fmt) || (/short/.test(fmt || '') && vs.some(v => Math.abs(v) >= 100)) ? 1 : 100;   // rounded as the item's format reads
        if (vs.length) x[prop] = Math.round(f(vs) * k) / k;
      }
      return;
    }
    if (typeof x.col === 'string') {
      const cs = x.col.split(',').map(s => s.trim());
      cs.forEach(c => { if (!has(c)) missing.add(c); });
      if (cs.every(has)) {
        if (typeof x.slot === 'string' && x.slot.includes(':')) x[x.slot.split(':')[1]] = col(cs[0]).find(v => v !== null);
        else if (cs.length > 1) { const old = x.data || []; x.data = rows.map(r => cs.map(c => r[c])).filter(t => t.every(v => v !== '' && v !== undefined && v !== null)).map((t, i) => keepStyle(old[i], t)); }
        else if (x.type === 'category') x.data = [...new Set(col(cs[0]).filter(v => v !== null).map(String))];
        else if (/^(value|time|log)$/.test(x.type || '')) x.data = col(cs[0]);
        else { const old = x.data || []; x.data = col(cs[0]).map((v, k) => keepStyle(old[k], v)); }
      }
    }
    Object.keys(x).forEach(k => { if (k !== 'data' || x.type === undefined) go(x[k]); });   // a series' data is not walked; a markLine's is
  };
  go(o);
  highlightSeries(o);
  return [...missing];
}
/* One key per line, one series per line: short enough to read and edit. */
function prettyJson(o, ind) {
  if (!o || typeof o !== 'object' || Array.isArray(o)) return JSON.stringify(o);
  const lines = Object.keys(o).map(k => {
    const v = o[k];
    if (Array.isArray(v) && (v.length > 1 || (k === 'series' && v.length)) && v.every(x => x && typeof x === 'object' && !Array.isArray(x))) return `${ind}  "${k}": [\n${v.map(x => `${ind}    ${JSON.stringify(x)}`).join(',\n')}\n${ind}  ]`;
    return `${ind}  "${k}": ${JSON.stringify(v)}`;
  });
  return `{\n${lines.join(',\n')}\n${ind}}`;
}
function prettyScripts(text) {
  return text.replace(/^([ \t]*)(.*?)<script type="application\/json">([\s\S]*?)<\/script>/gm, (all, ind, before, json) => {
    let o; try { o = JSON.parse(json); } catch (e) { return all; }
    const base = ind + (before.trim() ? '  ' : '');
    return `${ind}${before}<script type="application/json">\n${base}${prettyJson(o, base)}\n${base}</script>`;
  });
}

/* --by on a slide already added: one series per group, copied from the chart's first value series. */
function splitSeries(o, parts, valueCol) {
  const list = [].concat(o.series || []);
  const isValue = s => s && typeof s.col === 'string' && !s.col.includes(',') && typeof s.figure !== 'string' && (s.col === valueCol || parts.includes(s.col));
  const tpl = list.find(isValue);
  if (!tpl) stop(`the chart has no series showing ${valueCol}; nothing to split`);
  const clean = s => { ['itemStyle', 'lineStyle', 'areaStyle', 'endLabel', 'label'].forEach(k => { if (s[k] && typeof s[k] === 'object') { delete s[k].color; delete s[k].borderColor; } }); return s; };
  const made = parts.map(p => { const s = clean(JSON.parse(JSON.stringify(tpl))); s.name = pretty(p); s.col = p; s.data = []; delete s.highlight; return s; });
  const at = list.indexOf(tpl);
  o.series = list.filter((s, i) => i < at && !isValue(s)).concat(made, list.filter((s, i) => i > at && !isValue(s)));
}

/* ---------------------------------------------------------------- figures typed in the words */
/* "$4.6M", "1,209", "38%": each with the range of values it can stand for. Bare small whole numbers and years are left out. */
function typedFigures(text) {
  const out = [];
  for (const m of text.matchAll(/(\$)?(-?\d[\d,]*(?:\.\d+)?)\s?(K|M|B|bn|k|m)?\b(%)?/g)) {
    const raw = m[2].replace(/,/g, ''), dec = (raw.split('.')[1] || '').length;
    const mult = { K: 1e3, k: 1e3, M: 1e6, m: 1e6, B: 1e9, bn: 1e9 }[m[3]] || 1;
    if (!m[1] && !m[3] && !m[4] && !dec && (Math.abs(Number(raw)) < 100 || /^(19|20)\d\d$/.test(raw))) continue;
    out.push({ text: m[0].trim(), v: Number(raw) * mult, tol: 0.5 * Math.pow(10, -dec) * mult + 1e-9 });
  }
  return out;
}
/* Every number the slide's charts and tables show, plus each series' total. */
function dataValues(text) {
  const vals = [];
  for (const m of text.matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) {
    let o; try { o = JSON.parse(m[1]); } catch (e) { continue; }
    [].concat(o.series || []).forEach(s => {
      const nums = (s.data || []).map(d => (d && typeof d === 'object' && !Array.isArray(d) ? d.value : d)).flat().filter(v => typeof v === 'number');
      vals.push(...nums); if (nums.length > 1) vals.push(nums.reduce((a, b) => a + b, 0));
    });
  }
  for (const m of text.matchAll(/<t[dh]\b[^>]*data-slot="[^"]*"[^>]*>([^<]*)</g)) typedFigures(m[1]).forEach(f => vals.push(f.v));
  return vals;
}
/* Lines of a slide outside its copied items: the words. */
function wordLines(text) {
  const skip = [];
  for (const m of text.matchAll(/<div\b[^>]*\bdata-(?:item|echart)\b[^>]*>/g)) { const e = elementEnd(text, m.index); if (e !== -1) skip.push([m.index, e]); }
  const out = []; let at = 0;
  text.split('\n').forEach((l, i) => { const s = at; at += l.length + 1; if (!skip.some(([a, b]) => s >= a && s < b) && !/<(style|script)/.test(l)) out.push({ n: i + 1, text: l.replace(/<[^>]+>/g, ' ') }); });
  return out;
}
function staleFigures(before, after) {
  const oldV = dataValues(before), newV = dataValues(after), near = (f, vs) => vs.some(v => Math.abs(v - f.v) <= f.tol);
  const out = [];
  wordLines(after).forEach(l => typedFigures(l.text).forEach(f => { if (near(f, oldV) && !near(f, newV)) out.push(`line ${l.n}: "${f.text}" matched the old data and no longer does`); }));
  return out;
}

/* ---------------------------------------------------------------- tables and hero cards */
function htmlSlotsWithProp(html) { const s = new Set(); for (const m of html.matchAll(/data-slot="([^"]*)"/g)) m[1].split(/\s+/).forEach(t => { if (t.includes('@')) s.add(t.split('@')[0]); }); return s; }
function formattedRows(rows, map, html, fmt) {
  const raw = htmlSlotsWithProp(html), keep = new Set(Object.keys(map).filter(k => raw.has(k)).flatMap(k => map[k]));
  return rows.map(r => { const o = {}; Object.keys(r).forEach(k => { o[k] = keep.has(k) ? r[k] : fmtNum(r[k], fmt); }); return o; });
}
function stripControls(html) { return html.replace(/\s*<button[^>]*\bdata-csv\b[^>]*>[\s\S]*?<\/button>/g, ''); }
const hasHtmlSlots = html => /data-(slot|rows)/.test(html.replace(/<script[\s\S]*?<\/script>/g, ''));
/* Any copied block: chart options get the columns (marked "col", formats set), then HTML slots get formatted text. */
function fillBlock(I, html, rows, map, fmt, pct) {
  let out = html.replace(/(<script type="application\/json"[^>]*>)([\s\S]*?)(<\/script>)/g, (m, x, j, y) => {
    const o = I.fillChart(JSON.parse(j), rows, map); annotate(I, o, map, rows); nameAxes(I, o, map); formatChart(o, fmt, pct); return x + JSON.stringify(o) + y;
  });
  if (hasHtmlSlots(out)) {
    out = I.fillHtml(out, formattedRows(rows, map, out, fmt), map);
    Object.values(map).flat().forEach(c => { out = out.replace(new RegExp(`(<th\\b[^>]*data-slot="[^"]*"[^>]*>)${c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(</th>)`, 'g'), `$1${esc(pretty(c))}$2`); });
  }
  return stripControls(out);
}
function refillHtmlItem(I, inner, rows, map, fmt) {
  const oldHead = (inner.match(/<thead>[\s\S]*?<\/thead>/) || [])[0];
  const leads = [...inner.matchAll(/<tr\b[^>]*class="[^"]*\bon\b[^"]*"[^>]*>\s*<t[dh]\b[^>]*>([^<]*)</g)].map(m => m[1].trim());
  let out = I.fillHtml(inner, formattedRows(rows, map, inner, fmt), map);   // HTML slots only: the chart options were refilled already, keeping edits
  const newHead = (out.match(/<thead>[\s\S]*?<\/thead>/) || [])[0];
  if (oldHead && newHead && (oldHead.match(/<th\b/g) || []).length === (newHead.match(/<th\b/g) || []).length) out = out.replace(newHead, () => oldHead);
  if (leads.length) out = out.replace(/<tr\b([^>]*)>(\s*<t[dh]\b[^>]*>)([^<]*)</g, (m, a, td, txt) => {
    if (!leads.includes(txt.trim())) return m;
    const withOn = /class="/.test(a) ? a.replace(/class="([^"]*)"/, (x, c) => `class="${c ? c + ' ' : ''}on"`) : `${a} class="on"`;
    return `<tr${withOn}>${td}${txt}<`;
  });
  return stripControls(out);
}

/* data-cols: "label=region; value=paid,allowed"; a comma or semicolon inside one value (a figure typed as is) is %2C / %3B */
/* A figure typed as is (not a column) is quoted: value="+7.0%". */
const colsText = (map, cols) => Object.entries(map).map(([k, v]) => `${k}=${v.map(x => { const t = String(x).replace(/%/g, '%25').replace(/,/g, '%2C').replace(/;/g, '%3B'); return cols && !cols.includes(x) && x !== 'count' ? `"${t}"` : t; }).join(',')}`).join('; ');
function parseCols(s) {
  const map = {}, typed = new Set();
  s.split(';').map(x => x.trim()).filter(Boolean).forEach(x => {
    const at = x.indexOf('=');
    map[x.slice(0, at).trim()] = x.slice(at + 1).split(',').map(v => { v = v.trim(); const q = /^".*"$/.test(v); v = decodeURIComponent(q ? v.slice(1, -1) : v); if (q) typed.add(v); return v; });
  });
  Object.defineProperty(map, 'typed', { value: typed, enumerable: false });
  return map;
}

/* ---------------------------------------------------------------- add */
/* Which columns fill which slot. Never stops: a slot the item does not have, a column the data lacks or extra columns
   become notes; a required slot left without a column is returned in `missing` (it goes on placeholder data). */
function slotMap(slots, note, rows, itemId, notes) {
  const map = {}, cols = Object.keys(rows[0] || {});
  const isText = c => rows.slice(0, 200).some(r => typeof r[c] === 'string' && r[c] !== '');
  const inputs = calcInputs(itemId).filter(n => !note.some(s => s.name === n)).map(n => ({ name: n, kind: 'number', count: 'optional' }));   // columns a worked-out slot is made from (high)
  slots.forEach(s => {
    const at = String(s).indexOf('='), k = String(s).slice(0, at).trim(), v = String(s).slice(at + 1);
    if (at < 1) { notes.push(`Ignored --slot ${s}: write it as --slot <name>=<column>.`); return; }
    const slot = note.find(x => x.name === k) || inputs.find(x => x.name === k);
    if (!slot) { notes.push(`Ignored --slot ${k}: ${itemId} has no slot "${k}" (its slots: ${note.map(x => x.name).join(', ') || 'none'}).`); return; }
    let cs = slot.kind === 'figure' ? [v.trim()] : v.split(',').map(x => x.trim()).filter(Boolean);   // a figure is one value, commas and all
    if (slot.kind !== 'figure') {
      const absent = cs.filter(c => !cols.includes(c) && c !== 'count');
      if (absent.length) { cs = cs.filter(c => !absent.includes(c)); notes.push(`--slot ${k}: the data has no column ${absent.join(', ')}${cs.length ? '' : /optional|any/.test(slot.count) ? ', so it is left out' : ''} (columns: ${cols.join(', ')}).`); }
    }
    if (/^(one|optional)$/.test(slot.count) && cs.length > 1) { notes.push(`${k} takes one column: used ${cs[0]}, ignored ${cs.slice(1).join(', ')}.`); cs = cs.slice(0, 1); }
    if (cs.length) map[k] = cs;
  });
  if (!slots.length && cols.length <= 4) {   // a small shaped table: text slots take text columns, number slots the numbers, in order
    const texts = cols.filter(isText), nums = cols.filter(c => !texts.includes(c));
    note.forEach(s => {
      const pool = s.kind === 'text' ? texts : nums;
      if (s.kind === 'figure' || !pool.length) return;
      if (s.count === 'one') map[s.name] = [pool.shift()];
      else if (s.count === 'one or more') map[s.name] = pool.splice(0);
    });
  }
  const missing = note.filter(s => /^(one|one or more)$/.test(s.count) && !(map[s.name] || []).length);
  return { map, missing, texts: cols.filter(isText), nums: cols.filter(c => !isText(c)) };
}
/* ---- slots worked out from others (an item's recipe line) ----
   A slot is derived when its recipe part is a calculation ("low: the smaller of start and end"). Where the calculation
   is mechanical from columns given, add works it out (COMPUTE) and refill repeats it (data-calc on the item). */
const CALC_WORDS = /\bfit\b|minus|difference|smaller|larger|sum\b|cumulative|running|share|as a %|% of|÷|×|=|scale|combined|change on|width|position|the same as/i;
function derivedSlots(item) {
  const out = {};
  String(item.recipe || '').split(';').forEach(part => {
    const m = part.match(/^\s*([a-z][a-z0-9-]*(?:\s*,\s*[a-z][a-z0-9-]*)*)\s*[:=]\s*(.+)$/);
    if (!m) return;
    const how = m[2].trim();
    m[1].split(',').map(x => x.trim()).forEach(n => { if ((item.data || []).some(s => s.name === n) && !/^empty/i.test(how) && CALC_WORDS.test(how)) out[n] = how; });
  });
  return out;
}
/* What add can work out itself: item -> slot -> [function, input slots]. Inputs that are not slots (high) are given with --slot too. */
const COMPUTE = {
  'CT-08': { low: ['min', 'start', 'end'], gap: ['absdiff', 'start', 'end'] },
  'CT-11': { range: ['minus', 'high', 'low'] },
  'CT-22': { running: ['cumsum', 'variance'] },
  'CT-24': { share: ['runshare', 'value'] },
  'CT-19': { part: ['rowpct', 'part'] },
  'TB-08': { incurred: ['plus', 'paid', 'ibnr'], pmpm: ['divide', 'incurred', 'members'] },
  'AN-01': { 'value-number': ['number', 'value'] },
  'AN-10': { 'value-number': ['number', 'value'] },
};
const SORT_FIRST = { 'CT-02': 'value', 'CT-24': 'value' };   // items whose rows go largest first
const calcInputs = id => [...new Set(Object.values(COMPUTE[id] || {}).flatMap(c => c.slice(1)))];
const toNumber = v => (typeof v === 'number' ? v : Number(String(v).replace(/[^0-9.\-]/g, '')));
/* Works out one derived column (or several, for rowpct) into rows; returns the new column names, or null when an input is missing. */
function computeSlot(rows, fn, inputs, slot) {
  if (inputs.some(c => !c || !c.length)) return null;
  const col = c => rows.map(r => toNumber(r[c]));
  const name = (s) => `${s} (worked out)`;
  if (fn === 'rowpct') {
    const cs = inputs[0], made = cs.map(c => name(c));
    rows.forEach(r => { const tot = cs.reduce((a, c) => a + (toNumber(r[c]) || 0), 0); cs.forEach((c, i) => { r[made[i]] = tot ? Math.round(toNumber(r[c]) / tot * 1000) / 10 : null; }); });
    return made;
  }
  const [a, b] = inputs.map(x => x[0]), out = name(slot);
  const A = col(a), B = b ? col(b) : null;
  let run = 0;
  const tot = A.reduce((s, v) => s + (v || 0), 0);
  rows.forEach((r, i) => {
    const x = A[i], y = B ? B[i] : null;
    r[out] = fn === 'min' ? Math.min(x, y) : fn === 'absdiff' ? Math.abs(y - x) : fn === 'minus' ? x - y : fn === 'plus' ? x + y
      : fn === 'divide' ? (y ? x / y : null) : fn === 'cumsum' ? (run += x || 0) : fn === 'runshare' ? Math.round((run += x || 0) / (tot || 1) * 1000) / 10 : fn === 'number' ? x : null;
  });
  return [out];
}
/* Fills what can be worked out; returns the data-calc text that lets refill repeat it. */
function applyCalc(itemId, rows, map, notes) {
  const plan = COMPUTE[itemId], done = [];
  if (!plan) return '';
  Object.entries(plan).forEach(([slot, [fn, ...ins]]) => {
    if (fn === 'number') {   // a figure typed as is (or a column's first value): its plain number for a count-up
      const v = (map[ins[0]] || [])[0];
      if (v === undefined || (map[slot] || []).length) return;
      const first = rows.length && v in rows[0] ? rows[0][v] : v;
      if (!isNaN(toNumber(first))) { map[slot] = [String(toNumber(first))]; notes.push(`Worked out ${slot}: ${toNumber(first)}, the plain number in ${ins[0]}.`); }
      return;
    }
    const inputs = ins.map(s => (s === slot ? map[s] : map[s] || []));
    if (fn !== 'rowpct' && (map[slot] || []).length && !/ \(worked out\)$/.test(map[slot][0])) notes.push(`${slot} is worked out from ${ins.join(' and ')}, so the column you gave it (${map[slot].join(', ')}) was not used.`);
    const made = computeSlot(rows, fn, fn === 'rowpct' ? [map[slot] || []] : inputs, slot);
    if (!made) return;
    map[slot] = made;
    done.push(`${slot}=${fn}(${(fn === 'rowpct' ? map[slot].map(c => c.replace(/ \(worked out\)$/, '')) : ins.map(s => (map[s] || [])[0])).join(',')})`);
    const cols = ins.map(s => (map[s] || [])[0]);
    const words = { min: `the smaller of ${cols.join(' and ')}`, absdiff: `the difference between ${cols.join(' and ')}`, minus: `${cols[0]} minus ${cols[1]}`, plus: `${cols[0]} plus ${cols[1]}`,
      divide: `${cols[0]} divided by ${cols[1]}`, cumsum: `the running total of ${cols[0]}`, runshare: `the running total of ${cols[0]} as a % of its total`, rowpct: 'each column as a % of the row total' }[fn];
    notes.push(`Worked out ${slot}: ${words}.`);
  });
  return done.join('; ');
}
/* refill: repeat the calculations recorded in data-calc ("low=min(start,end); share=runshare(value)"). */
function reapplyCalc(rows, calc) {
  String(calc || '').split(';').map(s => s.trim()).filter(Boolean).forEach(s => {
    const m = s.match(/^([a-z0-9-]+)=(\w+)\(([^)]*)\)$/);
    if (!m) return;
    const cols = m[3].split(',').map(x => x.trim());
    computeSlot(rows, m[2], m[2] === 'rowpct' ? [cols] : cols.map(c => [c]), m[1]);
  });
  return rows;
}

/* Required slots with no column: a clearly marked placeholder column ("MANUAL <slot>") in the rows. */
function placeholders(rows, missing, map) {
  /* placeholder numbers sit on the scale of a number column already filled, so the chart stays readable */
  const real = Object.values(map).flat().find(c => !/^MANUAL /.test(c) && rows.some(r => typeof r[c] === 'number'));
  const top = real ? Math.max(...rows.map(r => Math.abs(toNumber(r[real]) || 0))) : 50;
  missing.forEach(s => {
    const c = `MANUAL ${s.name}`;
    rows.forEach((r, i) => { r[c] = s.kind === 'number' ? Math.round(top * (0.5 + 0.1 * (i % 5)) * 100) / 100 : s.kind === 'text' ? `MANUAL ${i + 1}` : 'MANUAL'; });
    map[s.name] = [c];
  });
}
/* A MANUAL line with both routes and the exact commands ({file}, {refill} and {build} are filled in once the slide exists). */
const manualLine = (s, cols, how) => `MANUAL: ${s.name} is not filled - it shows placeholder data, marked "MANUAL ${s.name}", in {file}.
  Either name a column: in that file change "MANUAL ${s.name}" to one of your ${s.kind === 'number' ? 'number ' : s.kind === 'text' ? 'text ' : ''}columns (${cols.join(', ') || 'none fits yet'})${how ? `; ${s.name} must be worked out first (${how}): add that column to your data` : ''}, then run
    {refill}
  Or type the figures by hand: replace the placeholder figures with yours, delete "MANUAL ${s.name}" from that item (the "col" in a chart, the data-cols entry in a table), and change data-manual="${s.name}" to data-typed="${s.name}" on it; then run
    {build}
  build and check list this slot until one of the two is done.`;
const fillTokens = (s, dir, file, id) => s.split('{file}').join(`slides/${file}`).split('{refill}').join(`${ME} refill "${dir}" ${id}`).split('{build}').join(`${ME} build "${dir}"`);
function getItem(I, id) { try { return I.get(id); } catch (e) { stop(`no library item ${id}. The library's index pages list the ids (index/slides.md, index/charts.md, index/tables.md, index/hero-cards.md, index/animations.md).`); } }
function facts(rows, label, value, fmt) {
  if (!label || !value || !rows.length || !rows.every(r => typeof r[value] === 'number')) return '';
  const order = rows.map((r, i) => i).sort((a, b) => rows[b][value] - rows[a][value]);
  const at = i => `${fmtNum(rows[i][value], fmt)} (${rows[i][label]})`;
  return `Facts for the words (${pretty(value)}): largest ${at(order[0])}` + (order.length > 1 ? `; second ${at(order[1])}; smallest ${at(order[order.length - 1])}` : '') +
    `; latest ${at(rows.length - 1)}; total ${fmtNum(rows.reduce((a, r) => a + r[value], 0), fmt)}; ${rows.length} rows.`;
}
/* Facts for every number column shown (a series, a table column), at most 8. */
function factsAll(rows, label, cols, fmt) {
  const out = [...new Set(cols)].slice(0, 8).map(c => facts(rows, label, c, fmt)).filter(Boolean);
  if (cols.length > 8) out.push(`(${cols.length - 8} more columns not listed)`);
  return out;
}
function plainSlide({ id, section, headline, spot, from, footnote }) {
  return `<section id="${id}"${section ? ` data-section="${escA(section)}"` : ''}${from ? ` data-from="${from}"` : ''}>
  <p class="kicker" data-spot="kicker">${section ? esc(section) : 'WORD: section name'}</p>
  <h2 data-spot="headline">${headline ? esc(headline) : 'WORD: the point as a sentence, with its number'}</h2>
  <div class="content">
    <div data-place="left" style="flex: 1; display: grid; grid-template-columns: 3fr 2fr; gap: var(--split-gap); min-height: 0; min-width: 0;">
${spot}
      <div class="commentary">
        <h3 data-spot="text">WORD: what is measured, the period</h3>
        <ul data-spot="bullets">
          <li>WORD: what to look at, with its number</li>
          <li>WORD: what it means for this audience</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="footnote" data-spot="footnote">${footnote}</div>
</section>
`;
}
const BLANK_CHART = `      <div class="chart" data-echart data-spot="chart">
        <script type="application/json">{"xAxis": {"type": "category", "data": []}, "yAxis": {"type": "value"}, "series": []}</script>
      </div>`;

function place(dir, files, after, id, text) {
  const ids = files.map(f => readSlide(dir, f).id);
  let base = id, n = 2;
  while (ids.includes(id) || files.some(f => f.replace(/^\d+[a-z]?-/, '') === `${id}.html`)) id = `${base}-${n++}`;
  const name = `00-${id}.html`;
  const finalText = text.replace(/<section id="[^"]*"/, `<section id="${id}"`);
  fs.writeFileSync(path.join(dir, 'slides', name), prettyScripts(finalText));
  const order = files.slice(); order.splice(after + 1, 0, name);
  const done = renumber(dir, order);
  return { file: done[after + 1], id };
}
function sectionNear(dir, files, after, given) {
  if (given !== undefined) return given;
  for (let i = after; i >= 0; i--) { const s = (readSlide(dir, files[i]).attrs.match(/data-section="([^"]*)"/) || [])[1]; if (s) return unesc(s); }
  return 'Results';
}
function reportLines(dir, file) {
  const lines = fs.readFileSync(path.join(dir, 'slides', file), 'utf8').split('\n');
  const hits = [];
  lines.forEach((l, i) => { if (/WORD|data-sample|Sample values|Heading: what|Caption: the/.test(l)) hits.push(`  ${i + 1}: ${l.trim()}`); });
  return { count: hits.length, hits };
}

function cmdAdd(a) {
  if (a.opt.from && !a.opt.from.includes('::')) {   // a report folder alone: say what it offers
    const folder = reportFolder(a.opt.from, path.resolve(a.pos[0] && fs.existsSync(a.pos[0]) ? a.pos[0] : '.'));
    console.log(`What ${folder} offers (use as --from "${a.opt.from.replace(/[\\/]+$/, '')}::<section>::<table>"):\n${catalog(folder)}`);
    return;
  }
  const dir = deckOf(a.pos[0]);
  let files = slideFiles(dir);
  const ids = a.pos.slice(1);
  if (ids.some(x => /^AN-\d/.test(x))) return cmdAnimate(a);   // an animation id: the animate command does it
  if (a.opt.data && !fs.existsSync(path.resolve(a.opt.data))) stop(`data file ${path.resolve(a.opt.data)} not found`);
  const I = lib(dir, a.opt.library);
  const notes = [];
  ids.forEach(x => { if (!/^[A-Z]{2}-\d{2,}$/.test(x)) stop(`"${x}" is not a library id (two capitals, a hyphen, two digits, such as LV-05 or CT-34)`); getItem(I, x); });
  const slideId = ids.find(x => SLIDE_ID.test(x)), itemId = ids.find(x => ITEM_ID.test(x));
  ids.filter(x => x !== slideId && x !== itemId).forEach(x => notes.push(`Ignored ${x}: add takes one slide id and one chart, table or hero card id (${getItem(I, x).h.type}s: ${/^TH-/.test(x) ? 'deck.js theme' : 'not added to slides'}).`));
  if (!slideId && !itemId) stop('give a slide id (FR EX LV CH CP BD UN DE BK), a chart, table or hero card id (CT TB HC), or both');
  const after = a.opt.after === undefined ? files.length - 1 : String(a.opt.after) === '0' ? -1 : findSlide(dir, files, a.opt.after);
  const isFrame = slideId && /^FR-/.test(slideId);
  const section = isFrame && a.opt.section === undefined ? undefined : sectionNear(dir, files, after, a.opt.section);
  if (slideId && !itemId && (a.opt.data || a.opt.from || a.slots.length || a.opt.by))
    notes.push(`MANUAL: ${slideId}'s own chart holds sample values and takes no data, so the slide went in without your data (as {file}). To show the data, run
    ${ME} add "${dir}" ${slideId} CT-34 ${a.opt.data ? `--data "${a.opt.data}"` : a.opt.from ? `--from "${a.opt.from}"` : '--data <file>'} ${a.slots.map(s => `--slot "${s}"`).join(' ') || '--slot label=<text column> --slot value=<number column>'}${a.opt.by ? ` --by ${a.opt.by}` : ''}
  (CT-34 is plain bars; CT-35 line, CT-36 stacked bars, TB-09 table and HC-15 cards also take data; deck.js show <id> lists their slots), then delete {file}.`);
  if (slideId && itemId) {   // a slide with no spot for the item: both go in, the item on a plain chart slide right after
    const spots = I.copyOf(getItem(I, slideId)).spots || [];
    if (!(a.opt.spot ? spots.includes(a.opt.spot) : spots.some(s => /^(chart|table|figure)/.test(s)))) {
      const first = finishAdd(I, a, dir, files, after, section, slideId, null, null, null,
        notes.concat([`MANUAL: ${slideId} has no ${a.opt.spot ? `spot "${a.opt.spot}"` : 'chart spot'} (its spots: ${spots.join(', ')}), so ${itemId} went on a plain chart slide right after it. Keep both, or move the item by hand.`]));
      files = slideFiles(dir);
      const b = Object.assign({}, a, { opt: Object.assign({}, a.opt, { headline: undefined, id: undefined }) });
      const p = prepareItem(I, b, dir, itemId, /^(chart|table|hero card)$/, 'a chart, table or hero card');
      finishAdd(I, b, dir, files, files.indexOf(first), sectionNear(dir, files, files.indexOf(first), a.opt.section), null, itemId, p.item, p.src, p.said);
      return;
    }
  }
  const { item, src, said } = itemId ? prepareItem(I, a, dir, itemId, /^(chart|table|hero card)$/, 'a chart, table or hero card') : { item: null, src: null, said: [] };
  finishAdd(I, a, dir, files, after, section, slideId, itemId, item, src, notes.concat(said));
}

/* A library item copied and, with --data or --from, filled: its html carries the data record on its wrapper. */
function prepareItem(I, a, dir, itemId, types, what) {
  let item = null, src = null;
  const said = [];
  {
    const it = getItem(I, itemId);
    if (!types.test(it.h.type)) stop(`${itemId} is a ${it.h.type}, not ${what}`);
    item = I.copyOf(it);
    if (a.opt.data || a.opt.from) {
      let rows, record, label;
      if (a.opt.from) {
        const [typed, an, tb] = a.opt.from.split('::').map(s => s.trim());
        if (!an) stop('--from "<report folder>::<section>[::<table>]" (the folder alone lists its sections and tables)');
        const folder = reportFolder(typed, dir);
        rows = runReport(folder, an, tb);
        record = `${rel(dir, folder)}::${an}${tb ? '::' + tb : ''}`;
        label = `${path.basename(folder)} report, ${an.replace(/^s\d+_/, '')}${tb ? ' ' + tb : ''}`;
      } else {
        const f = path.resolve(a.opt.data);
        if (!fs.existsSync(f)) stop(`data file ${f} not found`);
        rows = readTable(f); record = rel(dir, f); label = path.basename(f);
      }
      if (!rows.length) said.push(`MANUAL: the data has no rows, so ${itemId} went in on placeholder data in {file}. Point it at data that has rows:
    {refill} --data <file>`);
      const sm = slotMap(a.slots, item.data, rows, itemId, said);
      const map = sm.map;
      /* raw rows (a label repeats, or --by): sum the numbers by it, days become months when there are many;
         --by makes one column per group; tables keep their first rows (--top) */
      const textSlot = item.data.find(s => s.kind === 'text' && (map[s.name] || []).length);
      const by = textSlot ? map[textSlot.name][0] : null;
      let shape = null;
      let split = a.opt.by;
      if (split && !by) { said.push(`Ignored --by ${split}: the label slot has no column.`); split = null; }
      if (split && rows.length && !(split in rows[0])) { said.push(`Ignored --by ${split}: the data has no column "${split}" (columns: ${Object.keys(rows[0]).join(', ')}).`); split = null; }
      const splitSlot = split && item.data.find(s => s.kind === 'number' && /one or more|any/.test(s.count) && (map[s.name] || []).length);
      if (split && !splitSlot) { said.push(`Ignored --by ${split}: ${itemId} takes one value column, so it cannot show one line or bar per group (CT-34 bars, CT-35 lines and CT-36 stacked bars can).`); split = null; }
      if (split && map[splitSlot.name].length !== 1) { said.push(`--by splits one column: used ${map[splitSlot.name][0]}.`); map[splitSlot.name] = map[splitSlot.name].slice(0, 1); }
      if (!by && sm.missing.some(s => s.kind === 'text') && rows.length > 5) { rows = rows.slice(0, 5); said.push('The label slot has no column: placeholder labels on the first 5 rows.'); }
      if (by && (split || new Set(rows.map(r => r[by])).size < rows.length)) {
        const days = rows.every(r => typeof r[by] === 'string' && ISO_DAY.test(r[by]));
        const month = days && new Set(rows.map(r => r[by])).size > 24;
        const firstNum = item.data.filter(s => s.kind === 'number').flatMap(s => map[s.name] || [])[0];
        const periods = month || rows.slice(0, 50).every(r => PERIOD.test(String(r[by])) || ISO_DAY.test(String(r[by])));
        shape = { agg: a.opt.agg === 'mean' ? 'mean' : 'sum', by, month, order: periods ? 'label' : firstNum };
        if (split) {
          const slot = splitSlot;
          Object.assign(shape, { split, value: map[slot.name][0], order: periods ? 'label' : undefined });
          rows = applyShape(rows, shape);
          if (rows.parts.length > 6) said.push(`${split} has ${rows.parts.length} groups: a slide reads 4 at most.`);
          map[slot.name] = rows.parts;
        } else rows = applyShape(rows, shape);
        said.push(`Grouped: ${shape.agg} by ${by}${month ? ' month' : ''}${split ? `, one ${item.type === 'chart' ? 'series' : 'column'} per ${split} (${map[splitSlot.name].join(', ')})` : ''}, ${rows.length} rows, ${periods ? 'in order' : shape.order ? `largest ${shape.order} first` : 'in source order'}.`);
      }
      if (SORT_FIRST[itemId] && (map[SORT_FIRST[itemId]] || []).length && !(shape && shape.by)) {   // largest first, as the item's recipe says
        const c = map[SORT_FIRST[itemId]][0];
        rows = rows.slice().sort((x, y) => (toNumber(y[c]) || 0) - (toNumber(x[c]) || 0));
        shape = Object.assign(shape || {}, { order: c });
        said.push(`Sorted largest ${c} first (the item's recipe).`);
      }
      let top = a.opt.top !== undefined ? Number(a.opt.top) : item.type === 'table' ? 8 : 0;
      if (a.opt.top !== undefined && !(top > 0)) { said.push(`Ignored --top ${a.opt.top}: give a number of rows, such as --top 8.`); top = item.type === 'table' ? 8 : 0; }
      if (top && rows.length > top) {
        const all = rows.length, parts = rows.parts;
        rows = rows.slice(0, top); rows.parts = parts;
        shape = Object.assign(shape || {}, { top });
        said.push(`Kept the first ${top} of ${all} rows${a.opt.top === undefined ? ' (a slide reads about 8; --top N to change)' : ''}.`);
      }
      if (!rows.length) rows = [{}, {}, {}, {}, {}];
      /* slots worked out from others: largest first where the item wants it, then the calculations add can do */
      const derived = derivedSlots(item);
      const calc = applyCalc(itemId, rows, map, said);
      Object.entries(derived).forEach(([n, how]) => {
        if ((map[n] || []).length && !(COMPUTE[itemId] || {})[n]) said.push(`${n} must be worked out first (${how}); check that ${map[n].join(', ')} already holds that.`);
      });
      const missing = item.data.filter(s => /^(one|one or more)$/.test(s.count) && !(map[s.name] || []).length);
      placeholders(rows, missing, map);   // required slots with no column: marked placeholder data
      missing.forEach(s => said.push(manualLine(s, s.kind === 'text' ? sm.texts : s.kind === 'number' ? sm.nums : sm.texts.concat(sm.nums), derived[s.name])));
      const numCols = item.data.filter(s => s.kind !== 'text').flatMap(s => map[s.name] || []).filter(c => rows.length && c in rows[0]);
      let fmt = a.opt.format || (shape && shape.split ? guessFormat(shape.value, rows.map(r => ({ [shape.value]: r[numCols[0]] }))) : numCols[0] && !/^MANUAL /.test(numCols[0]) ? guessFormat(numCols[0], rows) : 'none');
      if (!FORMATS[fmt] && fmt !== 'none') { said.push(`Ignored --format ${fmt}: it is one of ${FORMAT_NAMES}.`); fmt = numCols[0] ? guessFormat(numCols[0], rows) : 'none'; }
      const pct = new Set(Object.entries(COMPUTE[itemId] || {}).filter(([, v]) => /^(runshare|rowpct)$/.test(v[0])).flatMap(([k]) => map[k] || []));   // worked-out shares read in %
      rows = tidy(rows, numCols.filter(c => !pct.has(c)), fmt);
      let html = fillBlock(I, item.html, rows, map, fmt, pct);
      html = html.replace(/\s*<p class="lib-source"[^>]*>Sample values[^<]*<\/p>/, '');
      const attrs = ` data-source="${escA(record)}"${shape ? ` data-shape="${escA(shapeText(shape))}"` : ''} data-format="${fmt}"` +
        (calc ? ` data-calc="${escA(calc)}"` : '') + (missing.length ? ` data-manual="${missing.map(s => s.name).join(' ')}"` : '') +
        (item.type === 'chart' ? '' : ` data-cols="${escA(colsText(map, Object.keys(rows[0] || {})))}"`);
      html = html.replace(/^<div data-item="([^"]+)"/, `<div data-item="$1"${attrs}`);
      item.html = html;
      src = { label, record };
      const labelCol = textSlot ? map[textSlot.name][0] : null;
      said.push(`Data: ${Object.entries(map).map(([k, v]) => `${k}=${v.join(',')}`).join('; ')} from ${record}; numbers as ${fmt}${a.opt.format ? '' : ' (guessed; --format to change)'}.`);
      said.push(...factsAll(rows, labelCol, numCols.filter(c => !/^MANUAL /.test(c) && !pct.has(c)), fmt), ...factsAll(rows, labelCol, [...pct], '%'));
    } else {
      item.html = stripControls(item.html).replace(/^<div data-item="([^"]+)"/, '<div data-item="$1" data-sample');
      said.push(`${itemId} holds library sample values: give --data or --from with --slot to fill it (${item.dataLine}).`);
    }
    if (item.js && /data-csv/.test(item.js)) item.js = '';
    if (item.type !== 'chart') {   // the item's own wording (heading, caption, notes): every text not filled from data
      const tree = parse(item.html);
      prefixAll(tree, 'WORD: ', x => attr(x, 'data-slot') !== null || attr(x, 'data-rows') !== null || /^(button|script|style)$/.test(x.tag) || /\blib-source\b/.test(attr(x, 'class') || ''));
      item.html = serialize(tree);
    }
  }
  return { item, src, said };
}

function finishAdd(I, a, dir, files, after, section, slideId, itemId, item, src, said) {
  /* the slide */
  const basis = item ? ((item.html.match(/<p class="basis">([\s\S]*?)<\/p>/) || [])[1] || '') : '';
  const foot = `WORD: ${basis && !/^What is measured/.test(basis) ? basis.replace(/\.?\s*Sample values\.?/, '') : 'what is measured, the period'}.${src ? ` Source: ${esc(src.label)}.` : ''}`.replace(/\.\./g, '.');
  let text, from = [slideId, itemId].filter(Boolean).join(' ');
  if (!slideId) {
    const wrap = item.html.replace(/<p class="basis">[\s\S]*?<\/p>\s*/, '').replace(/^<div data-item="([^"]+)"/, '<div data-item="$1" data-spot="chart"');
    text = plainSlide({ id: 'x', section, headline: a.opt.headline, from, footnote: foot, spot: wrap.split('\n').map(l => '      ' + l).join('\n') });
  } else {
    const sl = I.copyOf(getItem(I, slideId));
    let block = sl.html;
    const spots = sl.spots || [];
    if (item) {
      const spot = a.opt.spot || spots.find(s => /^chart/.test(s)) || spots.find(s => /^table/.test(s)) || spots.find(s => /^figure/.test(s));
      if (!spot) stop(`${slideId} has no chart, table or figure spot to take ${itemId} (its spots: ${spots.join(' ')}). Add ${itemId} alone for a plain chart slide.`);
      if (!spots.includes(spot)) stop(`${slideId} has no spot "${spot}"; its spots: ${spots.join(' ')}`);
      const ind = ((block.split('\n').find(l => l.includes(`data-spot="${spot}"`)) || '').match(/^\s*/) || [''])[0];
      block = I.swap(block, Object.assign({}, item, { html: item.html.split('\n').map((l, i) => (i ? ind + '  ' : '') + l).join('\n').replace(/\n\s*<\/div>$/, `\n${ind}</div>`) }), spot).html;
    }
    const tree = parse(block);
    walk(tree, (n, parent) => {
      if (n.tag === 'section') {
        setAttr(n, 'data-component', null); setAttr(n, 'id', 'x');
        if (section !== undefined) setAttr(n, 'data-section', escA(section));
        setAttr(n, 'data-from', from);
        return;
      }
      const s = attr(n, 'data-spot');
      if (!s) return;
      if (n.tag === 'div' && attr(n, 'data-item') !== null) {   // the swapped item: its spot's grid uses the deck's gap
        if (parent && /grid/.test(attr(parent, 'style') || '')) setAttr(parent, 'style', attr(parent, 'style').replace(/gap:\s*\d+px/, 'gap: var(--split-gap)'));
        return false;
      }
      if (/^(chart|table)/.test(s)) { setAttr(n, 'data-sample', null); n.attrs.push(['data-sample', null]); if (parent && /grid/.test(attr(parent, 'style') || '')) setAttr(parent, 'style', attr(parent, 'style').replace(/gap:\s*\d+px/, 'gap: var(--split-gap)')); return false; }
      if (s === 'kicker' && section) { n.children = [esc(section)]; return false; }
      if (s === 'headline' && a.opt.headline) {   // the headline's own text; anything nested (a quote's cite) stays to word
        const i = n.children.findIndex(c => typeof c === 'string' && c.trim());
        if (i === -1) n.children = [esc(a.opt.headline)];
        else { n.children[i] = n.children[i].replace(/\S[\s\S]*\S|\S/, () => esc(a.opt.headline)); n.children.filter(c => typeof c === 'object').forEach(c => prefixAll(c, 'WORD: ')); }
        return false;
      }
      if (s === 'footnote' && item) { n.children = [foot]; return false; }
      prefixAll(n, 'WORD: ');   // every piece of text in the spot: a bullet each, a quote and its cite
      return false;
    });
    text = serialize(tree).replace(/^\s+/, '').replace(/\n[ \t]*(?=\n)/g, '').replace(/\n {6}<\/section>\s*$/, '\n</section>') + '\n';
    if (slideId && !item && /data-sample/.test(text)) said.push(`${slideId} keeps its library sample chart or table (marked data-sample). To fill it, add ${slideId} with a chart id and --data, or edit it by hand.`);
  }
  if (item && item.css) text += `<style>\n${item.css}\n</style>\n`;
  if (item && item.js) text += `<script>\n${item.js}\n</script>\n`;
  const tidyId = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'slide';
  let want = a.opt.id ? tidyId(a.opt.id) : slug(a.opt.headline || (src && item ? `${item.name} ${src.label.replace(/\.\w+$/, '')}` : (slideId ? getItem(I, slideId).h.name : item.name)));
  if (a.opt.id && want !== a.opt.id) said.unshift(`--id ${a.opt.id} became ${want} (lowercase letters, digits and hyphens).`);
  const done = place(dir, files, after, want, text);
  build(dir, true);
  const r = reportLines(dir, done.file);
  console.log(`Added slides/${done.file} (${from}${src ? `, data from ${src.record}` : ''}), slide ${after + 2} of ${files.length + 1}.`);
  const manual = said.filter(s => /^MANUAL:/.test(s)).map(s => fillTokens(s, dir, done.file, done.id));
  said.filter(s => !/^MANUAL:/.test(s)).forEach(s => console.log(fillTokens(s, dir, done.file, done.id)));
  if (manual.length) console.log(`\n${manual.join('\n')}`);
  console.log(`\nWords to write: edit only these ${r.count} line${r.count === 1 ? '' : 's'} of slides/${done.file}:\n${r.hits.join('\n') || '  (none)'}`);
  console.log(`\nThen: ${ME} build "${dir}"`);
  return done.file;
}

function cmdOwn(a) {
  const dir = deckOf(a.pos[0]);
  const files = slideFiles(dir);
  const after = a.opt.after === undefined ? files.length - 1 : String(a.opt.after) === '0' ? -1 : findSlide(dir, files, a.opt.after);
  const section = sectionNear(dir, files, after, a.opt.section);
  const text = plainSlide({ id: 'x', section, headline: a.opt.headline, spot: BLANK_CHART, footnote: 'WORD: what is measured, the period. Source: WORD.' });
  const done = place(dir, files, after, a.opt.id || slug(a.opt.headline || 'own-chart'), text);
  build(dir, true);
  const r = reportLines(dir, done.file);
  console.log(`Added slides/${done.file}: a blank slide (headline, chart spot with empty options, commentary), slide ${after + 2} of ${files.length + 1}.`);
  console.log('Write the chart options in its <script type="application/json"> (references/make-your-own-slide.md); or put a table, cards or text in the chart spot instead.');
  console.log(`\nWords to write: edit only these ${r.count} lines of slides/${done.file}:\n${r.hits.join('\n')}`);
  console.log(`\nThen: ${ME} build "${dir}"`);
}

/* ---------------------------------------------------------------- show */
/* One library item's parts, never its code: what it is, its spots or data slots, and with data the columns that fit
   each slot and a ready add command. */
function cmdShow(a) {
  const id = a.pos.find(x => /^[A-Z]{2}-\d{2,}$/.test(x));
  if (!id) stop('give a library id: deck.js show LV-05 [<deck>] [--data <file> | --from "<report>::<section>::<table>"]');
  const deckArg = a.pos.find(x => x !== id);
  const base = deckArg ? (resolveDeck(deckArg) || process.cwd()) : process.cwd();
  const I = lib(base, a.opt.library);
  const c = I.copyOf(getItem(I, id));
  const out = [], deck = deckArg ? `"${deckArg}"` : '<deck>';
  const purpose = String(c.purpose || '').replace(/\s+/g, ' ');
  out.push(`${id}  ${c.name}  (${c.type})`, purpose.length > 160 ? purpose.slice(0, purpose.lastIndexOf(' ', 157)) + ' ...' : purpose);
  if (c.type === 'slide') {
    const counts = {};
    (c.spots || []).forEach(s => { const k = s.replace(/-\d+$/, ''); counts[k] = (counts[k] || 0) + 1; });
    out.push(`Spots (the parts you word or fill): ${Object.entries(counts).map(([k, n]) => (n > 1 ? `${k} x${n}` : k)).join(', ')}`);
    const holder = (c.spots || []).find(s => /^(chart|table|figure)/.test(s));
    if (/^(chart|table)/.test(holder || '')) out.push(`Its own ${holder.replace(/-\d+$/, '')} shows sample values and takes no data. To show your data, add a chart, table or hero card id after this slide's id; it goes into the ${holder} spot.`);
    else if (holder) out.push(`No chart spot. A chart, table or hero card id given with it goes into its ${holder} spot.`);
    else out.push('No chart spot: it takes no chart and no data. A chart id given with it goes on a plain chart slide after it.');
  } else if (c.type === 'theme') out.push(`A theme: deck.js theme ${deck} ${id}`);
  else {
    if (c.type === 'animation') out.push(`Moves: ${c.attaches || '-'}.  Fits: ${c.fits || '-'}.`);
    if (!c.data.length) out.push(c.type === 'animation' ? 'No data slots: its data is in its own script, edited by hand.' : 'No data slots.');
    else {
      out.push('Data slots (fill each with --slot <name>=<column>):');
      const w = Math.max(...c.data.map(s => s.name.length));
      const kind = s => (s.kind === 'figure' ? 'one value (a column\'s first value, or typed as is)' : `${s.kind} column${/one or more|any/.test(s.count) ? 's' : ''}`);
      const need = s => ({ one: 'required, one', 'one or more': 'required, one or more', optional: 'optional, one', any: 'optional, any number' }[s.count]);
      const der = derivedSlots(c), comp = COMPUTE[id] || {};
      c.data.forEach(s => {
        out.push(`  ${s.name.padEnd(w)}  ${kind(s)}, ${need(s)}`);
        if (der[s.name] || comp[s.name]) out.push(`  ${''.padEnd(w)}  worked out first: ${der[s.name] || 'from ' + comp[s.name].slice(1).join(' and ')}${comp[s.name] ? ` - add does this from ${comp[s.name][0] === 'rowpct' ? 'the columns you give it' : comp[s.name].slice(1).join(' and ')}` : ' - add cannot: make it a column in your data first, or type it in by hand after adding'}`);
      });
      calcInputs(id).filter(n => !c.data.some(s => s.name === n)).forEach(n => out.push(`  ${n.padEnd(w)}  number column, needed so add can work out ${Object.entries(comp).filter(([, v]) => v.includes(n)).map(([k]) => k).join(', ')}`));
    }
  }
  if (c.recipe) out.push(`Recipe (shape the data first): ${c.recipe}`);
  if ((a.opt.data || a.opt.from) && c.type !== 'theme') {
    let rows, flag;
    if (a.opt.from) { const [t, an, tb] = a.opt.from.split('::').map(s => s.trim()); if (!an) stop('--from "<report folder>::<section>[::<table>]"'); const folder = reportFolder(t, base); rows = runReport(folder, an, tb); flag = `--from "${a.opt.from}"`; }
    else { const f = path.resolve(a.opt.data); if (!fs.existsSync(f)) stop(`data file ${f} not found`); rows = readTable(f); flag = `--data "${a.opt.data}"`; }
    const cols = Object.keys(rows[0] || {}), isText = col => rows.slice(0, 200).some(r => typeof r[col] === 'string' && r[col] !== '');
    const texts = cols.filter(isText), nums = cols.filter(x => !isText(x));
    const slots = c.type === 'slide' ? null : c.data;
    out.push(`Your data: ${rows.length} rows; text columns: ${texts.join(', ') || 'none'}; number columns: ${nums.join(', ') || 'none'}.`);
    const chartId = c.type === 'slide' ? ((c.spots || []).some(s => /^(chart|table|figure)/.test(s)) ? 'CT-34' : null) : null;
    /* the ready command never maps a raw column onto a slot that is worked out first; it gives the inputs add needs */
    const useId = slots ? id : chartId, useItem = useId ? I.copyOf(getItem(I, useId)) : null;
    const der = useItem ? derivedSlots(useItem) : {}, comp = COMPUTE[useId] || {};
    const use = (useItem ? useItem.data : []).filter(s => !der[s.name] && !(comp[s.name] && comp[s.name][0] !== 'rowpct'))
      .concat(calcInputs(useId).filter(n => !(useItem ? useItem.data : []).some(s => s.name === n)).map(n => ({ name: n, kind: 'number', count: 'one' })));
    const distinct = col => new Set(rows.map(r => r[col])).size;
    const tp = texts.filter(x => distinct(x) > 1).sort((x, y) => distinct(x) - distinct(y)), np = nums.slice(), pick = {};   // labels: the column with fewest groups first
    use.forEach(s => {
      const fit = s.kind === 'text' ? texts : s.kind === 'number' ? nums : cols;
      if (slots) out.push(`  ${s.name}: ${fit.join(', ') || 'no column fits'}`);
      if (/^one/.test(s.count)) { const pool = s.kind === 'text' ? tp : np; const v = pool.find(x => fit.includes(x)); if (v) { pick[s.name] = v; pool.splice(pool.indexOf(v), 1); } }
    });
    const slotArgs = Object.entries(pick).map(([k, v]) => `--slot ${k}=${v}`).join(' ');
    const cmd = c.type === 'animation' ? `animate ${deck} ${id}` : c.type === 'slide' ? (chartId ? `add ${deck} ${id} ${chartId}` : `add ${deck} ${id}`) : `add ${deck} ${id}`;
    if (c.type === 'slide' && !chartId) out.push('This slide takes no data; add it without --data.');
    else out.push(`Ready to copy${chartId ? ` (with ${chartId} plain bars in its chart spot; any chart id works)` : ''}:`, `  ${ME} ${cmd} ${flag} ${slotArgs}`.replace(/\s+$/, ''));
    const lab = Object.entries(pick).find(([k]) => (use.find(s => s.name === k) || {}).kind === 'text');
    if (lab && distinct(lab[1]) < rows.length) out.push(`Raw rows: ${lab[1]} repeats, so the numbers are summed by it (dates by month when there are many).`);
  } else if (c.type !== 'slide' && c.type !== 'theme' && c.data.length) out.push(`With --data <file> or --from "<report>::<section>::<table>", show lists the columns that fit each slot and a ready add command.`);
  console.log(out.join('\n'));
}

/* ---------------------------------------------------------------- animate */
/* An animation (AN id) as a slide of its own, or into a spot of an existing slide (a figure, a chart, a table),
   chosen by what it moves (its attaches line). It plays each time its slide shows. */
function cmdAnimate(a) {
  const dir = deckOf(a.pos[0]);
  const files = slideFiles(dir);
  const rest = a.pos.slice(1), anId = rest.find(x => /^AN-\d{2,}$/.test(x)), key = rest.find(x => x !== anId);
  if (!anId) return cmdAdd(a);   // no animation id: an ordinary add
  if (a.opt.data && !fs.existsSync(path.resolve(a.opt.data))) stop(`data file ${path.resolve(a.opt.data)} not found`);
  const I = lib(dir, a.opt.library);
  const it = getItem(I, anId);
  const fits = it.h.fits || '';
  if (!/\bdeck\b/.test(fits) || /^none/.test(fits)) stop(`${anId} does not fit a deck (${fits}).`);
  const { item, src, said } = prepareItem(I, a, dir, anId, /^animation$/, 'an animation');
  item.html = item.html.replace(/^<div data-item="([^"]+)"/, '<div data-item="$1" data-trigger="manual"');
  said.push(`${anId} moves: ${item.attaches || '-'}. It plays each time its slide shows, has a Replay button, and shows its end state in screenshots, print and PDF.`);
  const own = (after, extra) => finishAdd(I, a, dir, files, after, sectionNear(dir, files, after, a.opt.section), null, anId, item, src, said.concat(extra || []));
  if (key === undefined) return own(a.opt.after === undefined ? files.length - 1 : String(a.opt.after) === '0' ? -1 : findSlide(dir, files, a.opt.after));
  /* into an existing slide: the spot that holds what it moves */
  const at = findSlide(dir, files, key), f = files[at], p = path.join(dir, 'slides', f);
  const tree = parse(fs.readFileSync(p, 'utf8'));
  const spots = [];
  walk(tree, (n, parent) => { const s = attr(n, 'data-spot'); if (s) { spots.push({ s, n, parent }); return false; } });
  const holds = (x, kind) => kind === 'figure' ? /^figure/.test(x.s) || /^HC-/.test(attr(x.n, 'data-item') || '') : kind === 'table' ? /^table/.test(x.s) || /^TB-/.test(attr(x.n, 'data-item') || '') : /^chart/.test(x.s);
  const kinds = (item.attaches || '').split(/,\s*/).map(k => (k === 'blocks' || k === 'steps' ? 'chart' : k)).concat(['chart', 'table', 'figure']);
  let hit = a.opt.spot ? spots.find(x => x.s === a.opt.spot) : null;
  for (const k of kinds) { if (hit) break; hit = spots.find(x => holds(x, k)); }
  if (!hit) {   // nowhere to put it: a slide of its own right after, and say so
    return own(at, [`MANUAL: slides/${f} has no ${a.opt.spot ? `spot "${a.opt.spot}"` : 'chart, table or figure spot'} for ${anId} (its spots: ${spots.map(x => x.s).join(', ')}), so it went on a slide of its own right after it. Keep both, or move it by hand.`]);
  }
  const ind = '      ';
  const wrap = elements(parse(item.html.replace(/<p class="basis">[\s\S]*?<\/p>\s*/, '').split('\n').map((l, i) => (i ? ind + '  ' : '') + l).join('\n')))[0];
  setAttr(wrap, 'data-spot', hit.s);
  hit.parent.children[hit.parent.children.indexOf(hit.n)] = wrap;
  let text = serialize(tree).replace(/\n*$/, '\n');
  if (item.css && !text.includes(item.css)) text += `<style>\n${item.css}\n</style>\n`;
  if (item.js && !text.includes(item.js)) text += `<script>\n${item.js}\n</script>\n`;
  fs.writeFileSync(p, prettyScripts(text));
  build(dir, true);
  const r = reportLines(dir, f);
  console.log(`slides/${f}: ${anId} is in its ${hit.s} spot (it replaced ${attr(hit.n, 'data-item') || hit.n.tag}).`);
  const sid = readSlide(dir, f).id;
  said.filter(s => !/^MANUAL:/.test(s)).forEach(s => console.log(fillTokens(s, dir, f, sid)));
  const manual = said.filter(s => /^MANUAL:/.test(s));
  if (manual.length) console.log(`\n${manual.map(s => fillTokens(s, dir, f, sid)).join('\n')}`);
  console.log(`\nWords to write: edit only these ${r.count} line${r.count === 1 ? '' : 's'} of slides/${f}:\n${r.hits.join('\n') || '  (none)'}`);
  console.log(`\nThen: ${ME} build "${dir}"`);
}

/* ---------------------------------------------------------------- refill */
function elementEnd(text, start) {   // the index after the </div> closing the <div> that opens at start
  const re = /<(\/?)div\b[^>]*>/g; re.lastIndex = start; let depth = 0, m;
  while ((m = re.exec(text))) { depth += m[1] ? -1 : 1; if (!depth) return re.lastIndex; }
  return -1;
}
function cmdRefill(a) {
  const dir = deckOf(a.pos[0]);
  const files = slideFiles(dir);
  const one = a.pos[1] !== undefined;
  if (a.opt.by && !one) stop('--by changes one slide: refill <deck> <slide> --by <column>');
  if (a.opt.data && a.opt.from) stop('give --data or --from, not both');
  /* a new source: --data replaces every file source (a report source with --from), or every source of the one slide named */
  let newSrc = null;
  if (a.opt.data) { const f = path.resolve(a.opt.data); if (!fs.existsSync(f)) stop(`${f} not found`); newSrc = { report: false, record: rel(dir, f) }; }
  if (a.opt.from) {
    const [typed, an, tb] = a.opt.from.split('::').map(s => s.trim());
    if (!an) stop('--from "<report folder>::<section>[::<table>]"');
    newSrc = { report: true, record: `${rel(dir, reportFolder(typed, dir))}::${an}${tb ? '::' + tb : ''}` };
  }
  const which = one ? [files[findSlide(dir, files, a.pos[1])]] : files;
  const cache = {}, stale = [];
  let n = 0;
  which.forEach(f => {
    const p = path.join(dir, 'slides', f);
    let text = fs.readFileSync(p, 'utf8');
    const before = text;
    const re = /<div\b[^>]*\bdata-source="([^"]+)"[^>]*>/g;
    let m, changed = false;
    const edits = [];
    while ((m = re.exec(text))) {
      let open = m[0];
      const start = m.index, end = elementEnd(text, start);
      if (end === -1) { console.log(`slides/${f}: the element with data-source has no closing </div>; skipped`); continue; }
      let srcText = unesc(m[1]);
      if (newSrc && (one || newSrc.report === srcText.includes('::'))) srcText = newSrc.record;
      const src = cache[srcText] || (cache[srcText] = loadSource(srcText, dir));
      let sh = parseShape(unesc((open.match(/data-shape="([^"]*)"/) || [])[1] || ''));
      const fmt = (open.match(/data-format="([^"]*)"/) || [])[1] || 'none';
      const itemId = (open.match(/data-item="([^"]*)"/) || [])[1] || 'chart';
      let inner = text.slice(start + open.length, end - 6);
      if (a.opt.by) {   // re-point: one series per group of a column of the raw rows
        const j = inner.match(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/);
        if (!j) stop(`--by works on charts; slides/${f} holds ${itemId}`);
        const o = JSON.parse(j[1]);
        const cat = [].concat(o.xAxis || [], o.yAxis || []).find(x => x && x.type === 'category' && typeof x.col === 'string');
        const val = (sh && sh.value) || ([].concat(o.series || []).find(s => s && typeof s.col === 'string' && !s.col.includes(',') && typeof s.figure !== 'string') || {}).col;
        if (!cat || !val) stop(`slides/${f}: the chart has no category axis and value series marked "col" to split`);
        const raw = src.rows;
        if (raw.length && !(a.opt.by in raw[0])) stop(`${srcText} has no column "${a.opt.by}" (columns: ${Object.keys(raw[0]).join(', ')}). --by needs the raw rows: add --data <raw file>`);
        if (raw.length && !(val in raw[0])) stop(`${srcText} has no column "${val}" to sum; columns: ${Object.keys(raw[0]).join(', ')}`);
        const days = raw.every(r => typeof r[cat.col] === 'string' && ISO_DAY.test(r[cat.col]));
        const periods = days || raw.slice(0, 50).every(r => PERIOD.test(String(r[cat.col])));
        sh = { agg: (sh && sh.agg) || 'sum', by: cat.col, month: (sh && sh.month) || (days && new Set(raw.map(r => r[cat.col])).size > 24), split: a.opt.by, value: val, order: periods ? 'label' : undefined, top: sh && sh.top };
        const parts = applyShape(raw.map(r => Object.assign({}, r)), sh).parts;
        splitSeries(o, parts, val);
        inner = inner.replace(j[0], () => j[0].replace(j[1], JSON.stringify(o)));
      }
      let rows = applyShape(src.rows.map(r => Object.assign({}, r)), sh);
      reapplyCalc(rows, unesc((open.match(/data-calc="([^"]*)"/) || [])[1] || ''));   // slots worked out from others
      const still = [...new Set([...(open + inner).matchAll(/MANUAL ([a-z][a-z0-9-]*)/g)].map(m => m[1]))];
      if (still.length) placeholders(rows, still.map(n => ({ name: n, kind: rows.some(r => typeof r[n] === 'string') ? 'text' : 'number' })), {});   // slots not yet given a column keep their placeholder
      const colsAttr = (open.match(/data-cols="([^"]*)"/) || [])[1];
      const map = colsAttr ? parseCols(unesc(colsAttr)) : {};
      const typed = map.typed || new Set();
      const numCols = colsAttr ? [...new Set(Object.values(map).flat())].filter(c => rows.length && rows.some(r => typeof r[c] === 'number')) : [];
      let missing = [];
      const jsonCols = [];
      inner = inner.replace(/(<script type="application\/json"[^>]*>)([\s\S]*?)(<\/script>)/g, (all, x, j, y) => {
        let o; try { o = JSON.parse(j); } catch (e) { stop(`slides/${f}: chart JSON is not valid (${e.message}); fix it, then refill`); }
        const cs = colsOfChart(o); if (!cs.length) return all;
        jsonCols.push(...cs);
        rows = tidy(rows, [...new Set(cs)].filter(c => rows.some(r => typeof r[c] === 'number')), fmt);
        missing.push(...refillChart(o, rows, fmt));
        return x + JSON.stringify(o) + y;
      });
      if (colsAttr && /data-rows|data-slot/.test(inner)) {
        const I = lib(dir, a.opt.library);
        const cols = Object.keys(rows[0] || {});
        Object.values(map).flat().forEach(c => { if (!cols.includes(c) && !typed.has(c) && c !== 'count') missing.push(c); });
        if (!missing.length) inner = refillHtmlItem(I, inner, tidy(rows, numCols, fmt), map, fmt);
      }
      if (missing.length) { console.log(`slides/${f}: ${itemId} not refilled: ${srcText} has no column ${[...new Set(missing)].join(', ')} (columns: ${Object.keys(rows[0] || {}).join(', ')})`); continue; }
      if (rows.parts) { const shown = new Set(jsonCols); const extra = rows.parts.filter(p => !shown.has(p)); if (extra.length) console.log(`slides/${f}: new groups not on the chart: ${extra.join(', ')} (copy a series line, set its "name" and "col", refill again)`); }
      open = open.replace(/data-source="[^"]*"/, `data-source="${escA(srcText)}"`);
      const manualNow = ((open.match(/data-manual="([^"]*)"/) || [])[1] || '').split(/\s+/).filter(Boolean);
      if (manualNow.length) {   // a slot counts as filled once its placeholder is gone and this refill filled it from the data
        const left = manualNow.filter(s => (open + inner).includes(`MANUAL ${s}`));
        manualNow.filter(s => !left.includes(s)).forEach(s => console.log(`slides/${f}: ${s} is now filled from ${srcText}.`));
        open = left.length ? open.replace(/data-manual="[^"]*"/, `data-manual="${left.join(' ')}"`) : open.replace(/\s*data-manual="[^"]*"/, '');
      }
      if (sh) open = /data-shape="/.test(open) ? open.replace(/data-shape="[^"]*"/, `data-shape="${escA(shapeText(sh))}"`) : open.replace(/>$/, ` data-shape="${escA(shapeText(sh))}">`);
      edits.push({ start, end: end - 6, inner: open + inner });
      const allCols = [...new Set([...jsonCols, ...Object.values(map).flat()])].filter(c => !typed.has(c));
      const label = allCols.find(c => rows.some(r => typeof r[c] === 'string'));
      const values = allCols.filter(c => rows.length && rows.every(r => typeof r[c] === 'number'));
      console.log(`slides/${f}: ${itemId} refilled from ${srcText} (${rows.length} rows).`);
      factsAll(rows, label, values, fmt).forEach(x => console.log(`  ${x}`));
      changed = true; n++;
    }
    if (changed) {
      edits.reverse().forEach(e => { text = text.slice(0, e.start) + e.inner + text.slice(e.end); });
      text = prettyScripts(text);
      fs.writeFileSync(p, text);
      staleFigures(before, text).forEach(s => stale.push(`slides/${f} ${s}`));
    }
  });
  if (!n) { console.log('Nothing to refill: no item with data-source in ' + (one ? 'that slide' : 'the deck') + '.'); return; }
  build(dir, true);
  console.log(`\nCharts and tables hold the new figures; names, styles and axis settings are as you left them. presentation.html rebuilt.`);
  if (stale.length) { console.log(`\nFigures in the words that matched the old data and no longer do (reword them from the facts above):\n${stale.map(s => '  ' + s).join('\n')}`); process.exitCode = 1; }
  else console.log('No typed figure that matched the old data is out of date; figures worked out by hand (ratios, differences) are not checked.');
}

/* ---------------------------------------------------------------- list, theme, place */
/* Where a slide's chart (or table) sits: left, right, full, above or below its text; '' when it has none. */
function chartPlace(text) {
  let spot = null, grid = null;
  walk(parse(text), (n, parent) => { if (spot) return false; const s = attr(n, 'data-spot'); if (s && /^(chart|table)/.test(s)) { spot = n; grid = parent; return false; } });
  if (!spot) return '';
  const st = styleMap(grid && attr(grid, 'style')), kids = grid ? elements(grid) : [];
  if (!grid || !/grid/.test(st.get('display') || '') || kids.length < 2) return 'full';
  const cols = (st.get('grid-template-columns') || '').split(/\s+/).filter(Boolean);
  const first = kids.indexOf(spot) === 0;
  if (cols.length >= 2) return first ? 'left' : 'right';
  return attr(grid, 'data-place') === 'full' ? 'full' : first ? 'above the text' : 'below the text';
}
function cmdList(a) {
  const dir = deckOf(a.pos[0]);
  const files = slideFiles(dir);
  console.log(`${titleOf(dir)}: ${files.length} slides in ${path.join(dir, 'slides')}`);
  files.forEach((f, i) => {
    const t = fs.readFileSync(path.join(dir, 'slides', f), 'utf8');
    const h = (t.match(/data-spot="headline"[^>]*>([\s\S]*?)<\/(h[12]|blockquote|p)>/) || t.match(/<h[12][^>]*>([\s\S]*?)<\/h[12]>/) || [])[1] || '(no headline)';
    const from = (t.match(/data-from="([^"]*)"/) || [])[1];
    const where = chartPlace(t);
    const flags = [/WORD/.test(t) ? 'to word' : '', /data-sample/.test(t) ? 'sample values' : '', /data-source=/.test(t) ? 'has data' : '', /data-manual=/.test(t) ? 'MANUAL slot' : '', where ? `chart ${where}` : ''].filter(Boolean);
    console.log(`${String(i + 1).padStart(2)}  slides/${f}${from ? `  [${from}]` : ''}${flags.length ? `  (${flags.join(', ')})` : ''}\n    ${h.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 120)}`);
  });
}
function cmdTheme(a) {
  const dir = deckOf(a.pos[0]);
  const id = a.pos[1];
  const I = lib(dir, a.opt.library);
  const t = applyTheme(dir, I.folder, id);
  console.log(`Theme ${t.id} (${t.name}) is in ${path.join(dir, 'styles.css')}.${t.licence ? ` Its embedded font's licence is beside it (${path.basename(t.licence)}); send it with the deck.` : ''}${t.removed ? ` Removed ${t.removed.join(', ')} (the previous theme's font licence).` : ''} Open presentation.html again; no build needed.`);
}
function styleMap(s) { const m = new Map(); (s || '').split(';').map(x => x.trim()).filter(Boolean).forEach(x => { const i = x.indexOf(':'); m.set(x.slice(0, i).trim(), x.slice(i + 1).trim()); }); return m; }
const styleText = m => [...m].map(([k, v]) => `${k}: ${v};`).join(' ');
function cmdPlace(a) {
  const dir = deckOf(a.pos[0]);
  const files = slideFiles(dir);
  const f = files[findSlide(dir, files, a.pos[1])];
  const where = a.pos[2];
  if (!/^(left|right|full)$/.test(where || '')) stop('where the chart sits: left, right or full');
  const p = path.join(dir, 'slides', f);
  const tree = parse(fs.readFileSync(p, 'utf8'));
  let spot = null, grid = null;
  walk(tree, (n, parent) => {
    if (spot) return false;
    const s = attr(n, 'data-spot');
    if (s && (a.opt.spot ? s === a.opt.spot : /^(chart|table)/.test(s))) { spot = n; grid = parent; return false; }
  });
  if (!spot) stop(`slides/${f} has no chart or table spot`);
  const kids = grid ? elements(grid) : [];
  const st = styleMap(grid && attr(grid, 'style'));
  if (!grid || !/grid/.test(st.get('display') || '') || kids.length !== 2) stop(`in slides/${f} the chart is not one of two blocks side by side in a grid; move it by hand (its grid line: grid-template-columns)`);
  const other = kids.find(k => k !== spot);
  const cols = (st.get('grid-template-columns') || '').split(/\s+/).filter(Boolean);
  let chartW, otherW;
  const saved = (attr(grid, 'data-widths') || '').split(/\s+/).filter(Boolean);
  if (cols.length === 2) { const ci = kids.indexOf(spot); chartW = cols[ci]; otherW = cols[1 - ci]; }
  else if (saved.length === 2) [chartW, otherW] = saved;
  else [chartW, otherW] = ['3fr', '2fr'];
  const between = grid.children.filter(c => typeof c === 'string');
  const ws = between[1] !== undefined ? between[1] : '\n';
  if (where === 'full') {
    st.set('grid-template-columns', '1fr'); st.set('grid-template-rows', '1fr auto');
    setAttr(grid, 'data-widths', `${chartW} ${otherW}`);
    grid.children = [between[0] || '\n', spot, ws, other, between[2] || '\n'];
  } else {
    st.delete('grid-template-rows');
    st.set('grid-template-columns', where === 'left' ? `${chartW} ${otherW}` : `${otherW} ${chartW}`);
    setAttr(grid, 'data-widths', null);
    grid.children = [between[0] || '\n', where === 'left' ? spot : other, ws, where === 'left' ? other : spot, between[2] || '\n'];
  }
  setAttr(grid, 'style', styleText(st)); setAttr(grid, 'data-place', where);
  fs.writeFileSync(p, serialize(tree));
  build(dir, true);
  console.log(`slides/${f}: chart ${where === 'full' ? 'full width, commentary under it' : `on the ${where}`}. presentation.html rebuilt.`);
}

/* ---------------------------------------------------------------- new */
function cmdNew(a) {
  if (!a.pos[0]) stop(`${ME} new <name or folder> --title "Short deck title" [--theme TH-02]`);
  const home = decksHome(process.cwd());
  const dir = plainName(a.pos[0]) ? path.join(home.folder, a.pos[0]) : path.resolve(a.pos[0]);
  if (fs.existsSync(path.join(dir, 'presentation.html')) || fs.existsSync(path.join(dir, 'slides'))) stop(`${dir} already holds a deck`);
  if (!a.opt.title) a.opt.title = pretty(path.basename(dir).replace(/^\d{4}-\d{2}-/, '').replace(/-/g, ' '));
  const I = lib(dir, a.opt.library);
  let tid = a.opt.theme || 'TH-01';
  if (!/^TH-\d{2,}$/.test(tid)) { console.log(`Ignored --theme ${tid}: a theme is an id such as TH-02; using TH-01.`); tid = 'TH-01'; }
  const theme = themeFrom(I.folder, tid);
  fs.mkdirSync(path.join(dir, 'slides'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'styles.css'), stylesCss(theme, fs.readFileSync(path.join(I.folder, 'host.css'), 'utf8')));
  fs.copyFileSync(path.join(I.folder, 'host-runtime.js'), path.join(dir, 'host-runtime.js'));
  if (theme.licence && fs.existsSync(path.join(I.folder, theme.licence))) fs.copyFileSync(path.join(I.folder, theme.licence), path.join(dir, path.basename(theme.licence)));
  fs.writeFileSync(path.join(dir, 'presentation.html'), `<title>${esc(a.opt.title)}</title>`);
  build(dir, true);
  console.log(`Made ${dir}: presentation.html (built), styles.css (look and spacing, theme ${theme.id} ${theme.name}), slides/ (empty). Title: "${a.opt.title}".`);
  if (plainName(a.pos[0])) console.log(`Folder: ${home.why}.`);
  console.log(`Library: ${I.folder}\nNext: ${ME} add "${dir}" FR-01 --headline "The answer as a sentence"`);
}

/* ---------------------------------------------------------------- check in a browser */
const CHECKER = `<script id="deck-check-run">
(function () {
  var out = [];
  function nm(el) { var s = el.closest('[data-spot]'); var t = (el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 50); return (s ? s.getAttribute('data-spot') : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '')) + (t ? ' "' + t + '"' : ''); }
  function measure(s) {
    var R = s.getBoundingClientRect(), k = R.width / 1280 || 1, seen = {};
    function rel(el) { var r = el.getBoundingClientRect(); return { l: (r.left - R.left) / k, t: (r.top - R.top) / k, r: (r.right - R.left) / k, b: (r.bottom - R.top) / k, w: r.width / k, h: r.height / k }; }
    function say(m) { if (!seen[m]) { seen[m] = 1; out.push({ slide: s.id, msg: m }); } }
    var foot = s.querySelector(':scope > .footnote'), limit = foot ? rel(foot).t - 2 : 650;
    if (foot && rel(foot).b > 690) say('footnote runs into the section bar (shorten it)');
    var content = s.querySelector(':scope > .content');
    if (content) {   /* any box, borders included, past the footnote's top or the right edge; the outermost one is named */
      var over = [];
      Array.prototype.forEach.call(content.querySelectorAll('*'), function (el) {
        if (el.closest('.chart') || el.closest('svg')) return;
        var r = rel(el); if (!r.w || !r.h) return;
        if (r.b > limit + 1 || r.r > 1280 - 20) over.push(el);
      });
      over.filter(function (el) { return over.indexOf(el.parentElement) === -1; }).slice(0, 3).forEach(function (el) {
        var r = rel(el); say((r.b > limit + 1 ? 'runs into the footnote or off the slide by ' + Math.round(r.b - limit) + 'px: ' : 'runs off the right edge: ') + nm(el));
      });
    }
    Array.prototype.forEach.call(s.querySelectorAll('[data-spot]'), function (el) {
      if (el.querySelector('.chart')) return;
      var cs = getComputedStyle(el);
      if ((el.scrollHeight > el.clientHeight + 3 && cs.overflowY !== 'visible') || el.scrollWidth > el.clientWidth + 3) say('text cut off: ' + nm(el));
    });
    var h = s.querySelector('[data-spot="headline"]');
    if (h) {
      var rg = document.createRange(); rg.selectNodeContents(h);
      var tops = Array.prototype.filter.call(rg.getClientRects(), function (r) { return r.width > 1; }).map(function (r) { return r.top / k; }).sort(function (a, b) { return a - b; });
      var lines = tops.length ? 1 : 0; for (var q = 1; q < tops.length; q++) if (tops[q] - tops[q - 1] > 12) lines++;
      if (lines > 2) say('headline over two lines');
    }
    Array.prototype.forEach.call(s.querySelectorAll('.chart[data-echart]'), function (box) {
      var b = rel(box), svg = box.querySelector('svg'), id = box.closest('[data-item]') ? box.closest('[data-item]').getAttribute('data-item') : 'chart';
      if (!svg && box.querySelector('canvas')) return;   /* drawn on a canvas (an old deck shown live): nothing to measure */
      if (!svg || svg.querySelectorAll('path,rect,text').length < 4) { say(id + ': chart not drawn' + (svg ? '' : ' (no drawing in its box: check its JSON and that its slide shows)')); return; }
      if (b.h < 150) say(id + ': chart squeezed to ' + Math.round(b.h) + 'px high');
      var texts = Array.prototype.filter.call(svg.querySelectorAll('text'), function (t) { return t.textContent.trim() && getComputedStyle(t).opacity !== '0'; }).map(function (t) { return { t: t.textContent.trim(), r: rel(t) }; });
      var cut = 0, over = 0;
      texts.forEach(function (x, i) {
        if (cut < 3 && (x.r.l < b.l - 3 || x.r.r > b.r + 3 || x.r.t < b.t - 3 || x.r.b > b.b + 3)) { cut++; say(id + ': chart text cut off at the edge: "' + x.t.slice(0, 40) + '"'); }
        if (/^-?\\d{5,}(\\.\\d+)?$/.test(x.t) || /\\d\\.\\d{3,}$/.test(x.t)) say(id + ': unformatted number on the chart: ' + x.t + ' (give a formatter)');
        for (var j = i + 1; j < texts.length && over < 3; j++) {
          var y = texts[j], w = Math.min(x.r.r, y.r.r) - Math.max(x.r.l, y.r.l), hh = Math.min(x.r.b, y.r.b) - Math.max(x.r.t, y.r.t);
          if (w > 2 && hh > 2 && w * hh > 0.3 * Math.min(x.r.w * x.r.h, y.r.w * y.r.h)) { over++; say(id + ': labels overlap: "' + x.t.slice(0, 30) + '" and "' + y.t.slice(0, 30) + '"'); }
        }
      });
    });
  }
  function run() {
    var slides = Reveal.getSlides(), i = 0;
    try { if (slides.length > 1) Reveal.slide(slides.length - 1); } catch (e) { /* see below */ }
    (function step() {
      if (i >= slides.length) { var pre = document.createElement('pre'); pre.id = 'deck-check'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre); return; }
      var s = slides[i++];
      try { Reveal.slide(i - 1); } catch (e) { /* moving only matters for decks that draw a chart when its slide shows */ }
      setTimeout(function () { try { measure(s); } catch (e) { out.push({ slide: s.id, msg: 'check failed: ' + e.message }); } step(); }, 350);
    })();
  }
  var t0 = Date.now(), wait = setInterval(function () {   /* decks from the old scripts draw a chart only when its slide shows */
    var drawn = document.querySelectorAll('.chart[data-echart] svg').length >= document.querySelectorAll('.chart[data-echart]').length;
    if (window.Reveal && Reveal.isReady && Reveal.isReady() && (drawn || Date.now() - t0 > 3000)) {
      clearInterval(wait);
      try { Reveal.configure({ hash: false, history: false }); } catch (e) { /* older reveal */ }
      setTimeout(run, 300);
    }
  }, 200);
})();
</script>`;
function findBrowser(given) {
  const b = [given, ...BROWSERS].filter(Boolean).find(p => fs.existsSync(p));
  if (!b) stop('no Edge or Chrome found. Add --browser <path to the browser>.');
  return b;
}
function cmdCheck(a) {
  const dir = deckOf(a.pos[0]);
  const deck = path.join(dir, 'presentation.html');
  let staticCount = 0;
  if (fs.existsSync(path.join(dir, 'slides'))) {
    const probs = build(dir, true);
    staticCount = probs.length;
    if (probs.length) console.log(`Static checks (deck.js build): ${probs.length} to fix:\n${probs.map(p => '  ' + p).join('\n')}\n`);
  } else if (!fs.existsSync(deck)) stop(`no presentation.html in ${dir}`);
  else {   // a deck from the old scripts: the same static checks, on the slides part of presentation.html
    const full = fs.readFileSync(deck, 'utf8'), end = full.indexOf('<!-- SLIDES:END -->'), probs = [];
    full.slice(0, end === -1 ? full.length : end).split('\n').forEach((l, i) => { if (/WORD/.test(l) && !/<!--/.test(l)) probs.push(`presentation.html:${i + 1} to reword: ${l.trim().slice(0, 100)}`); });
    for (const m of full.slice(0, end).matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) {
      try { checkChart(JSON.parse(m[1])).forEach(w => probs.push(`presentation.html:${lineAt(full, m.index)} ${w}`)); } catch (e) { probs.push(`presentation.html:${lineAt(full, m.index)} chart JSON is not valid: ${e.message}`); }
    }
    staticCount = probs.length;
    if (probs.length) console.log(`Static checks: ${probs.length} to fix:\n${probs.map(p => '  ' + p).join('\n')}\n`);
  }
  const html = fs.readFileSync(deck, 'utf8');
  if (!/<section\b/.test(html)) { console.log('No slides yet: add one, then check.'); return; }
  const base = pathToFileURL(dir + path.sep).href;
  const page = html.replace(/<head>/i, `<head>\n<base href="${base}">`).replace(/<\/body>/i, `${CHECKER}\n</body>`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'deck-check-'));
  const file = path.join(tmp, 'check.html');
  fs.writeFileSync(file, page);
  const n = (html.match(/<section\b/g) || []).length;
  const r = spawnSync(findBrowser(a.opt.browser), ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', `--user-data-dir=${path.join(tmp, 'p')}`,
    '--window-size=1280,720', `--virtual-time-budget=${4000 + n * 600}`, '--dump-dom', pathToFileURL(file).href + '?export'], { encoding: 'utf8', timeout: 120000, maxBuffer: 64 * 1024 * 1024 });
  try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (e) { /* the profile may still be locked */ }
  const m = (r.stdout || '').match(/<pre id="deck-check">([\s\S]*?)<\/pre>/);
  if (!m) stop('the browser check did not finish (no network for reveal.js and ECharts, or the deck has a script error). Open presentation.html to see.');
  const found = JSON.parse(unesc(m[1]));
  const files = fs.existsSync(path.join(dir, 'slides')) ? slideFiles(dir) : [];
  const fileOf = id => { const f = files.find(x => readSlide(dir, x).id === id); return f ? `slides/${f}` : `slide ${id}`; };
  if (!found.length) console.log(`Drawn and measured ${n} slides: nothing overflows, every chart drew, no chart text cut off or overlapping.`);
  else console.log(`Drawn and measured ${n} slides; ${found.length} to fix:\n${found.map(x => `  ${fileOf(x.slide)}: ${x.msg}`).join('\n')}`);
  console.log(`\nLook at it: node "${path.join(__dirname, 'screenshot.js')}" "${dir}"`);
  if (found.length || staticCount) process.exitCode = 1;   // findings: not a clean pass
}

/* ---------------------------------------------------------------- main */
function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  const a = parseArgs(rest);
  const run = { new: cmdNew, show: cmdShow, add: cmdAdd, animate: cmdAnimate, own: cmdOwn, list: cmdList, refill: cmdRefill, theme: cmdTheme, place: cmdPlace, check: cmdCheck, build: x => {
    const d = deckOf(x.pos[0]), p = path.join(d, 'presentation.html');
    if (x.opt.title && fs.existsSync(p)) fs.writeFileSync(p, fs.readFileSync(p, 'utf8').replace(/<title>[\s\S]*?<\/title>/, `<title>${esc(x.opt.title)}</title>`));   // a new title for the bottom bar
    build(d);
  } }[cmd];
  if (!run) { console.log(fs.readFileSync(__filename, 'utf8').match(/\/\*\*([\s\S]*?)\*\//)[1].replace(/^ \* ?/gm, '').trim()); process.exit(cmd ? 1 : 0); }
  run(a);
}
module.exports = { resolveDeck };
if (require.main === module) main();
