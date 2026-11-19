#!/usr/bin/env node

/**
 * Keeps every item's shared blocks in step, checks every item, and writes index.md and index.html.
 * No dependencies. Usage: node build-index.js
 *
 * Shared blocks, rewritten from one source each: the tokens (from the default theme item, or a
 * theme item's own tokens), the deck stylesheet in slides (from the presentation skill's
 * base-styles.css) and the item engine (from save-item.js).
 *
 * Fails on: a missing or duplicate id or name, an id in the wrong scheme or a retired one, a missing
 * purpose, anything loaded from outside the file except the ECharts CDN, and a colour or font
 * written outside the tokens. Items saved by the librarian (all but original-samples.txt) also fail
 * on a date, on more than 6 data points, and on any word denylist.json recorded from their source. Not checked for colours: the tokens block, a theme's JSON block,
 * an embedded SOURCE block (the code to copy) and HTML comments. No other exceptions.
 */

const fs = require('fs');
const path = require('path');
const S = require('./save-item.js');

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
  // nothing from outside the file but ECharts
  const refs = [...it.text.matchAll(/\b(?:src|href)\s*=\s*"([^"]*)"|url\(([^)]*)\)|@import|<link\b/gi)];
  refs.forEach(m => { const v = m[1] || m[2] || m[0]; if (v !== S.ECHARTS && !/^#/.test(v)) say(it, `loads "${v}" from outside the item; only the ECharts CDN is allowed`); });
  // colours and fonts only through tokens
  const body = it.text
    .replace(/<style id="tokens">[\s\S]*?<\/style>/, '')
    .replace(/<script type="application\/json" id="theme">[\s\S]*?<\/script>/, '')
    .replace(/<!-- SOURCE[\s\S]*?<!-- SOURCE END -->/, '')
    .replace(/<!--[\s\S]*?-->/g, '');
  const hex = body.match(/#[0-9a-fA-F]{3,8}\b/);
  if (hex) say(it, `hard-coded colour ${hex[0]}; use a token such as var(--blue)`);
  if (/\b(?:rgba?|hsla?)\(/.test(body)) say(it, 'hard-coded rgb()/hsl() colour; use a token');
  const named = body.match(NAMED);
  if (named) say(it, `hard-coded colour "${named[1]}"; use a token`);
  const font = body.match(/font-family\s*:\s*([^;}"]*)/i) || body.match(/"fontFamily"\s*:\s*"([^"]*)"/);
  if (font && !/var\(--/.test(font[1])) say(it, `hard-coded font "${font[1].trim()}"; use var(--body-font) or var(--heading-font)`);
  const short = [...body.matchAll(/[{;\s]font\s*:\s*([^;}]*)/g)].find(m => !/var\(--[a-z-]*font\)/.test(m[1]));
  if (short) say(it, `font shorthand without a font token: "${short[1].trim()}"`);

  // Saved items (not the hand-made originals): no dates, at most 6 points, no word from the project copied
  if (originals.includes(h.id)) return;
  const all = it.text.replace(/<style id="(tokens|deck-css)">[\s\S]*?<\/style>/g, '').replace(/<script id="item-engine">[\s\S]*?<\/script>/, '').replace(S.ECHARTS, '');
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
const md = ['# Design library index', '',
  'One line per item: id, type, name, purpose. An item is the file `<type folder>/<id>-<name>.html`; open only the one you need.', ''];
order.forEach(t => {
  const list = byType(t);
  md.push(`## ${t.charAt(0).toUpperCase() + t.slice(1)}s (\`${S.TYPES[t]}/\`)`, '');
  if (!list.length) { md.push('None yet. Saved by the design-librarian agent.', ''); return; }
  list.forEach(i => md.push(`- ${i.h.id} | ${i.h.type} | ${i.h.name} | ${i.h.purpose}`));
  md.push('');
});
fs.writeFileSync(path.join(S.LIB, 'index.md'), md.join('\n'));

/* ---------- index.html ---------- */
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const themes = byType('theme').map(i => ({ id: i.h.id, name: i.h.name, purpose: i.h.purpose,
  theme: JSON.parse(i.text.match(/<script type="application\/json" id="theme">([\s\S]*?)<\/script>/)[1]) }));
const cards = order.flatMap(byType).map(i => `<div class="card" data-type="${esc(i.h.type)}">
<div class="pv"><iframe loading="lazy" src="${esc(i.rel)}" title="${esc(i.h.id)}" tabindex="-1"></iframe></div>
<a class="name" href="${esc(i.rel)}" target="_blank"><b>${esc(i.h.id)}</b> ${esc(i.h.name)}</a>
<p>${esc(i.h.purpose)}</p></div>`).join('\n');
fs.writeFileSync(path.join(S.LIB, 'index.html'), `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Design library</title>
${S.tokensBlock(def)}
<style>
  body { margin: 0; display: grid; grid-template-columns: 250px 1fr; min-height: 100vh; font-family: var(--body-font); color: var(--ink); background: var(--wash); }
  aside { position: sticky; top: 0; height: 100vh; overflow: auto; box-sizing: border-box; padding: 22px 18px; background: var(--paper); border-right: 1px solid var(--rule); }
  h1 { font: var(--heading-weight) 22px var(--heading-font); color: var(--navy); margin: 0 0 4px; }
  h2 { font: var(--heading-weight) 12px var(--body-font); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 22px 0 8px; }
  .now { font-size: 13px; color: var(--muted); margin: 0; }
  button { display: block; width: 100%; text-align: left; font: 14px var(--body-font); color: var(--ink); background: none; border: 1px solid transparent; border-left: 3px solid transparent; padding: 7px 10px; cursor: pointer; }
  button:hover { background: var(--wash); }
  button.on { border-left-color: var(--blue); background: var(--wash); color: var(--navy); font-weight: 600; }
  button small { display: block; color: var(--muted); font-weight: 400; font-size: 12px; margin-top: 2px; }
  main { padding: 22px 26px 60px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
  .card { background: var(--paper); border: 1px solid var(--rule); }
  .card:hover { border-color: var(--blue); }
  .pv { position: relative; aspect-ratio: 16 / 9; border-bottom: 1px solid var(--rule); overflow: hidden; }
  .pv iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; pointer-events: none; }
  .name { display: block; padding: 10px 12px 2px; text-decoration: none; color: var(--navy); font-size: 14px; }
  .name b { color: var(--blue); margin-right: 4px; }
  .card p { margin: 0; padding: 0 12px 12px; font-size: 12.5px; color: var(--muted); line-height: 1.4; }
  .count { color: var(--muted); font-size: 13px; margin: 0 0 14px; }
</style></head><body>
<aside>
<h1>Design library</h1>
<p class="now">Theme: <b id="now"></b></p>
<h2>Themes</h2>
<div id="themes"></div>
<h2>Show</h2>
<div id="types"></div>
</aside>
<main>
<p class="count" id="count"></p>
<div class="grid">
${cards}
</div>
</main>
<script>
(function () {
  var THEMES = ${JSON.stringify(themes)};
  var TYPES = ['all'].concat(${JSON.stringify(order)});
  function get(k, d) { try { return localStorage.getItem(k) || d; } catch (e) { return d; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* works without storage */ } }
  var current = get('design-library-theme', THEMES[0].id), type = get('design-library-type', 'all');
  var hash = (location.hash.match(/theme=([A-Z]{2}-[0-9]+)/) || [])[1]; if (hash) current = hash;
  if (!THEMES.some(function (t) { return t.id === current; })) current = THEMES[0].id;
  var frames = Array.prototype.slice.call(document.querySelectorAll('.pv iframe'));
  function theme() { return THEMES.filter(function (t) { return t.id === current; })[0]; }
  function send(f) { try { f.contentWindow.postMessage({ theme: theme().theme }, '*'); } catch (e) { /* not loaded yet */ } }
  function applyTheme() {
    var t = theme(), r = document.documentElement;
    Object.keys(t.theme.css).forEach(function (k) { r.style.setProperty(k, t.theme.css[k]); });
    document.getElementById('now').textContent = t.id + ' ' + t.name;
    frames.forEach(send);
    draw();
  }
  function applyType() {
    var n = 0;
    Array.prototype.forEach.call(document.querySelectorAll('.card'), function (c) {
      var show = type === 'all' || c.getAttribute('data-type') === type;
      c.style.display = show ? '' : 'none'; if (show) n++;
    });
    document.getElementById('count').textContent = n + ' item' + (n === 1 ? '' : 's') + (type === 'all' ? '' : ' of type ' + type);
    draw();
  }
  function button(label, sub, on, click) {
    var b = document.createElement('button'); b.className = on ? 'on' : '';
    b.textContent = label; if (sub) { var s = document.createElement('small'); s.textContent = sub; b.appendChild(s); }
    b.onclick = click; return b;
  }
  function draw() {
    var th = document.getElementById('themes'), ty = document.getElementById('types');
    th.innerHTML = ''; ty.innerHTML = '';
    THEMES.forEach(function (t) { th.appendChild(button(t.id + ' ' + t.name, t.purpose, t.id === current, function () { current = t.id; put('design-library-theme', current); applyTheme(); })); });
    TYPES.forEach(function (t) { ty.appendChild(button(t, '', t === type, function () { type = t; put('design-library-type', type); applyType(); })); });
  }
  frames.forEach(function (f) { f.addEventListener('load', function () { send(f); }); });
  applyTheme(); applyType();
})();
</script>
</body></html>
`);

const counts = order.map(t => `${byType(t).length} ${t}`).join(', ');
console.log(`${all.length} items (${counts}).${synced ? ` Shared blocks brought in step in ${synced}.` : ''} Wrote index.md and index.html.`);
if (problems.length) { console.log(`\n${problems.length} to fix:`); problems.forEach(p => console.log('  - ' + p)); process.exit(1); }
