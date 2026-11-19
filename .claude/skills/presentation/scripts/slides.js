#!/usr/bin/env node

/**
 * The deck without reading its HTML. No dependencies.
 *
 *   node slides.js <deck.html>                         the BRIEF facts and one line per slide
 *   node slides.js <deck.html> --show <id|n>           one slide's HTML, nothing else
 *   node slides.js <deck.html> --sync                  rewrite the BRIEF slide list from the slides
 *   node slides.js <deck.html> --remove <id|n>         delete a slide; sections and BRIEF stay right
 *   node slides.js <deck.html> --move <id|n> --after <id|n|0>
 *   node slides.js <deck.html> --desc <id|n> "what the slide is for, 8 to 10 words"
 *   node slides.js <project folder>                    every deck found, each with its slides
 *
 * The BRIEF slide list is written by these scripts, never by hand.
 */

const fs = require('fs');

const START = '<!-- SLIDES:START -->';
const END = '<!-- SLIDES:END -->';
const BRIEF_KEYS = ['Audience', 'Want from them', 'Minutes', 'Answer', 'Basis', 'Sources'];

const strip = html => html.replace(/<[^>]+>/g, ' ').replace(/&amp;/g, '&').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();

function stop(msg) { console.error('STOP: ' + msg); process.exit(1); }

function load(file) {
  if (!fs.existsSync(file)) stop(`${file} not found`);
  return parse(fs.readFileSync(file, 'utf8'));
}

function parse(html) {
  const a = html.indexOf(START), b = html.indexOf(END);
  if (a === -1 || b === -1) stop('no SLIDES:START / SLIDES:END markers; not a deck made by create-presentation.js');
  const base = a + START.length;
  const body = html.slice(base, b);
  const slides = [];
  const re = /<section\b([^>]*)>/g;
  let m;
  while ((m = re.exec(body))) {
    const close = body.indexOf('</section>', re.lastIndex);
    if (close === -1) stop('a <section> has no </section>');
    const inner = body.slice(re.lastIndex, close);
    if (/<section\b/.test(inner)) stop('vertical stacks are not supported by these scripts; edit by hand');
    const end = close + '</section>'.length;
    slides.push({
      open: m.index, end, attrs: m[1], inner,
      id: (m[1].match(/\bid="([^"]*)"/) || [])[1] || '',
      own: (m[1].match(/\bdata-section="([^"]*)"/) || [])[1],
      desc: ((m[1].match(/\bdata-desc="([^"]*)"/) || [])[1] || '').replace(/&quot;/g, '"').replace(/&amp;/g, '&'),
    });
    re.lastIndex = end;
  }
  let sec = '';
  slides.forEach(s => { if (s.own !== undefined) sec = s.own; s.section = sec; });
  return { html, base, body, slides };
}

function find(deck, key) {
  const i = /^\d+$/.test(String(key)) ? Number(key) - 1 : deck.slides.findIndex(s => s.id === key);
  if (i < 0 || i >= deck.slides.length) stop(`no slide "${key}". Run slides.js for the list`);
  return i;
}

function headline(s) {
  const h = s.inner.match(/<h[12][^>]*>([\s\S]*?)<\/h[12]>/);
  return h ? strip(h[1]) : '(no headline)';
}

function layout(s) {
  const own = (s.attrs.match(/data-layout="([^"]*)"/) || [])[1];
  if (own) return own;
  if (/section-divider/.test(s.attrs)) return 'title';
  if (/data-echart/.test(s.inner)) return /class="commentary"/.test(s.inner) ? 'chart-commentary' : /class="callout/.test(s.inner) ? 'chart-callout' : 'chart';
  if (/<table class="data"/.test(s.inner)) return 'table';
  if (/class="figures"|class="stat[ "]/.test(s.inner)) return 'figures';
  if (/class="rows/.test(s.inner)) return 'rows';
  if (/<blockquote/.test(s.inner)) return 'statement';
  return 'other';
}

function chart(s) {
  const out = [];
  for (const m of s.inner.matchAll(/data-echart[^>]*>\s*<script type="application\/json">([\s\S]*?)<\/script>/g)) {
    let o;
    try { o = JSON.parse(m[1]); } catch (e) { out.push('chart JSON invalid'); continue; }
    const series = [].concat(o.series || []);
    const cat = [].concat(o.xAxis || [], o.yAxis || []).find(x => x && x.type === 'category');
    const labels = cat && cat.data ? cat.data : [];
    const names = series.map(x => x.name).filter(Boolean);
    let hi = '';
    series.forEach(x => (x.data || []).forEach((d, i) => {
      if (d && typeof d === 'object' && d.itemStyle && /--blue/.test(String(d.itemStyle.color))) hi = String(labels[i] !== undefined ? labels[i] : i);
    }));
    out.push(`${[...new Set(series.map(x => x.type))].join('+')}: ${labels.length} points` +
      (labels.length ? ` ${labels[0]}..${labels[labels.length - 1]}` : '') +
      (names.length ? `, series ${names.join(', ')}` : '') + (hi ? `, highlight ${hi}` : ''));
  }
  return out.join('; ');
}

function source(s) {
  const f = s.inner.match(/class="footnote"[^>]*>([\s\S]*?)<\/div>/);
  if (!f) return '';
  const t = strip(f[1]);
  const m = t.match(/Source:?\s*(.*)$/i);
  const src = m ? m[1] : t.split('. ').pop();
  return src.length > 70 ? src.slice(0, 67) + '...' : src;
}

function brief(deck) {
  const m = deck.body.match(/<!-- BRIEF([\s\S]*?)-->/);
  if (!m) return null;
  const facts = {};
  m[1].split('\n').forEach(line => {
    const k = BRIEF_KEYS.find(key => line.trim().startsWith(key + ':'));
    if (k) facts[k] = line.trim().slice(k.length + 1).trim();
  });
  return facts;
}

/* The BRIEF "Slides:" list, rewritten from the slides themselves. */
function synced(html) {
  const deck = parse(html);
  const list = deck.slides.map(s => `        ${s.id}: ${s.desc || '(no description) ' + headline(s)}`).join('\n');
  const body = deck.body.replace(/(<!-- BRIEF[\s\S]*?)(\n[ \t]*Slides:[\s\S]*?)?(\n[ \t]*-->)/,
    (all, head, old, close) => `${head}\n      Slides: (written by slides.js; do not edit)\n${list}${close}`);
  return html.slice(0, deck.base) + body + html.slice(deck.base + deck.body.length);
}

/* Give slide `index` an explicit data-section when it only inherited one, so a cut or insert
   before it cannot change its section. */
function pin(html, index) {
  const deck = parse(html);
  const s = deck.slides[index];
  if (!s || s.own !== undefined || !s.section) return html;
  const at = deck.base + deck.body.indexOf('>', s.open);
  return html.slice(0, at) + ` data-section="${s.section}"` + html.slice(at);
}

function cut(html, index) {
  html = pin(html, index + 1);
  const deck = parse(html);
  const s = deck.slides[index];
  const lineStart = deck.body.lastIndexOf('\n', s.open) + 1;
  const from = deck.base + (/^\s*$/.test(deck.body.slice(lineStart, s.open)) ? lineStart : s.open);
  let to = deck.base + s.end;
  while (html[to] === '\n' && html[to + 1] === '\n') to += 1;
  if (html[to] === '\n') to += 1;
  return { html: html.slice(0, from) + html.slice(to), piece: deck.body.slice(s.open, s.end), slide: s };
}

/* Insert after slide `index` (-1: before the first slide). */
function insertAfter(html, index, piece) {
  html = pin(html, index + 1);
  const deck = parse(html);
  if (!deck.slides.length) {
    const at = deck.base + deck.body.length;
    return html.slice(0, at).replace(/[ \t]*<!-- NEW SLIDES:[^\n]*-->\n*/, '') + '      ' + piece.trim() + '\n\n' + html.slice(at);
  }
  if (index < 0) {
    const at = deck.base + deck.slides[0].open;
    return html.slice(0, at) + piece.trim() + '\n\n      ' + html.slice(at);
  }
  const at = deck.base + deck.slides[index].end;
  return html.slice(0, at) + '\n\n      ' + piece.trim() + html.slice(at);
}

function inventory(deck, where) {
  const f = brief(deck) || {};
  const lines = [];
  ['Audience', 'Want from them', 'Basis', 'Sources'].forEach(k => { if (f[k]) lines.push(`${k}: ${f[k]}`); });
  if (!Object.keys(f).length) lines.push('No BRIEF comment found.');
  lines.push('');
  const seen = [];
  deck.slides.forEach((s, i) => {
    const h = headline(s), c = chart(s), src = source(s), flags = [];
    if (s.section && seen.includes(s.section) && seen[seen.length - 1] !== s.section) flags.push(`section "${s.section}" reopened: bar out of order`);
    if (s.section && seen[seen.length - 1] !== s.section) seen.push(s.section);
    if (/WORD:/.test(s.inner)) flags.push('TO WORD');
    if (h.length > 120) flags.push('headline over 2 lines');
    lines.push(`${String(i + 1).padStart(2)} ${s.id} | ${where} | ${s.section || '-'} | ${layout(s)}${c ? ' | ' + c : ''} | ${s.desc || '-'}`);
    lines.push(`   ${h}${src ? '  (source: ' + src + ')' : ''}${flags.length ? '  <- ' + flags.join('; ') : ''}`);
  });
  const bare = deck.slides.filter(s => !s.desc).length;
  if (bare) lines.push(`\n${bare} of ${deck.slides.length} slides have no description. Set one: node slides.js <deck> --desc <id> "what the slide is for, 8 to 10 words"`);
  return lines.join('\n');
}

/* The project map's row for this deck: if it states "N slides", make N the deck's count. */
function updateMapCount(file, n) {
  const path = require('path');
  const deckDir = path.dirname(path.resolve(file));
  for (let d = deckDir, i = 0; i < 6; i++, d = path.dirname(d)) {
    const map = path.join(d, 'CLAUDE.md');
    if (!fs.existsSync(map)) continue;
    const rel = path.relative(d, deckDir).split(path.sep).join('/');
    const text = fs.readFileSync(map, 'utf8');
    const lines = text.split('\n');
    const k = lines.findIndex(l => l.trim().startsWith('|') && (l.includes(rel + '/') || l.includes(rel + '`')));
    if (k === -1 || !/\b\d+ slides\b/.test(lines[k])) return '';
    const before = lines[k];
    lines[k] = before.replace(/\b\d+ slides\b/, `${n} slides`);
    if (lines[k] === before) return '';
    fs.writeFileSync(map, lines.join('\n'));
    return `Map row updated: ${n} slides (${path.relative(process.cwd(), map) || map}).`;
  }
  return '';
}

/* Every deck in a project folder: any .html file with the SLIDES markers. */
function decksIn(dir) {
  const out = [];
  const walk = d => fs.readdirSync(d, { withFileTypes: true }).forEach(e => {
    const p = require('path').join(d, e.name);
    if (e.isDirectory()) { if (!/^(\.|node_modules|__pycache__)/.test(e.name)) walk(p); }
    else if (/\.html$/i.test(e.name)) { const t = fs.readFileSync(p, 'utf8'); if (t.includes(START) && t.includes(END) && t.includes('Reveal.initialize')) out.push(p); }
  });
  walk(dir);
  return out;
}

function main() {
  const args = process.argv.slice(2);
  const file = args[0];
  if (!file) stop('usage: node slides.js <deck.html> [--show ID | --sync | --remove ID | --move ID --after ID]');
  const opt = k => { const i = args.indexOf(k); return i === -1 ? undefined : args[i + 1]; };
  const path = require('path');
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) {
    const decks = decksIn(file);
    if (!decks.length) { console.log(`No decks under ${file}.`); return; }
    decks.forEach(d => { const rel = path.relative(file, d).split(path.sep).join('/'); console.log(`== ${rel}\n${inventory(load(d), rel)}\n`); });
    return;
  }
  const deck = load(file);
  const where = path.basename(file);
  const save = html => { fs.writeFileSync(file, synced(html)); };

  if (opt('--show')) {
    const s = deck.slides[find(deck, opt('--show'))];
    console.log(deck.body.slice(s.open, s.end));
  } else if (opt('--desc')) {
    const s = deck.slides[find(deck, opt('--desc'))];
    const text = args[args.indexOf('--desc') + 2];
    if (!text) stop('--desc <id|n> "what the slide is for, in 8 to 10 words"');
    const val = text.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    const attrs = /\bdata-desc="[^"]*"/.test(s.attrs) ? s.attrs.replace(/\bdata-desc="[^"]*"/, `data-desc="${val}"`) : `${s.attrs} data-desc="${val}"`;
    const at = deck.base + s.open;
    save(deck.html.slice(0, at) + `<section${attrs}>` + deck.html.slice(at + `<section${s.attrs}>`.length));
    console.log(`Description set on ${s.id}. BRIEF slide list rewritten.`);
  } else if (args.includes('--sync')) {
    save(deck.html);
    console.log('BRIEF slide list rewritten.');
  } else if (opt('--remove')) {
    const out = cut(deck.html, find(deck, opt('--remove')));
    save(out.html);
    const mapNote = updateMapCount(file, load(file).slides.length);
    console.log(`Removed ${out.slide.id}. BRIEF slide list rewritten.${mapNote ? ' ' + mapNote : ''}\n\n${inventory(load(file), where)}`);
  } else if (opt('--move')) {
    if (opt('--after') === undefined) stop('--move needs --after <id|n> (0 for first)');
    const out = cut(deck.html, find(deck, opt('--move')));
    const after = opt('--after') === '0' ? -1 : find(parse(out.html), opt('--after'));
    let piece = out.piece;
    if (out.slide.own === undefined && out.slide.section) piece = piece.replace(/^<section\b/, `<section data-section="${out.slide.section}"`);
    save(insertAfter(out.html, after, piece));
    console.log(`Moved ${out.slide.id}. BRIEF slide list rewritten. Check the section order:\n\n${inventory(load(file), where)}`);
  } else {
    console.log(inventory(deck, where));
  }
}

module.exports = { load, parse, find, headline, synced, insertAfter, stop, inventory, updateMapCount };
if (require.main === module) main();
