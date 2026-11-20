#!/usr/bin/env node

/**
 * Hands one library item to a project, as a small copy. No dependencies. AUTHORING.md, "Adding an item to a project".
 *
 *   node item.js <id> [<id> ...] [--json]      an item's own block, data note, recipe, scoped CSS and script (never the engine)
 *   node item.js fill <id|--block file> --data <rows.json|rows.csv> --slot <name>=<column>[,<column>] ... [--json]
 *                                              the block with its sample data replaced by those columns
 *   node item.js swap <slide id> <chart id> [--spot chart-2] [--json]
 *                                              the slide with that chart in its chart spot
 *   node item.js shot <id> [--out <file.png>] [--theme <TH id>] [--browser <path>]
 *                                              a headless Chrome or Edge picture of the item, to look at
 *   node item.js theme <TH id> [--json] [--fonts]
 *                                              the theme's tokens as a :root block (--fonts adds its embedded font)
 *
 * Also a module: require('<library>/item.js') gives get, fill, fillChart, fillHtml, swap, parseNote, scopeCss, parse, serialize.
 */

const fs = require('fs');
const path = require('path');
const S = require('./save-item.js');

/* ---------- a small HTML tree: enough for item blocks ---------- */
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
const escText = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escAttr = s => escText(s).replace(/"/g, '&quot;');
function serialize(n) {
  if (typeof n === 'string') return n;
  if (n.comment) return n.comment;
  const inner = n.raw !== undefined ? n.raw : n.children.map(serialize).join('');
  if (n.tag === '#root') return inner;
  const open = `<${n.tag}${n.attrs.map(([k, v]) => (v === null ? ` ${k}` : ` ${k}="${v}"`)).join('')}>`;
  return VOID.test(n.tag) ? open : `${open}${inner}</${n.tag}>`;
}
function walk(n, fn, parent) { if (typeof n !== 'object' || n.comment) return; if (fn(n, parent) === false) return; (n.children || []).forEach(c => walk(c, fn, n)); }
const clone = n => JSON.parse(JSON.stringify(n));
const elements = n => (n.children || []).filter(c => typeof c === 'object' && !c.comment);
const textOf = n => (typeof n === 'string' ? n : n.comment ? '' : n.raw !== undefined ? '' : (n.children || []).map(textOf).join(''));

/* ---------- the data note: "data: label (text, one); value (number, one or more)" ---------- */
const SLOT = /^([a-z][a-z0-9-]*) \((text|number|figure), (one|one or more|optional|any)\)$/;
function parseNote(line) {
  if (!line) return null;
  const slots = line.split(';').map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(SLOT); return m ? { name: m[1], kind: m[2], count: m[3] } : { bad: s }; });
  return slots;
}

/* ---------- items ---------- */
const all = () => S.items();
function get(id) {
  const it = all().find(i => i.h.id === id);
  if (!it) throw new Error(`no item ${id}`);
  return it;
}
const blockOf = text => { const a = text.indexOf('<!-- ITEM:START -->'), b = text.indexOf('<!-- ITEM:END -->'); return a === -1 || b === -1 ? '' : text.slice(a + 19, b).trim(); };
const compactJson = html => html.replace(/(<script type="application\/json"[^>]*>)([\s\S]*?)(<\/script>)/g, (m, a, j, b) => { try { return a + JSON.stringify(JSON.parse(j)) + b; } catch (e) { return m; } });
/* Every selector of an item's own CSS, prefixed with [data-item="<id>"], so two items never share a class by accident. */
function scopeCss(css, id) {
  const pre = `[data-item="${id}"]`;
  css = css.replace(/\/\*[\s\S]*?\*\//g, '');
  // keyframe names are global: each takes the item id, so two items never share one
  [...new Set([...css.matchAll(/@keyframes\s+([\w-]+)/g)].map(m => m[1]))].filter(k => !k.startsWith(id)).forEach(k => {
    css = css.replace(new RegExp(`@keyframes\\s+${k}\\b`, 'g'), `@keyframes ${id}-${k}`)
      .replace(new RegExp(`(animation(?:-name)?\\s*:[^;}]*?)\\b${k}\\b`, 'g'), `$1${id}-${k}`);
  });
  let out = '', i = 0;
  while (i < css.length) {
    const open = css.indexOf('{', i);
    if (open === -1) break;
    const sel = css.slice(i, open).trim();
    let depth = 1, j = open + 1;
    while (j < css.length && depth) { if (css[j] === '{') depth++; else if (css[j] === '}') depth--; j++; }
    const body = css.slice(open + 1, j - 1);
    if (/^@(media|supports)/.test(sel)) out += `${sel} {\n${scopeCss(body, id)}}\n`;
    else if (/^@/.test(sel)) out += `${sel} {${body}}\n`;
    else out += sel.split(/,(?![^(]*\))/).map(s => s.trim()).map(s => (/^(html)?\.play\b/.test(s) ? s.replace(/^(html)?\.play/, `${pre}.play`)   // an animation plays when its wrapper has .play
      : /^(html|body|:root)\b/.test(s) ? s.replace(/^(\S+)/, `$1 ${pre}`) : `${pre} ${s}`)).join(', ') + ` {${body}}\n`;
    i = j;
  }
  return out.trim();
}
/* What a project copies: the block in its wrapper, the data note and recipe, the item's own CSS (scoped) and script. */
function copyOf(it) {
  const h = it.h, id = h.id;
  const css = ((it.text.match(/<style id="item-css">([\s\S]*?)<\/style>/) || [])[1] || '').trim();
  const js = ((it.text.match(/<script id="item-js">([\s\S]*?)<\/script>/) || [])[1] || '').trim();
  const block = compactJson(blockOf(it.text));
  const out = { id, type: h.type, name: h.name, purpose: h.purpose, data: parseNote(h.data) || [], dataLine: h.data || '', recipe: h.recipe || '', css: css ? scopeCss(css, id) : '', js };
  if (h.type === 'animation') {   // what it moves and where it fits; its script runs once per copy, inside that copy (host-motion.js)
    out.attaches = h.attaches || ''; out.fits = h.fits || '';
    if (js) out.js = `ItemMotion.attach('${id}', function (document, window, ItemEngine, addEventListener) {\n${js}\n});`;
  }
  if (h.type === 'slide') { out.html = block; out.spots = spotsOf(block); }
  else if (h.type === 'theme') { out.html = ''; }
  else out.html = `<div data-item="${id}">\n${block}\n</div>`;
  return out;
}
const spotsOf = html => { const s = []; walk(parse(html), n => { const v = attr(n, 'data-spot'); if (v) s.push(v); }); return s; };

/* ---------- fill: sample data out, real columns in ---------- */
const isEmpty = v => v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
const num = v => (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v.trim()) ? Number(v) : v);
function column(rows, c) { const v = rows.map(r => (isEmpty(r[c]) ? null : num(r[c]))); while (v.length && v[v.length - 1] === null) v.pop(); return v; }
/* a figure: the first value of the column, or the text given when no such column exists */
const figure = (rows, c) => (rows.length && c in rows[0] ? column(rows, c).find(v => v !== null) : num(c));
/* keep a sample entry's own style by position, drop its label text (it held a sample value) */
function restyle(old, v) {
  if (!old || typeof old !== 'object' || Array.isArray(old) || !('value' in old)) return v;
  const o = clone(old); o.value = v;
  if (o.label) { delete o.label.formatter; if (!Object.keys(o.label).length) delete o.label; }
  return o;
}
function dropColour(o) { ['itemStyle', 'lineStyle', 'areaStyle', 'endLabel', 'label'].forEach(k => { if (o[k] && typeof o[k] === 'object') { delete o[k].color; delete o[k].borderColor; } }); }
/* All objects marked "slot" in a chart option, with their parent array and index. */
function marks(o) {
  const out = [];
  const go = (x, parent, key) => {
    if (Array.isArray(x)) return x.forEach((v, i) => go(v, x, i));
    if (!x || typeof x !== 'object') return;
    if (typeof x.slot === 'string') out.push({ obj: x, parent, key });
    Object.keys(x).forEach(k => go(x[k], x, k));
  };
  go(o, null, null);
  return out;
}
const slotNames = spec => spec.split(':')[0].split(',').map(s => s.trim().replace(/^=/, ''));   // "=value": follows the value slot's first column
/* map: { slot: [columns] }. A slot given no column: its marked series or data entries are removed. */
function fillChart(o, rows, map, warn = []) {
  const drop = (m, name) => { if (m.obj.type) warn.push(`series "${m.obj.name || m.obj.type}" (slot ${name}) left out: no column for it`); m.parent.splice(m.parent.indexOf(m.obj), 1); };
  const names = [...new Set(marks(o).flatMap(m => slotNames(m.obj.slot)))];
  names.forEach(name => {
    const ms = marks(o).filter(m => slotNames(m.obj.slot).includes(name));
    const cols = map[name] || [];
    const removable = m => Array.isArray(m.parent) && !/^(category|value|time|log)$/.test(m.obj.type || '');   // series and data entries, never an axis
    if (ms.some(m => m.obj.slot.includes(':'))) {   // "target:yAxis": one property takes a figure
      ms.forEach(m => { const prop = m.obj.slot.split(':')[1]; if (cols.length) m.obj[prop] = figure(rows, cols[0]); else if (removable(m)) m.parent.splice(m.parent.indexOf(m.obj), 1); });
      return;
    }
    const tuple = ms.filter(m => slotNames(m.obj.slot).length > 1);
    if (tuple.length) {                              // "x,y": rows of [x, y], rows with an empty cell left out
      tuple.forEach(m => {
        const parts = slotNames(m.obj.slot);
        if (m.done) return;
        if (parts.some(p => !(map[p] || []).length)) { if (removable(m)) drop(m, name); m.done = true; return; }
        const old = m.obj.data || [];
        m.obj.data = rows.map(r => parts.map(p => (isEmpty(r[map[p][0]]) ? null : num(r[map[p][0]])))).filter(t => t.every(v => v !== null)).map((t, i) => restyle(old[i], t));
        m.done = true;
      });
      if (tuple.length === ms.length) return;
    }
    // an axis (panels share one) takes the slot's first column, every marked axis alike; series follow the order rule below
    const isAxis = m => /^(category|value|time|log)$/.test(m.obj.type || '');
    ms.filter(m => slotNames(m.obj.slot).length === 1 && isAxis(m)).forEach(m => {
      if (!cols.length) return;
      const c = cols[0];
      if (m.obj.type === 'category') m.obj.data = [...new Set(column(rows, c).filter(v => v !== null).map(String))];
      else m.obj.data = column(rows, c);
    });
    // a follower ("slot": "=value", a lollipop's dot) takes the slot's first column too, and never counts as one of its series
    ms.filter(m => /^=/.test(m.obj.slot)).forEach(m => {
      if (!cols.length) { if (removable(m)) drop(m, name); return; }
      const old = m.obj.data || [];
      m.obj.data = column(rows, cols[0]).map((v, k) => restyle(old[k], v));
    });
    const plain = ms.filter(m => slotNames(m.obj.slot).length === 1 && !isAxis(m) && !/^=/.test(m.obj.slot));
    if (!plain.length) return;
    if (!cols.length) { plain.slice().reverse().forEach(m => { if (removable(m)) drop(m, name); }); return; }
    cols.forEach((c, i) => {
      let m = plain[i];
      if (!m) {                                      // more columns than marks: repeat the last mark
        const last = plain[plain.length - 1], copy = clone(last.obj);
        dropColour(copy);
        last.parent.splice(last.parent.indexOf(last.obj) + (i - plain.length) + 1, 0, copy);
        m = { obj: copy, parent: last.parent };
      }
      const o2 = m.obj;
      if (o2.type === 'category') { o2.data = [...new Set(column(rows, c).filter(v => v !== null).map(String))]; return; }
      const old = o2.data || [];
      o2.data = column(rows, c).map((v, k) => restyle(old[k], v));
      if (o2.type && o2.type !== 'value') o2.name = c;
    });
    plain.slice(cols.length).reverse().forEach(m => { if (removable(m)) drop(m, name); });   // two series on one column: name it twice (value=v,v)
  });
  // a shown value axis drops the fixed range the sample set, so it fits the real values (hidden layout axes keep theirs)
  if (names.length) [].concat(o.xAxis || [], o.yAxis || []).forEach(a => { if (a && a.type === 'value' && a.show !== false) { delete a.min; delete a.max; delete a.interval; } });
  return o;
}
/* HTML: data-rows repeats one child per row (the one marked data-template, else the first); data-slot="name" sets
   text, "name@class" a state class, "name@aria-label" or "@title" that attribute, any other "name@prop" an inline
   style (a bare number gets %). A slot given a column but an empty value empties the text. */
const STATES = /^(good|bad|neutral|over|under|up|down|dn)$/;
function applySlot(n, row, map, inHead, rows) {
  const spec = attr(n, 'data-slot');
  spec.split(/\s+/).forEach(t => {
    const [name, prop] = t.split('@'), c = (map[name] || [])[0];
    if (c === undefined) { if (!prop && !row && !inHead) n.children = []; return; }   // a figure given nothing is emptied
    let v = inHead ? c : row ? row[c] : figure(rows, c);
    if (v === undefined || v === null) v = '';
    if (!prop) n.children = [escText(v)];
    else if (prop === 'class') { const cls = (attr(n, 'class') || '').split(/\s+/).filter(x => x && !STATES.test(x)); if (!isEmpty(v)) cls.push(String(v)); setAttr(n, 'class', cls.join(' ')); }
    else if (/^(aria-|title$|data-(?!slot|rows|template))/.test(prop)) setAttr(n, prop, escAttr(v));   // data-tick-up, data-v ...
    else { const unitless = /^(flex-grow|flex-shrink|opacity|order|z-index)$/.test(prop); const st = (attr(n, 'style') || '').split(';').map(s => s.trim()).filter(s => s && !s.startsWith(prop + ':')); if (!isEmpty(v)) st.push(`${prop}: ${/^-?\d+(\.\d+)?$/.test(String(v)) && !unitless ? v + '%' : escAttr(v)}`); setAttr(n, 'style', st.length ? st.join('; ') + ';' : null); }
  });
}
/* A th or td whose slot has several columns repeats once per column; the same slot's further cells in that row go
   (a sample row shows several, the copy keeps the first). In a row or header, a text slot given no column: the element
   goes (a column leaves the table); elsewhere it stays, emptied (keep). */
function expandColumns(parent, map, keep) {
  const done = new Set();
  parent.children = parent.children.flatMap(c => {
    if (typeof c !== 'object' || c.comment || !attr(c, 'data-slot')) return [c];
    const t = (attr(c, 'data-slot').split(/\s+/).find(x => !x.includes('@')) || '').split('=')[0], cols = map[t] || [];
    if (!t) return [c];
    if (done.has(t)) return [];
    done.add(t);
    if (!cols.length) return keep ? [c] : [];
    if (cols.length === 1) return [c];
    return cols.map((col, i) => { const k = clone(c); setAttr(k, 'data-slot', attr(c, 'data-slot').replace(new RegExp(`(^|\\s)${t}(@|\\s|$)`, 'g'), `$1${t}=${i}$2`)); return k; });
  });
  parent.children.forEach(c => { if (typeof c === 'object' && !c.comment && !/^(script|style)$/.test(c.tag)) expandColumns(c, map, keep && attr(c, 'data-rows') === null && c.tag !== 'thead'); });
}
function fillHtml(html, rows, map) {
  const tree = parse(html);
  // the template row first, so the column rule above reads the row the copies are made from
  walk(tree, n => { if (attr(n, 'data-rows') !== null) { const kids = elements(n), tpl = kids.find(k => attr(k, 'data-template') !== null) || kids[0]; if (tpl) n.children = ['\n', tpl, '\n']; } });
  expandColumns(tree, map, true);
  // a repeated cell carries "slot=<n>": read that slot's nth column
  const at = (n, inHead, row) => {
    const spec = attr(n, 'data-slot'), m = {};
    spec.split(/\s+/).forEach(t => { const [nm] = t.split('@'); const [s, k] = nm.split('='); m[s] = k !== undefined ? [(map[s] || [])[+k]] : map[s]; });
    const plain = clone(n); setAttr(plain, 'data-slot', spec.replace(/=[^@\s]+/g, ''));
    applySlot(plain, row, m, inHead, rows);
    Object.assign(n, plain);
  };
  walk(tree, (n, parent) => {
    if (attr(n, 'data-rows') !== null) {
      const tpl = elements(n)[0];
      if (!tpl) return false;
      const made = rows.map((r, i) => {
        const k = clone(tpl);
        if (i) setAttr(k, 'data-template', null);
        setAttr(k, 'class', (attr(k, 'class') || '').split(/\s+/).filter(x => x && x !== 'on').join(' ') || null);   // the lead row is chosen by hand
        walk(k, x => { if (attr(x, 'data-slot')) at(x, false, r); });
        return k;
      });
      n.children = ['\n'].concat(...made.map(k => [k, '\n']));
      return false;
    }
    if (attr(n, 'data-slot')) at(n, !!(parent && isHead(tree, n)), null);
  });
  return serialize(tree);
}
function isHead(tree, node) { let found = false; walk(tree, n => { if (n.tag === 'thead') walk(n, x => { if (x === node) found = true; }); }); return found; }
/* A block: charts get their JSON filled, everything else its HTML slots. */
function fill(html, rows, map, warn = []) {   // warn collects the series left out for want of a column
  html = html.replace(/(<script type="application\/json"[^>]*>)([\s\S]*?)(<\/script>)/g, (m, a, j, b) => a + JSON.stringify(fillChart(JSON.parse(j), rows, map, warn)) + b);
  return /data-(slot|rows)/.test(html) ? fillHtml(html, rows, map) : html;
}
/* What a fill call is missing against an item's data note. */
function check(note, map) {
  const out = [];
  (note || []).forEach(s => {
    const n = (map[s.name] || []).length;
    if (s.count === 'one' && n !== 1) out.push(`${s.name} needs one column`);
    if (s.count === 'one or more' && n < 1) out.push(`${s.name} needs one or more columns`);
    if (s.count === 'optional' && n > 1) out.push(`${s.name} takes at most one column`);
  });
  Object.keys(map || {}).forEach(k => { if (note && !note.some(s => s.name === k)) out.push(`${k} is not a slot of this item`); });
  return out;
}

/* ---------- swap: a chart item into a slide's chart spot ---------- */
function swap(slideHtml, chartCopy, spot = 'chart') {
  const tree = parse(slideHtml);
  let done = false;
  walk(tree, (n, parent) => {
    if (done || attr(n, 'data-spot') !== spot) return;
    const w = parse(chartCopy.html), wrap = elements(w)[0];
    wrap.children = wrap.children.filter(c => !(typeof c === 'object' && /\bbasis\b/.test(attr(c, 'class') || '')));
    setAttr(wrap, 'data-spot', spot);
    parent.children[parent.children.indexOf(n)] = wrap;
    done = true;
    return false;
  });
  if (!done) throw new Error(`the slide has no data-spot="${spot}"`);
  const basis = (chartCopy.html.match(/<p class="basis">([\s\S]*?)<\/p>/) || [])[1] || '';
  return { html: serialize(tree), css: chartCopy.css, basis };
}

/* ---------- slide spots: data-spot on each chart and each piece of text ---------- */
const SPOT = /^(kicker|headline|chart|bullets|text|figure|table|footnote)(-\d+)?$/;
const hasClass = (n, c) => (' ' + (attr(n, 'class') || '') + ' ').includes(` ${c} `);
const skip = n => /^(script|style)$/.test(n.tag) || (n.tag === 'aside' && hasClass(n, 'notes'));
/* Marks every chart and piece of visible text in a slide that is not marked yet, numbering repeats (bullets, bullets-2). */
function markSpots(html) {
  const tree = parse(html), count = {};
  walk(tree, n => { const v = attr(n, 'data-spot'); if (v) { const k = v.replace(/-\d+$/, ''); count[k] = Math.max(count[k] || 0, +(v.match(/-(\d+)$/) || [0, 1])[1]); } });
  const name = k => { count[k] = (count[k] || 0) + 1; return count[k] === 1 ? k : `${k}-${count[k]}`; };
  const visit = n => elements(n).forEach(c => {
    if (skip(c) || attr(c, 'data-spot')) return;
    let k = null;
    if (hasClass(c, 'chart') && attr(c, 'data-echart') !== null) k = 'chart';
    else if (hasClass(c, 'kicker')) k = 'kicker';
    else if (/^(h1|h2|blockquote)$/.test(c.tag) && !count.headline) k = 'headline';   // a quote slide's quote is its headline
    else if (hasClass(c, 'footnote')) k = 'footnote';
    else if (/^(ul|ol)$/.test(c.tag)) k = 'bullets';
    else if (c.tag === 'table') k = 'table';
    else if (/(^|\s)(stat-value|row-key|text-[3-9]xl)(\s|$)/.test(attr(c, 'class') || '')) k = 'figure';
    else if (c.children.some(x => typeof x === 'string' && x.trim())) k = 'text';
    if (k) setAttr(c, 'data-spot', name(k)); else visit(c);
  });
  visit(tree);
  return serialize(tree);
}

/* ---------- checks build-index.js runs ---------- */
function slideProblems(html) {
  const out = [], tree = parse(html), seen = {};
  walk(tree, n => {
    if (skip(n)) return false;
    const v = attr(n, 'data-spot');
    if (v) { if (!SPOT.test(v)) out.push(`data-spot="${v}" is not one of kicker, headline, chart, bullets, text, figure, table, footnote (with -2, -3 for repeats)`); if (seen[v]) out.push(`data-spot="${v}" is used twice`); seen[v] = 1; }
    if (hasClass(n, 'chart') && attr(n, 'data-echart') !== null && !/^chart(-\d+)?$/.test(v || '')) out.push('a chart without data-spot="chart"');
    if (v) return false;   // everything inside a spot belongs to it
    const loose = n.children.find(x => typeof x === 'string' && x.trim());
    if (loose && n.tag !== '#root') out.push(`text outside a spot: "${loose.trim().slice(0, 40)}"`);
  });
  if (!seen.headline) out.push('no data-spot="headline"');
  return out;
}
function chartBlockProblems(block) {
  const out = [], tree = parse(block);
  const isChart = n => hasClass(n, 'chart') && attr(n, 'data-echart') !== null;
  const ok = n => (isChart(n) && elements(n).every(c => c.tag === 'script' && attr(c, 'type') === 'application/json') && elements(n).length === 1) || hasClass(n, 'key') || (n.tag === 'p' && hasClass(n, 'basis'));
  tree.children.forEach(c => {
    if (typeof c === 'string') { if (c.trim()) out.push(`text outside the options, key and basis line: "${c.trim().slice(0, 40)}"`); return; }
    if (c.comment || ok(c)) return;
    if (c.tag === 'div' && !isChart(c) && elements(c).every(ok) && elements(c).some(isChart)) return;   // one wrapper holding a chart and its key
    out.push(`<${c.tag}${attr(c, 'class') ? ` class="${attr(c, 'class')}"` : ''}> is not the chart, its key or its basis line`);
  });
  if (!(block.match(/<div class="chart[^"]*" data-echart/g) || []).length) out.push('no chart (div.chart[data-echart]) in the block');
  return out;
}
/* The slot names an item's block marks: "slot" keys in its chart JSON, data-slot attributes in its HTML. */
function markedSlots(block) {
  const names = new Set();
  for (const m of block.matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) { try { marks(JSON.parse(m[1])).forEach(k => slotNames(k.obj.slot).forEach(s => names.add(s))); } catch (e) { /* the JSON check reports it */ } }
  for (const m of block.matchAll(/data-slot="([^"]*)"/g)) m[1].split(/\s+/).filter(Boolean).forEach(t => names.add(t.split('@')[0]));
  return names;
}
function slotProblems(h, block) {
  if (!h.data) return ['no data note ("data: label (text, one); value (number, one or more)", AUTHORING.md)'];
  const out = [], note = parseNote(h.data), names = note.filter(s => s.name).map(s => s.name), marked = markedSlots(block);
  note.filter(s => s.bad).forEach(s => out.push(`data note: "${s.bad}" is not "<name> (<text|number|figure>, <one|one or more|optional|any>)"`));
  names.filter((n, i) => names.indexOf(n) !== i).forEach(n => out.push(`data note: slot ${n} named twice`));
  names.filter(n => !marked.has(n)).forEach(n => out.push(`slot ${n} is in the data note but marked nowhere in the block`));
  [...marked].filter(n => !names.includes(n)).forEach(n => out.push(`slot ${n} is marked in the block but not in the data note`));
  return out;
}

/* An animation's script must not carry the block's own sample wording or values (they would overwrite a filled copy). */
function scriptEchoes(block, js) {
  if (!js) return [];
  const dec = s => s.replace(/&middot;/g, '·').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/&#(\d+);/g, (m, n) => String.fromCharCode(+n)).replace(/\s+/g, ' ').trim();
  const code = js.replace(/\\u([0-9a-f]{4})/gi, (m, h) => String.fromCharCode(parseInt(h, 16)));
  const out = [], tree = parse(block);
  walk(tree, n => {
    if (n.tag === 'script' || n.tag === 'style') return false;
    if (!/(^|\s)(cap|lib-source|finding|basis)(\s|$)/.test(attr(n, 'class') || '') && !/^h[1-3]$/.test(n.tag) && !attr(n, 'data-slot')) return;
    const t = dec(textOf(n));
    if (t.length >= 15 && code.includes(t)) out.push(`its script writes the block's sample text "${t.slice(0, 50)}"; take it from the block`);
  });
  for (const m of block.matchAll(/<script type="application\/json"[^>]*>([\s\S]*?)<\/script>/g)) {
    let o; try { o = JSON.parse(m[1]); } catch (e) { continue; }
    marks(o).forEach(k => {
      const nums = [].concat(k.obj.data || []).map(d => (d && typeof d === 'object' && !Array.isArray(d) ? d.value : d)).filter(v => typeof v === 'number');
      if (nums.length >= 3 && [', ', ','].some(sep => code.includes(`[${nums.slice(0, 3).join(sep)}`))) out.push(`its script holds the sample values of slot ${k.obj.slot}; read them from the block's JSON`);
    });
  }
  return out;
}

/* ---------- rows from a file ---------- */
function readRows(file) {
  const t = fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
  if (/\.json$/i.test(file)) return JSON.parse(t);
  const lines = t.split(/\r?\n/).filter(l => l.trim());
  const cells = l => { const out = []; let cur = '', q = false; for (let i = 0; i < l.length; i++) { const ch = l[i]; if (q) { if (ch === '"' && l[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; } else if (ch === '"') q = true; else if (ch === ',') { out.push(cur); cur = ''; } else cur += ch; } out.push(cur); return out; };
  const head = cells(lines[0]);
  return lines.slice(1).map(l => { const c = cells(l), r = {}; head.forEach((h, i) => { r[h] = c[i] === undefined ? '' : c[i]; }); return r; });
}

/* ---------- CLI ---------- */
function text(c) {
  const out = [`${c.id} ${c.name} (${c.type})`];
  if (c.dataLine) out.push(`data: ${c.dataLine}`);
  if (c.recipe) out.push(`recipe: ${c.recipe}`);
  if (c.attaches) out.push(`attaches: ${c.attaches}`);
  if (c.fits) out.push(`fits: ${c.fits}`);
  if (c.spots) out.push(`spots: ${c.spots.join(' ')}`);
  if (c.css) out.push('css:', c.css);
  if (c.js) out.push('js:', c.js);
  out.push('html:', c.html);
  return out.join('\n');
}
function cli() {
  const args = process.argv.slice(2);
  const stop = m => { console.error('STOP: ' + m); process.exit(1); };
  const opt = k => { const i = args.indexOf(k); return i === -1 ? undefined : args[i + 1]; };
  const json = args.includes('--json');
  const say = v => console.log(json ? JSON.stringify(v, null, 1) : v);
  if (!args.length) stop('give an item id (see the top of item.js)');
  try {
    if (args[0] === 'theme') {
      const id = args[1], it = get(id);
      if (it.h.type !== 'theme') stop(`${id} is not a theme`);
      const t = S.themeOf(id), fonts = S.fontsOf(id), lic = (fonts.match(/themes\/([\w.-]+\.txt)/) || [])[1] || '';
      const withFonts = args.includes('--fonts');
      if (json) return say({ id, name: it.h.name, css: t.css, series: t.series, hasFonts: !!fonts, licence: lic ? `themes/${lic}` : '', fonts: withFonts ? fonts : '' });
      console.log(S.tokensBlock(t));
      if (fonts && withFonts) console.log(`<style id="theme-fonts">\n${fonts}\n</style>`);
      else if (fonts) console.log(`<!-- ${id} embeds a font: add --fonts for its @font-face block (about 90 KB) and copy themes/${lic} beside the page -->`);
      return;
    }
    if (args[0] === 'fill') {
      const map = {};
      args.forEach((a, i) => { if (a === '--slot') { const [k, v] = String(args[i + 1] || '').split('='); if (!k || v === undefined) stop('--slot <name>=<column>[,<column>]'); map[k] = v.split(',').map(s => s.trim()).filter(Boolean); } });
      if (!opt('--data')) stop('fill needs --data <rows.json|rows.csv>');
      const rows = readRows(opt('--data'));
      let html, note = null, c = null;
      if (opt('--block')) html = fs.readFileSync(opt('--block'), 'utf8');
      else { c = copyOf(get(args[1])); html = c.html; note = c.data; }
      const missing = check(note, map);
      if (missing.length) stop(missing.join('; '));
      const warn = [], out = fill(html, rows, map, warn);
      warn.forEach(w => console.error(`NOTE: ${w}`));
      return json ? say(Object.assign({}, c || {}, { html: out })) : console.log(out);
    }
    if (args[0] === 'shot') {   // a picture of the item as the library draws it, to look at (Chrome or Edge, headless)
      const it = get(args[1]), os = require('os'), { spawnSync } = require('child_process');
      const out = path.resolve(opt('--out') || path.join(os.tmpdir(), `${it.h.id}.png`));
      const browsers = [opt('--browser'), process.env.CHROME_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/microsoft-edge'].filter(Boolean);
      const exe = browsers.find(b => fs.existsSync(b));
      if (!exe) stop('no Chrome or Edge found; pass --browser <path>');
      const size = it.h.type === 'slide' ? '1280,720' : '960,540';
      const theme = opt('--theme') ? `&theme=${encodeURIComponent(JSON.stringify(S.themeOf(opt('--theme'))))}` : '';
      const url = 'file:///' + it.file.split(path.sep).join('/').replace(/^\//, '') + '#grid' + theme;
      const r = spawnSync(exe, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--window-size=${size}`, '--virtual-time-budget=6000', `--screenshot=${out}`, url], { encoding: 'utf8' });
      if (!fs.existsSync(out)) stop(`no picture written (${(r.stderr || '').split('\n').slice(-2).join(' ').trim()})`);
      return console.log(`Wrote ${out}. Read it to look at the item.`);
    }
    if (args[0] === 'swap') {
      const slide = get(args[1]), chart = get(args[2]);
      if (slide.h.type !== 'slide') stop(`${args[1]} is not a slide`);
      if (!/^(chart|table|hero card)$/.test(chart.h.type)) stop(`${args[2]} is not a chart, table or hero card`);
      const r = swap(blockOf(slide.text), copyOf(chart), opt('--spot') || 'chart');
      return json ? say(r) : console.log([r.css ? 'css:\n' + r.css : '', r.basis ? 'basis: ' + r.basis : '', 'html:', r.html].filter(Boolean).join('\n'));
    }
    const ids = args.filter(a => /^[A-Z]{2}-\d{2,}$/.test(a));
    if (!ids.length) stop(`no item id in "${args.join(' ')}"`);
    const copies = ids.map(id => copyOf(get(id)));
    return json ? say(copies) : console.log(copies.map(text).join('\n\n'));
  } catch (e) { stop(e.message); }
}

/* The text item.js prints for an item: build-index.js holds every chart to 6 KB of it. */
const printed = it => text(copyOf(it));

module.exports = { get, copyOf, blockOf, fill, fillChart, fillHtml, check, swap, parseNote, scopeCss, parse, serialize, walk, attr, textOf, spotsOf, marks, slotNames, readRows, SLOT, SPOT,
  markSpots, slideProblems, chartBlockProblems, slotProblems, markedSlots, printed, scriptEchoes };
if (require.main === module) cli();
