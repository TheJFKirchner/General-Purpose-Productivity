#!/usr/bin/env node

/**
 * Keeps every item's shared blocks in step, checks every item, and writes index.md, index/<type>.md,
 * index.html and host.css. No dependencies. Usage: node build-index.js
 *
 * Shared blocks, rewritten from one source each: the tokens (from the default theme item, or a
 * theme item's own tokens), the deck stylesheet in slides (from the presentation skill's
 * base-styles.css), the kit and chart styles and the item engine (from save-item.js and host-runtime.js).
 *
 * Fails on: a missing or duplicate id or name, an id in the wrong scheme or a retired one, a missing
 * purpose, anything loaded from outside the file except the ECharts CDN, and a colour or font
 * written outside the tokens (exceptions: `transparent`, `currentColor`, `font: inherit`).
 * Charts, tables and hero cards fail without a data note whose slots are all marked in the block; a chart
 * block holding anything but its options, key and basis line, or printing over 6 KB from item.js; a slide
 * without its spots (every chart and piece of text marked data-spot). Items saved by the librarian (all but original-samples.txt) also fail
 * on a date, on more than 6 data points, and on any word denylist.json recorded from their source. Not checked for colours: the tokens block, a theme's JSON block,
 * an embedded SOURCE block (older saved items had one) and HTML comments. No other exceptions.
 */

const fs = require('fs');
const path = require('path');
const S = require('./save-item.js');
const I = require('./item.js');

const problems = [];
const say = (it, msg) => problems.push(`${it.rel}: ${msg}`);

/* ---------- sync the shared blocks ---------- */
const def = S.themeOf(S.DEFAULT_THEME);
const css = S.deckCss(def);
let synced = 0;
S.items().forEach(it => {
  let t = it.text;
  const own = it.h.type === 'theme' ? JSON.parse((t.match(/<script type="application\/json" id="theme">([\s\S]*?)<\/script>/) || [, '{}'])[1]) : def;
  if (own.css) t = t.replace(/<style id="tokens">[\s\S]*?<\/style>/, () => S.tokensBlock(own));
  t = t.replace(/<script id="item-engine">[\s\S]*?<\/script>/, () => `<script id="item-engine">\n${S.ENGINE}\n</script>`);
  if (it.h.type === 'slide') t = t.replace(/<style id="deck-css">[\s\S]*?<\/style>/, () => `<style id="deck-css">\n${css}\n</style>`);
  t = t.replace(/<style id="kit-css">[\s\S]*?<\/style>/, () => `<style id="kit-css">\n${S.KIT_CSS}\n</style>`);
  if (it.h.type === 'chart') {   // the basis line and key styles every chart shares
    const cc = `<style id="chart-css">\n${S.CHART_CSS('.fit')}\n</style>`;
    t = /<style id="chart-css">/.test(t) ? t.replace(/<style id="chart-css">[\s\S]*?<\/style>/, () => cc) : t.replace('<style id="item-css">', () => `${cc}\n<style id="item-css">`);
  }
  if (t !== it.text) { fs.writeFileSync(it.file, t); synced++; }
});

/* ---------- check ---------- */
const all = S.items();
const retired = fs.existsSync(path.join(S.LIB, 'retired-ids.txt')) ? fs.readFileSync(path.join(S.LIB, 'retired-ids.txt'), 'utf8').split(/\s+/).filter(Boolean) : [];
const seen = {};
const names = {};
const list = f => (fs.existsSync(path.join(S.LIB, f)) ? fs.readFileSync(path.join(S.LIB, f), 'utf8').split('\n').filter(l => !l.startsWith('#')).join(' ').split(/\s+/).filter(Boolean) : []);
const originals = list('original-samples.txt');
const deny = fs.existsSync(path.join(S.LIB, 'denylist.json')) ? JSON.parse(fs.readFileSync(path.join(S.LIB, 'denylist.json'), 'utf8')) : {};
const NAMED = /(?:color|background|fill|stroke|border[a-z-]*)\s*["']?\s*:\s*["']?(white|black|red|green|blue|gr[ae]y|navy|orange|teal|silver|yellow|purple)\b/i;
all.forEach(it => {
  const h = it.h;
  if (!h.id) return say(it, 'no ITEM header with an id');
  if (!/^[A-Z]{2}-\d{2,}$/.test(h.id)) say(it, `id "${h.id}" is not two letters, a hyphen and two digits`);
  if (seen[h.id]) say(it, `id ${h.id} also used by ${seen[h.id]}`);
  seen[h.id] = it.rel;
  if (retired.includes(h.id)) say(it, `id ${h.id} is retired; ids are never reused`);
  if (!S.TYPES[h.type]) say(it, `type "${h.type}" is not one of ${Object.keys(S.TYPES).join(', ')}`);
  else if (it.rel.split('/')[0] !== S.TYPES[h.type]) say(it, `a ${h.type} belongs in ${S.TYPES[h.type]}/`);
  const prefix = h.id.split('-')[0];
  if (h.type === 'slide' ? !S.GROUPS.includes(prefix) : S.PREFIX[h.type] !== prefix) say(it, `id prefix ${prefix} does not fit type ${h.type}`);
  if (!path.basename(it.file).startsWith(h.id + '-')) say(it, 'file name must start with the id');
  if (!h.name) say(it, 'no name');
  else if (names[h.name]) say(it, `name "${h.name}" also used by ${names[h.name]}`);
  names[h.name] = it.rel;
  if (!h.purpose || /^WRITE/i.test(h.purpose)) say(it, 'no purpose sentence');
  if (!h.from) say(it, 'no "from" (the skill it came from)');
  if (h.type === 'slide' && !new RegExp(`<section id="${h.name}" data-component="${h.id}"`).test(it.text)) say(it, 'the slide\'s section needs id="<name>" data-component="<id>"');
  // what a project copies: data note and slots (charts, tables, hero cards), a bare chart block, slide spots (AUTHORING.md)
  const block = I.blockOf(it.text);
  if (/^(chart|table|hero card)$/.test(h.type)) I.slotProblems(h, block).forEach(p => say(it, p));
  if (h.type === 'chart') {
    I.chartBlockProblems(block).forEach(p => say(it, p));
    const size = Buffer.byteLength(I.printed(it));
    if (size > 6144) say(it, `node item.js prints ${(size / 1024).toFixed(1)} KB for it; a chart stays under 6 KB`);
  }
  if (h.type === 'slide') I.slideProblems(block).forEach(p => say(it, p));
  if (h.recipe !== undefined && !h.data) say(it, 'a recipe without a data note');
  // an embedded font: only in a theme item, only @font-face rules with woff2 data: URIs, its licence file named and present.
  // That block is the one place a data: URI and a font name are allowed; it is checked here, then left out of the checks below.
  let text = it.text;
  const fb = text.match(/<style id="theme-fonts">([\s\S]*?)<\/style>/);
  if (fb) {
    if (h.type !== 'theme') say(it, 'an embedded font (style#theme-fonts) belongs only in a theme item');
    const face = /@font-face\s*\{\s*font-family:\s*"[^"]+";(?:\s*[a-z-]+:\s*[^;{}()]+;)*\s*src:\s*url\(data:font\/woff2;base64,[A-Za-z0-9+/]+=*\)\s*format\("woff2"\);(?:\s*[a-z-]+:\s*[^;{}()]+;)*\s*\}/g;
    if (fb[1].replace(/\/\*[\s\S]*?\*\//g, '').replace(face, '').trim()) say(it, 'style#theme-fonts may hold only @font-face rules with woff2 data: URIs');
    const lic = (fb[1].match(/themes\/([\w.-]+\.txt)/) || [])[1];
    if (!lic || !fs.existsSync(path.join(S.LIB, 'themes', lic))) say(it, 'an embedded font needs its licence file named in its block (themes/<file>.txt) and present');
    text = text.replace(fb[0], '');
  }
  // nothing from outside the file but ECharts
  const refs = [...text.matchAll(/\b(?:src|href)\s*=\s*"([^"]*)"|(?<![A-Za-z])url\(([^)]*)\)|@import|<link\b/g)];   // url( in CSS, not createObjectURL(
  refs.forEach(m => { const v = m[1] || m[2] || m[0]; if (v !== S.ECHARTS && !/^#/.test(v)) say(it, `loads "${v}" from outside the item; only the ECharts CDN is allowed`); });
  // colours and fonts only through tokens
  const body = text
    .replace(/<style id="tokens">[\s\S]*?<\/style>/, '')
    .replace(/<script type="application\/json" id="theme">[\s\S]*?<\/script>/, '')
    .replace(/<!-- SOURCE[\s\S]*?<!-- SOURCE END -->/, '')
    .replace(/<!--[\s\S]*?-->/g, '');
  const hex = body.match(/(?<![&\w])#[0-9a-fA-F]{3,8}\b/);   // not an HTML entity such as &#9650;
  if (hex) say(it, `hard-coded colour ${hex[0]}; use a token such as var(--blue)`);
  if (/\b(?:rgba?|hsla?)\(/.test(body)) say(it, 'hard-coded rgb()/hsl() colour; use a token');
  const named = body.match(NAMED);
  if (named) say(it, `hard-coded colour "${named[1]}"; use a token`);
  const font = body.match(/font-family\s*:\s*([^;}"]*)/i) || body.match(/"fontFamily"\s*:\s*"([^"]*)"/);
  if (font && !/var\(--/.test(font[1])) say(it, `hard-coded font "${font[1].trim()}"; use var(--body-font) or var(--heading-font)`);
  const short = [...body.matchAll(/[{;\s]font\s*:\s*([^;}]*)/g)].find(m => !/var\(--[a-z-]*font\)/.test(m[1]) && m[1].trim() !== 'inherit');   // font: inherit is allowed
  if (short) say(it, `font shorthand without a font token: "${short[1].trim()}"`);

  // Saved items (not the hand-made originals): no dates, at most 6 points, no word from the project copied
  if (originals.includes(h.id)) return;
  const all = text.replace(/<style id="(tokens|deck-css|kit-css)">[\s\S]*?<\/style>/g, '').replace(/<script id="item-engine">[\s\S]*?<\/script>/, '').replace(S.ECHARTS, '');
  const date = all.match(/\b(?:19|20)\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+'?\d{2}\b/i);
  if (date) say(it, `date "${date[0]}": a saved item carries no dates; use plain month names or "Group A"`);
  for (const m of it.text.matchAll(/<script type="application\/json">([\s\S]*?)<\/script>/g)) {
    let o; try { o = JSON.parse(m[1]); } catch (e) { say(it, 'chart JSON does not parse'); continue; }
    const cats = [].concat(o.xAxis || [], o.yAxis || []).filter(a => a && Array.isArray(a.data)).map(a => a.data.length);
    const pts = [].concat(o.series || []).filter(s => s.type !== 'heatmap').map(s => (s.data || []).length);
    const most = Math.max(0, ...cats, ...pts);
    if (most > 6) say(it, `${most} points; sample data is 4 to 6 points`);
  }
  const words = deny[h.id] || [];
  if (words.length) {
    const toks = new Set();
    for (const m of all.matchAll(/(["'`])((?:(?!\1)[^\\\n]){2,40})\1/g)) toks.add(m[2].trim());
    const plain = all.replace(/<[^>]+>/g, ' ').match(/[A-Za-z][\w-]*/g) || [];
    plain.forEach((w, i) => { toks.add(w); toks.add(`${w} ${plain[i + 1] || ''}`); toks.add(`${w} ${plain[i + 1] || ''} ${plain[i + 2] || ''}`); });
    const hit = [...toks].find(t => words.includes(S.hash(t)));
    if (hit) say(it, `"${hit}" comes from the project it was copied from; replace it with neutral wording`);
  }
});

/* ---------- index.md ---------- */
const order = Object.keys(S.TYPES);
const rank = id => { const g = S.GROUPS.indexOf(id.split('-')[0]); return (g === -1 ? 99 : g) * 1000 + Number(id.split('-')[1]); };
const byType = t => all.filter(i => i.h.type === t).sort((a, b) => rank(a.h.id) - rank(b.h.id) || a.h.id.localeCompare(b.h.id));
/* index.md holds every type; index/<type folder>.md one type each, so a reader can load only the charts. */
const line = i => `- ${i.h.id} | ${i.h.type} | ${i.h.name} | ${i.h.purpose}${i.h.data ? ` | data: ${i.h.data}` : ''}`;
const section = t => {
  const list = byType(t), out = [`## ${t.charAt(0).toUpperCase() + t.slice(1)}s (\`${S.TYPES[t]}/\`)`, ''];
  if (!list.length) out.push('None yet. Saved by the design-librarian agent.');
  else list.forEach(i => out.push(line(i)));
  return out.concat('');
};
const md = ['# Design library index', '',
  'One line per item: id, type, name, purpose and, for charts, tables and hero cards, the data it needs. An item is the file `<type folder>/<id>-<name>.html`; open only the one you need, or print its block with `node item.js <id>`. One type alone: `index/<type folder>.md`.', ''];
order.forEach(t => md.push(...section(t)));
fs.writeFileSync(path.join(S.LIB, 'index.md'), md.join('\n'));
fs.mkdirSync(path.join(S.LIB, 'index'), { recursive: true });
order.forEach(t => fs.writeFileSync(path.join(S.LIB, 'index', `${S.TYPES[t]}.md`), [`# Design library: ${t}s`, '', 'id | type | name | purpose' + (/^(chart|table|hero card)$/.test(t) ? ' | data it needs (AUTHORING.md, "Adding an item to a project")' : ''), ''].concat(section(t).slice(2)).join('\n')));
/* what a project's page carries once to draw copied items (host-runtime.js is the other half) */
fs.writeFileSync(path.join(S.LIB, 'host.css'), S.HOST_CSS());

/* ---------- index.html ---------- */
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
/* A theme's embedded font is held once here (themes that share a font share one copy) and sent with its tokens. */
const FONTS = {};
const themes = byType('theme').map(i => {
  const f = S.fontsOf(i.h.id), key = f ? S.hash(f) : '';
  if (f) FONTS[key] = f;
  return { id: i.h.id, name: i.h.name, purpose: i.h.purpose, font: key,
    theme: JSON.parse(i.text.match(/<script type="application\/json" id="theme">([\s\S]*?)<\/script>/)[1]) };
});
const moves = i => i.h.type === 'animation' || /\bdata-animate\b/.test(i.text.replace(/<script id="item-engine">[\s\S]*?<\/script>/, ''));
const shown = order.flatMap(byType);
const cards = shown.map((i, n) => `<button type="button" class="card" data-type="${esc(i.h.type)}" data-i="${n}"${moves(i) ? ' data-moves' : ''} aria-label="Preview ${esc(i.h.id)} ${esc(i.h.name)}">
<span class="pv"><iframe loading="lazy" src="${esc(i.rel)}#grid" title="${esc(i.h.id)} preview" tabindex="-1" aria-hidden="true"></iframe></span>
<span class="name"><b>${esc(i.h.id)}</b> ${esc(i.h.name)}</span>
<span class="purpose">${esc(i.h.purpose)}</span>
<span class="from">${esc(i.h.type)} &#183; from ${esc(i.h.from || '?')}</span></button>`).join('\n');
const itemsJson = JSON.stringify(shown.map(i => ({ id: i.h.id, name: i.h.name, type: i.h.type, from: i.h.from, purpose: i.h.purpose, rel: i.rel, moves: moves(i) })));
fs.writeFileSync(path.join(S.LIB, 'index.html'), `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design library</title>
${S.tokensBlock(def)}
<style>
  body { margin: 0; font-family: var(--body-font); color: var(--ink); background: var(--wash); }
  body.locked { overflow: hidden; }
  header { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 22px; padding: 12px 24px; background: var(--paper); border-bottom: 1px solid var(--rule); }
  h1 { font: var(--heading-weight) 20px var(--heading-font); color: var(--navy); margin: 0 auto 0 0; }
  label { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: var(--muted); }
  select { font: 14px var(--body-font); color: var(--navy); background: var(--paper); border: 1.5px solid var(--navy); border-radius: var(--radius); padding: 6px 8px; min-height: 36px; }
  .count { font-size: 13px; color: var(--muted); }
  main { padding: 20px 24px 60px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 16px; }
  .card { display: block; width: 100%; text-align: left; font: inherit; color: inherit; padding: 0; cursor: pointer; background: var(--paper); border: 1px solid var(--rule); border-radius: var(--radius); }
  .card[hidden] { display: none; }
  .card:hover, .card:focus-visible { border-color: var(--blue); box-shadow: 3px 3px 0 var(--shadow); }
  .card:focus-visible { outline: 3px solid var(--orange); outline-offset: 2px; }
  .pv { position: relative; display: block; aspect-ratio: 16 / 9; border-bottom: 1px solid var(--rule); overflow: hidden; }
  .pv iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; pointer-events: none; }
  .name { display: block; padding: 10px 12px 2px; color: var(--navy); font-size: 14px; }
  .name b, .pop .id { color: var(--blue); margin-right: 4px; }
  .purpose { display: block; padding: 0 12px 6px; font-size: 12.5px; color: var(--muted); line-height: 1.4; }
  .from { display: block; padding: 0 12px 12px; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
  /* popup */
  .pop { position: fixed; inset: 0; z-index: 20; display: flex; align-items: center; justify-content: center; padding: 16px; background: color-mix(in srgb, var(--navy) 55%, transparent); }
  .pop[hidden] { display: none; }
  .box { width: min(1180px, 100%); max-height: 100%; overflow: auto; box-sizing: border-box; display: flex; flex-direction: column; gap: 10px; background: var(--paper); border: 1.5px solid var(--navy); border-radius: var(--radius); padding: 14px 16px 16px; }
  .bar { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px 14px; }
  .bar h2 { flex: 1 1 260px; margin: 0; font: var(--heading-weight) 18px var(--heading-font); color: var(--navy); }
  .bar .type { font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin-left: 6px; }
  .tools { display: flex; gap: 8px; align-items: center; }
  .tools button { font: 600 14px var(--body-font); min-width: 44px; min-height: 40px; padding: 6px 12px; cursor: pointer; color: var(--navy); background: var(--paper); border: 1.5px solid var(--navy); border-radius: var(--radius); }
  .tools button:hover { background: var(--tint); }
  .about { margin: 0; font-size: 14px; color: var(--muted); }
  .about a { color: var(--blue); margin-left: 8px; font-size: 13px; white-space: nowrap; }
  .stage { position: relative; aspect-ratio: 16 / 9; width: 100%; border: 1px solid var(--rule); }
  .stage iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
  @media (max-width: 640px) { header { padding: 10px 14px; } main { padding: 14px; } .pop { padding: 6px; } .box { padding: 10px; } .stage { aspect-ratio: 4 / 3; } }
</style></head><body>
<header>
<h1>Design library</h1>
<label>Theme <select id="theme" aria-label="Theme"></select></label>
<label>Show <select id="type" aria-label="Type of item"></select></label>
<span class="count" id="count" aria-live="polite"></span>
</header>
<main>
<div class="grid">
${cards}
</div>
</main>
<div class="pop" id="pop" hidden>
<div class="box" role="dialog" aria-modal="true" aria-labelledby="pop-title">
<div class="bar"><h2 id="pop-title"><span class="id" id="pop-id"></span><span id="pop-name"></span><span class="type" id="pop-type"></span></h2>
<div class="tools"><button type="button" id="prev" aria-label="Previous item">&#8592;</button><button type="button" id="next" aria-label="Next item">&#8594;</button><button type="button" id="close" aria-label="Close">Close</button></div></div>
<p class="about"><span id="pop-purpose"></span><a id="pop-open" href="#" target="_blank" rel="noopener">Open by itself</a></p>
<div class="stage"><iframe id="pop-frame" name="pop" title="Item preview"></iframe></div>
</div>
</div>
<script>
(function () {
  var THEMES = ${JSON.stringify(themes)};
  /* embedded theme fonts, once each; their licence is named inside each (themes/*.txt) */
  var FONTS = ${JSON.stringify(FONTS)};
  var ITEMS = ${itemsJson};
  var TYPES = ['all'].concat(${JSON.stringify(order)});
  function get(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* works without storage */ } }
  var current = get('design-library-theme', THEMES[0].id), type = get('design-library-type', 'all');
  var hash = (location.hash.match(/theme=([A-Z]{2}-[0-9]+)/) || [])[1]; if (hash) current = hash;
  var ht = (location.hash.match(/type=([a-z%0-9]+)/) || [])[1]; if (ht) type = decodeURIComponent(ht);
  if (!THEMES.some(function (t) { return t.id === current; })) current = THEMES[0].id;
  if (TYPES.indexOf(type) === -1) type = 'all';
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var pop = document.getElementById('pop'), frame = document.getElementById('pop-frame');
  function theme() { return THEMES.filter(function (t) { return t.id === current; })[0]; }
  function send(f, msg) { try { f.contentWindow.postMessage(msg, '*'); } catch (e) { /* not loaded yet */ } }
  /* the theme as sent to an item: its tokens and series, plus its embedded font faces when it has them */
  function full(t) { return t.font ? Object.assign({}, t.theme, { fonts: FONTS[t.font] }) : t.theme; }
  function sendTheme(f) { send(f, { theme: full(theme()) }); }
  function link(t) { return '#theme=' + encodeURIComponent(JSON.stringify(full(t))); }

  /* theme and type dropdowns */
  var ts = document.getElementById('theme'), ty = document.getElementById('type');
  THEMES.forEach(function (t) { var o = document.createElement('option'); o.value = t.id; o.textContent = t.id + ' ' + t.name; o.title = t.purpose; ts.appendChild(o); });
  TYPES.forEach(function (t) { var o = document.createElement('option'); o.value = t; o.textContent = t === 'all' ? 'All types' : t; ty.appendChild(o); });
  function applyTheme() {
    var t = theme(), r = document.documentElement;
    Object.keys(t.theme.css).forEach(function (k) { r.style.setProperty(k, t.theme.css[k]); });
    ts.value = t.id; ts.title = t.purpose;
    cards.forEach(function (c) { sendTheme(c.querySelector('iframe')); });
    var live = document.getElementById('theme-fonts-live');   /* the index itself takes the theme's font too */
    if (t.font) { if (!live) { live = document.createElement('style'); live.id = 'theme-fonts-live'; document.head.appendChild(live); } if (live.textContent !== FONTS[t.font]) live.textContent = FONTS[t.font]; }
    else if (live) live.parentNode.removeChild(live);
    if (!pop.hidden) { sendTheme(frame); var po = document.getElementById('pop-open'); po.href = po.href.split('#')[0] + link(t); }
  }
  function visible() { return cards.filter(function (c) { return !c.hidden; }); }
  function applyType() {
    cards.forEach(function (c) { c.hidden = !(type === 'all' || c.getAttribute('data-type') === type); });
    ty.value = type;
    var n = visible().length;
    document.getElementById('count').textContent = n + ' item' + (n === 1 ? '' : 's');
  }
  ts.addEventListener('change', function () { current = ts.value; put('design-library-theme', current); applyTheme(); });
  ty.addEventListener('change', function () { type = ty.value; put('design-library-type', type); applyType(); });
  cards.forEach(function (c) { c.querySelector('iframe').addEventListener('load', function () { sendTheme(this); }); });

  /* moving items replay when they scroll into view; never loop */
  if (window.IntersectionObserver) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) send(e.target, { replay: true }); }); }, { threshold: 0.6 });
    cards.forEach(function (c) { if (c.hasAttribute('data-moves')) io.observe(c.querySelector('iframe')); });
  }

  /* popup in the same window */
  var at = -1, opener = null;
  function show(card) {
    var it = ITEMS[+card.getAttribute('data-i')];
    at = visible().indexOf(card);
    document.getElementById('pop-id').textContent = it.id;
    document.getElementById('pop-name').textContent = it.name;
    document.getElementById('pop-type').textContent = it.type + ' \u00b7 from ' + (it.from || '?');
    document.getElementById('pop-purpose').textContent = it.purpose;
    document.getElementById('pop-open').href = it.rel + link(theme());   /* opens in the theme the popup shows, font included */
    frame.title = it.id + ' ' + it.name;
    frame.onload = function () { sendTheme(frame); if (it.moves) send(frame, { replay: true, explicit: true }); };   /* opening it is the request: plays even under reduced motion */
    frame.src = it.rel;
  }
  function open(card) {
    opener = card; show(card);
    pop.hidden = false; document.body.classList.add('locked');
    document.getElementById('close').focus();
  }
  function close() {
    pop.hidden = true; document.body.classList.remove('locked'); frame.removeAttribute('src');
    var v = visible(); if (v[at]) opener = v[at];
    if (opener) opener.focus();
  }
  function step(d) { var v = visible(); if (!v.length) return; at = (at + d + v.length) % v.length; show(v[at]); }
  cards.forEach(function (c) { c.addEventListener('click', function () { open(c); }); });
  document.getElementById('close').addEventListener('click', close);
  document.getElementById('prev').addEventListener('click', function () { step(-1); });
  document.getElementById('next').addEventListener('click', function () { step(1); });
  pop.addEventListener('click', function (e) { if (e.target === pop) close(); });
  /* Escape pressed while focus is inside the item: its engine passes the key up */
  window.addEventListener('message', function (e) { if (!pop.hidden && e.source === frame.contentWindow && e.data && e.data.escape) close(); });
  document.addEventListener('keydown', function (e) {
    if (pop.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && document.activeElement !== frame && (document.activeElement === document.body || document.activeElement.closest('.tools'))) {
      e.preventDefault(); step(e.key === 'ArrowLeft' ? -1 : 1);   /* the item keeps its own arrow keys: Tab into it to drive its steps */
    }
    else if (e.key === 'Tab') {   /* keep focus inside the popup */
      var f = Array.prototype.slice.call(pop.querySelectorAll('button, a[href], iframe'));
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  /* for links and checks: #open=<id> opens that item */
  var oh = (location.hash.match(/open=([A-Z]{2}-[0-9]+)/) || [])[1];
  applyTheme(); applyType();
  if (oh) { var k = ITEMS.map(function (x) { return x.id; }).indexOf(oh); if (k !== -1) { if (cards[k].hidden) { type = 'all'; applyType(); } open(cards[k]); } }
})();
</script>
</body></html>
`);

const counts = order.map(t => `${byType(t).length} ${t}`).join(', ');
console.log(`${all.length} items (${counts}).${synced ? ` Shared blocks brought in step in ${synced}.` : ''} Wrote index.md, index/, index.html and host.css.`);
if (problems.length) { console.log(`\n${problems.length} to fix:`); problems.forEach(p => console.log('  - ' + p)); process.exit(1); }
