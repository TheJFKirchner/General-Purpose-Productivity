#!/usr/bin/env node
/*
 * Builds cosmo.html: the four pages and cosmo.css combined into one self-contained file.
 * The separate pages stay the source; run this again after changing any of them.
 *
 *   node build-single.mjs
 *
 * No dependencies. What it does:
 * - inlines cosmo.css once, and each page's own <style> scoped under its view (#home, #deliverables ...);
 * - takes each page's <main> as one view; ids inside a view get the view's name in front ("brain-bg-run"),
 *   and links, aria references, url(#...) and the page's own scripts are rewritten to match;
 * - links between pages become in-file links: index.html -> #home, brain.html#x -> #brain-x;
 * - one header and footer for all views; a small script shows one view at a time from the address hash,
 *   so the back button and pasted links work. Without scripts, and in print, all views show in order.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const OUT = 'cosmo.html';
const PAGES = [
  { key: 'home', file: 'index.html', label: 'Home' },
  { key: 'deliverables', file: 'deliverables.html', label: 'Deliverables' },
  { key: 'brain', file: 'brain.html', label: 'Brain' },
  { key: 'orchestration', file: 'orchestration.html', label: 'Orchestration' },
];

const read = f => readFileSync(join(DIR, f), 'utf8').replace(/\r\n/g, '\n');
const fail = msg => { console.error('STOP: ' + msg); process.exit(1); };
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/* ---------- 1. read each page ---------- */
for (const p of PAGES) {
  const html = read(p.file);
  const head = html.slice(0, html.indexOf('</head>'));
  const body = html.slice(html.indexOf('<body'));
  if (/<script[^>]*\ssrc=/i.test(html) || /<link[^>]*rel="stylesheet"[^>]*href="(?!cosmo\.css)/i.test(html)) fail(`${p.file} loads an outside file`);
  const main = body.match(/<main id="main">([\s\S]*?)<\/main>/);
  if (!main) fail(`${p.file} has no <main id="main">`);
  p.title = (head.match(/<title>([\s\S]*?)<\/title>/) || [, p.label + ' · Cosmo'])[1].trim();
  p.css = [...head.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  p.js = [...body.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  p.main = main[1];
  p.ids = [...new Set([...p.main.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]))];
  p.map = Object.fromEntries(p.ids.map(id => [id, `${p.key}-${id}`]));
}
const byFile = Object.fromEntries(PAGES.map(p => [p.file, p]));
const viewKeys = PAGES.map(p => p.key);
for (const p of PAGES) for (const id of Object.values(p.map)) if (viewKeys.includes(id)) fail(`id ${id} collides with a view name`);

/* ---------- 2. rewrite links and ids ---------- */
function rewriteHref(href, page) {
  if (/^(https?:|mailto:|data:|javascript:)/i.test(href)) return href;
  const [file, frag] = href.split('#');
  if (file === '') return frag && page.map[frag] ? '#' + page.map[frag] : href;      // same page
  const target = byFile[file];
  if (!target) return href;                                                         // not one of ours: leave
  if (frag) return target.map[frag] ? '#' + target.map[frag] : '#' + target.key;
  return '#' + target.key;
}
function rewriteMarkup(html, page) {
  const pre = id => page.map[id] || id;
  return html
    .replace(/\sid="([^"]+)"/g, (m, id) => ` id="${pre(id)}"`)
    .replace(/\s(for|aria-labelledby|aria-describedby|aria-controls|aria-owns|aria-activedescendant)="([^"]+)"/g,
      (m, a, v) => ` ${a}="${v.split(/\s+/).map(pre).join(' ')}"`)
    .replace(/url\(#([^)]+)\)/g, (m, id) => `url(#${pre(id)})`)
    .replace(/\s(href|xlink:href)="([^"]*)"/g, (m, a, v) => ` ${a}="${rewriteHref(v, page)}"`);
}
function rewriteScript(js, page) {
  let out = js;
  for (const id of page.ids) out = out.replace(new RegExp(`(['"])(#?)${esc(id)}\\1`, 'g'), (m, q, h) => `${q}${h}${page.map[id]}${q}`);
  return out;
}

/* ---------- 3. scope a page's CSS under its view ---------- */
function closeOf(css, open) {
  let depth = 0;
  for (let i = open; i < css.length; i++) { if (css[i] === '{') depth++; else if (css[i] === '}' && --depth === 0) return i; }
  fail('unbalanced braces in a page <style>');
}
function splitTop(sel) {
  const parts = []; let depth = 0, cur = '';
  for (const ch of sel) { if (ch === '(') depth++; if (ch === ')') depth--; if (ch === ',' && !depth) { parts.push(cur); cur = ''; } else cur += ch; }
  return parts.concat(cur).map(s => s.trim()).filter(Boolean);
}
function scopeCss(css, prefix) {
  css = css.replace(/\/\*[\s\S]*?\*\//g, '');
  let out = '', i = 0;
  while (i < css.length) {
    const ws = /^\s+/.exec(css.slice(i));
    if (ws) { out += ws[0]; i += ws[0].length; continue; }
    const open = css.indexOf('{', i);
    if (css[i] === '@') {
      const semi = css.indexOf(';', i);
      if (semi !== -1 && (open === -1 || semi < open)) { out += css.slice(i, semi + 1); i = semi + 1; continue; }
      const close = closeOf(css, open), head = css.slice(i, open).trim(), inner = css.slice(open + 1, close);
      out += /^@(media|supports|container|layer)\b/.test(head) ? `${head} {${scopeCss(inner, prefix)}}` : `${head} {${inner}}`;
      i = close + 1; continue;
    }
    if (open === -1) break;
    const close = closeOf(css, open);
    const sels = splitTop(css.slice(i, open)).map(s => /^(:root|html|body)\b/.test(s) ? s.replace(/^(:root|html|body)/, prefix) : `${prefix} ${s}`);
    out += `${sels.join(', ')} {${css.slice(open + 1, close)}}`;
    i = close + 1;
  }
  return out;
}

/* ---------- 4. shared header and footer (from index.html) ---------- */
const home = read('index.html');
let header = home.match(/<header class="top">[\s\S]*?<\/header>/)[0].replace(/\s*aria-current="page"/g, '');
let footer = home.match(/<footer class="foot">[\s\S]*?<\/footer>/)[0]
  .replace(/<p class="foot-note">[\s\S]*?<\/p>/, '<p class="foot-note">An overview for colleagues. All four pages in one file; it works offline.</p>');
const linkFix = s => s.replace(/\shref="([^"#]+\.html)"/g, (m, f) => byFile[f] ? ` href="#${byFile[f].key}"` : m);
header = linkFix(header); footer = linkFix(footer);
for (const p of PAGES) if (!header.includes(`href="#${p.key}"`)) fail(`header has no link to ${p.file}`);

/* ---------- 5. assemble ---------- */
const views = PAGES.map(p => `<section class="view" id="${p.key}" aria-label="${p.label}" data-title="${p.title.replace(/"/g, '&quot;')}">\n${rewriteMarkup(p.main, p).trim()}\n</section>`).join('\n\n');
const pageCss = PAGES.filter(p => p.css.trim()).map(p => `/* from ${p.file} */\n${scopeCss(p.css, '#' + p.key)}`).join('\n');
const pageJs = PAGES.flatMap(p => p.js.map(js => `/* from ${p.file} */\n${rewriteScript(js, p).trim()}`)).join('\n');

const shellCss = `
/* single file: one view at a time when scripts run; all views in order without scripts and in print */
html.js .view:not(.on) { display: none; }
html:not(.js) .view + .view { border-top: 6px solid var(--blue); }
html:not(.js) button { display: none; }   /* buttons need scripts */
[tabindex="-1"]:focus { outline: none; }
@media print {
  html.js .view { display: block !important; }
  .view + .view { break-before: page; border-top: 0; }
}`;

const router = `
(function () {
  var views = [].slice.call(document.querySelectorAll('main > .view'));
  var keys = views.map(function (v) { return v.id; });
  function resolve(hash) {
    var id = decodeURIComponent((hash || '').replace(/^#/, ''));
    if (!id) return { view: keys[0] };
    if (keys.indexOf(id) > -1) return { view: id };
    var el = document.getElementById(id), v = el && el.closest('.view');
    return v ? { view: v.id, el: el } : null;
  }
  function focus(el) { if (!el) return; if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1'); el.focus({ preventScroll: true }); }
  function current() { return document.querySelector('main > .view.on') || views[0]; }
  function show(hash, first) {
    var r = resolve(hash);
    if (!r) return;
    views.forEach(function (v) { v.classList.toggle('on', v.id === r.view); });
    [].forEach.call(document.querySelectorAll('.top .nav a'), function (a) {
      if (a.getAttribute('href') === '#' + r.view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    var v = current();
    document.title = v.getAttribute('data-title') || document.title;
    if (r.el) { r.el.scrollIntoView({ behavior: 'instant', block: 'start' }); if (!first) focus(r.el); }
    else { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); if (!first) focus(v.querySelector('h1') || v); }
  }
  window.addEventListener('hashchange', function () { show(location.hash, false); });
  var skip = document.querySelector('.skip');
  if (skip) skip.addEventListener('click', function (e) { e.preventDefault(); var v = current(); focus(v.querySelector('h1') || v); });
  var opened = [];
  window.addEventListener('beforeprint', function () { opened = [].filter.call(document.querySelectorAll('details:not([open])'), function (d) { d.open = true; return true; }); });
  window.addEventListener('afterprint', function () { opened.forEach(function (d) { d.open = false; }); opened = []; });
  show(location.hash, true);
})();`;

const out = `<!doctype html>
<!-- GENERATED by build-single.mjs from ${PAGES.map(p => p.file).join(', ')} and cosmo.css. Do not edit this file:
     edit those, then run: node build-single.mjs -->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${PAGES[0].title}</title>
<meta name="description" content="An overview of Cosmo in one file: what it is, deliverables, the brain and orchestration.">
<link rel="icon" href="data:,">
<script>document.documentElement.classList.add('js');</script>
<style>
${read('cosmo.css').trim()}
</style>
<style>${shellCss}
${pageCss}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

${header}

<main id="main">

${views}

</main>

${footer}
<script>
${pageJs}
</script>
<script>${router}
</script>
</body>
</html>
`;

writeFileSync(join(DIR, OUT), out);
const kb = (Buffer.byteLength(out) / 1024).toFixed(0);
console.log(`${OUT}: ${kb} KB, ${PAGES.length} views (${viewKeys.join(', ')}), ${PAGES.reduce((n, p) => n + p.js.length, 0)} page script(s).`);
