#!/usr/bin/env node

/**
 * Inserts one working slide into an existing deck. No dependencies.
 *
 * node add-slide.js <deck.html> --after <id|n|0> --id <new-id>
 *     --layout chart-commentary|figures|rows|table|statement   (or --pattern <library code, e.g. CP-05>)
 *     [--section <name>] [--headline "..."] [--bullets N] [--chart bar|line]
 *     [--data <file.json|file.csv> | --from "<report folder>::<section or analytic>::<table>"] [--x COL] [--y COL]
 *     [--format $K|$M|$|%|n] [--highlight <x label>] [--desc "what the slide is for, 8 to 10 words"]
 *
 * --from runs `python run.py data <section or analytic> <table> --json` in the report folder, so no number is
 * copied by hand. A time series keeps every period. The section comes from the slide before the new
 * one unless --section is given. The BRIEF slide list is rewritten. Unusual slides are a hand edit.
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { load, parse, find, synced, insertAfter, stop, updateMapCount } = require('./slides.js');

const LAYOUTS = ['chart-commentary', 'figures', 'rows', 'table', 'statement'];
const PERIOD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(\s*'?\d{2,4})?$|^\d{4}[-/]\d{1,2}$|^q[1-4]\s*'?\d{2,4}$|^\d{4}\s*q[1-4]$|^\d{4}$/i;
const SKILL = path.join(__dirname, '..');

const args = process.argv.slice(2);
const file = args[0];
const opt = k => { const i = args.indexOf(k); return i === -1 ? undefined : args[i + 1]; };

/* The report folder as typed: from here, from the deck's folder, or from the project root
   (the nearest folder above the deck with a CLAUDE.md). Slashes either way, trailing or not. */
function reportFolder(given) {
  const g = given.trim().replace(/^["']|["']$/g, '').replace(/[\\/]+$/, '') || '.';
  const deckDir = file && fs.existsSync(file) ? path.dirname(path.resolve(file)) : process.cwd();
  let root = deckDir;
  for (let d = deckDir, i = 0; i < 6; i++, d = path.dirname(d)) if (fs.existsSync(path.join(d, 'CLAUDE.md'))) { root = d; break; }
  const tried = [...new Set([path.resolve(g), path.resolve(deckDir, g), path.resolve(root, g)])];
  const hit = tried.find(d => fs.existsSync(path.join(d, 'run.py')));
  if (!hit) stop(`no run.py found for --from "${given}". Looked in:\n  ${tried.join('\n  ')}\n--from takes a report folder (the one holding run.py and report.py)`);
  return hit;
}

/* run.py data in a report folder (both layouts: sections/sN_<name>.py or one analytics file) */
function runData(folder, rest) {
  const cmd = ['run.py', 'data', ...rest, '--json'];
  let r = spawnSync('python', cmd, { cwd: folder, encoding: 'utf8' });
  if (r.error) r = spawnSync('python3', cmd, { cwd: folder, encoding: 'utf8' });
  const at = Math.min(...['[', '{'].map(c => { const i = (r.stdout || '').indexOf(c); return i === -1 ? 1e9 : i; }));
  try { r.rows = at < 1e9 ? JSON.parse(r.stdout.slice(at)) : null; } catch (e) { r.rows = null; }
  return r;
}
const lastLine = r => ((r.stderr || '') + (r.stdout || '')).trim().split(/\r?\n/).filter(l => /STOP|Error/i.test(l)).pop() || 'no output';

/* Every section or analytic, its tables and their columns, asked of run.py itself. */
function catalog(folder, typed) {
  const show = typed || folder;
  // Current run.py: "python run.py data" alone prints one line per analytic: "name(): table T [cols]; ..."
  const first = runData(folder, []);
  const listed = [];
  ((first.stdout || '') + '\n' + (first.stderr || '')).split(/\r?\n/).forEach(l => {
    const m = l.match(/^\s*(\w+)\(\): (.*)$/);
    if (!m) return;
    const tables = [...m[2].matchAll(/table (\S+) \[([^\]]*)\]/g)];
    if (!tables.length) listed.push(`  ${m[1]}: ${m[2].split(';')[0]}`);
    tables.forEach(t => listed.push(`  ${show}::${m[1]}::${t[1]}   columns: ${t[2]}`));
  });
  if (listed.length) return listed.join('\n');
  // Older run.py: names only in the STOP line; ask each for its tables and columns
  const names = (lastLine(runData(folder, ['__none__'])).match(/(?:Sections|Analytics): (.*)$/) || [])[1];
  if (!names) stop(`run.py in ${folder} listed no sections or analytics. It said: ${lastLine(first)}\nRun python run.py list there to see the report.`);
  const out = [];
  names.split(',').map(n => n.trim()).filter(Boolean).forEach(n => {
    const tables = ((lastLine(runData(folder, [n, '__none__'])).match(/It has: (.*)$/) || [])[1] || '').split(',').map(t => t.trim()).filter(Boolean);
    if (!tables.length) out.push(`  ${n}: no tables`);
    tables.forEach(t => {
      const r = runData(folder, [n, t]);
      const rows = Array.isArray(r.rows) ? r.rows : [];
      out.push(`  ${show}::${n}::${t}   ${rows.length} rows   columns: ${Object.keys(rows[0] || {}).join(', ')}`);
    });
  });
  if (!out.length) stop(`run.py in ${folder} named analytics but none had tables`);
  return out.join('\n');
}

if (opt('--from') && !opt('--from').includes('::')) {
  const typed = opt('--from').trim().replace(/[\\/]+$/, '');
  const folder = reportFolder(typed);
  console.log(`What ${folder} offers, as --from values:\n${catalog(folder, typed)}\nThen: --from "<one of these>" --x COL --y COL`);
  process.exit(0);
}
if (!file || !opt('--after') || !(opt('--layout') || opt('--pattern'))) {
  stop('usage: node add-slide.js <deck.html> --after <id|n|0> [--id <new-id>] --layout ' + LAYOUTS.join('|') +
    ' (or --pattern <code>) [--section S] [--headline H] [--bullets N] [--chart bar|line] [--data FILE | --from "folder::section-or-analytic::table"] [--x COL] [--y COL] [--format $K|$M|$|%|n]');
}
const lay = opt('--layout');
if (lay && !LAYOUTS.includes(lay)) stop(`layout "${lay}" is not one of ${LAYOUTS.join(', ')}. Anything else is a hand edit: references/slides.md, "Layouts"`);

const deck = load(file);
/* Ids are names, not positions. A given "sNN-name" whose number another slide already uses
   loses the number; no --id: one is made from the headline or the data. */
let id = opt('--id');
const idNotes = [];
if (id !== undefined) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(id)) stop('--id: lowercase letters, digits and hyphens, such as paid-by-month');
  const num = id.match(/^(s\d+)-(.+)$/);
  if (num && deck.slides.some(s => s.id.startsWith(num[1] + '-'))) { idNotes.push(`id ${id} renamed ${num[2]}: ${num[1]} is already used`); id = num[2]; }
}
const uniqueId = base => { let v = base, n = 2; while (deck.slides.some(s => s.id === v)) v = `${base}-${n++}`; return v; };
const slug = t => t.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, ' ').trim().split(' ')
  .filter(w => !/^(the|a|an|of|in|by|and|to|for|on|is|was|at)$/.test(w)).slice(0, 4).join('-') || 'slide';
const after = opt('--after') === '0' ? -1 : find(deck, opt('--after'));
const near = deck.slides[after] && deck.slides[after].section ? deck.slides[after] : deck.slides[after + 1];
const section = opt('--section') || (near && near.section) || 'Results';
const esc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const headline = opt('--headline') ? esc(opt('--headline')) : 'WORD: the point as a sentence, with its number (2 lines of 60 characters at most)';
const todo = [];
if (!opt('--headline')) todo.push('headline');

/* ---------- data ---------- */
function readData() {
  if (opt('--from')) {
    const [typed, analytic, table] = opt('--from').split('::').map(s => s.trim());
    if (!typed || !analytic) stop('--from needs "<report folder>::<section or analytic>[::<table>]"');
    const folder = reportFolder(typed);
    const r = runData(folder, [analytic].concat(table ? [table] : []));
    if (r.status !== 0 || !Array.isArray(r.rows)) {
      console.error(`STOP: python run.py data ${analytic}${table ? ' ' + table : ''} failed in ${folder}: ${lastLine(r)}\n\nWhat it offers:\n${catalog(folder, typed.replace(/[\\/]+$/, ''))}`);
      process.exit(1);
    }
    return { rows: r.rows, src: `${path.basename(path.resolve(folder))}, ${analytic}${table ? ', ' + table : ''}`,
      how: `python run.py data ${analytic}${table ? ' ' + table : ''} --json (in ${folder})`, folder, analytic, table };
  }
  if (opt('--data')) {
    const f = opt('--data');
    if (!fs.existsSync(f)) stop(`${f} not found`);
    const text = fs.readFileSync(f, 'utf8');
    let rows;
    if (/\.json$/i.test(f)) rows = JSON.parse(text);
    else {
      const lines = text.trim().split(/\r?\n/).map(l => l.split(',').map(c => c.trim().replace(/^"|"$/g, '')));
      rows = lines.slice(1).map(l => Object.fromEntries(lines[0].map((h, i) => [h, isNaN(Number(l[i])) || l[i] === '' ? l[i] : Number(l[i])])));
    }
    return { rows, src: path.basename(f), how: f };
  }
  return null;
}

const data = readData();
if (data && !Array.isArray(data.rows)) stop('the data is not a table (a list of rows); metrics go on a figures slide by hand');
if (data && opt('--pattern')) stop('data fills --layout slides only. Use --layout chart-commentary or table, or fill the pattern by hand');

let x, y, labels = [], values = [], fmt, isTime = false;
if (data) {
  const cols = Object.keys(data.rows[0] || {});
  x = opt('--x') || cols[0];
  y = opt('--y') || cols.find(c => c !== x && data.rows.every(r => typeof r[c] === 'number'));
  if (!cols.includes(x) || !cols.includes(y)) stop(`columns are ${cols.join(', ')}; pick with --x and --y`);
  labels = data.rows.map(r => String(r[x]));
  values = data.rows.map(r => Number(r[y]));
  isTime = labels.filter(l => PERIOD.test(l)).length >= labels.length / 2;
  fmt = opt('--format') || (/paid|cost|amount|revenue|spend|premium|price|dollar/i.test(y) ? (Math.max(...values.map(Math.abs)) >= 1e6 ? '$M' : '$K')
    : /rate|share|pct|percent|ratio/i.test(y) ? '%' : 'n');
}

const pct = values.length && values.every(v => Math.abs(v) <= 1.5);
const scale = v => fmt === '$K' ? v / 1e3 : fmt === '$M' ? v / 1e6 : fmt === '%' && pct ? v * 100 : v;
const round = v => { const a = Math.abs(v); return Number(v.toFixed(fmt === '$M' ? 2 : a >= 100 ? 0 : 1)); };
const text = v => { const r = round(scale(v)); const s = r.toLocaleString('en-US');
  return fmt === '$K' ? `$${s}K` : fmt === '$M' ? `$${s}M` : fmt === '%' ? `${s}%` : fmt === '$' ? `$${s}` : s; };
const tmpl = t => fmt === '$K' ? `\${${t}}K` : fmt === '$M' ? `\${${t}}M` : fmt === '%' ? `{${t}}%` : fmt === '$' ? `\${${t}}` : `{${t}}`;

/* ---------- chart ---------- */
/* One key per line; one data item per line: short enough to read and word. */
function compact(o) {
  const lines = Object.keys(o).filter(k => k !== 'series').map(k => `  "${k}": ${JSON.stringify(o[k])}`);
  const series = o.series.map(sr => {
    const { data, ...rest } = sr;
    const head = JSON.stringify(rest).slice(0, -1);
    return `    ${head},\n      "data": [\n        ${data.map(d => JSON.stringify(d)).join(',\n        ')}\n      ] }`;
  });
  return `{\n${lines.join(',\n')},\n  "series": [\n${series.join(',\n')}\n  ]\n}`;
}

function chartJson() {
  return compact(chartObj());
}

function chartObj() {
  const kind = opt('--chart') || 'bar';
  if (!data) {
    todo.push('chart data (placeholder values: give --data or --from, or replace them)');
    return ({ xAxis: { type: 'category', data: ['WORD A', 'WORD B', 'WORD C', 'WORD D'] }, yAxis: { type: 'value', show: false, max: 91 },
      series: [{ type: 'bar', barWidth: '52%', itemStyle: { color: 'var(--chart-muted)' }, label: { show: true, position: 'top', formatter: '{c}%' },
        data: [81, 79, 84, { value: 91, itemStyle: { color: 'var(--blue)' } }] }] });
  }
  const scaled = values.map(v => round(scale(v)));
  if (kind === 'line') {
    return ({
      xAxis: { type: 'category', boundaryGap: false, data: labels },
      yAxis: { type: 'value', axisLabel: { formatter: tmpl('value') } },
      grid: { left: 8, right: 120, top: 30, bottom: 8, containLabel: true },
      series: [{ type: 'line', name: y, data: scaled, itemStyle: { color: 'var(--blue)' }, lineStyle: { width: 4 }, showSymbol: false,
        label: { formatter: tmpl('c') }, endLabel: { show: true, formatter: text(values[values.length - 1]), color: 'var(--blue)', fontWeight: 600 } }],
    });
  }
  const hl = opt('--highlight') !== undefined ? labels.indexOf(opt('--highlight')) : values.indexOf(Math.max(...values));
  if (hl === -1) stop(`--highlight "${opt('--highlight')}" is not one of the ${x} values`);
  const few = labels.length <= 12;
  return ({
    xAxis: Object.assign({ type: 'category', data: labels }, few ? { axisLabel: { interval: 0 } } : {}),
    yAxis: { type: 'value', show: false, max: Math.max(...scaled) },
    grid: { left: 8, right: 8, top: 34, bottom: 8, containLabel: true },
    series: [{ type: 'bar', barWidth: '58%', itemStyle: { color: 'var(--chart-muted)' }, label: { show: few, position: 'top' },
      data: scaled.map((v, i) => i === hl
        ? { value: v, itemStyle: { color: 'var(--blue)' }, label: { show: true, position: 'top', formatter: text(values[i]), color: 'var(--blue)', fontWeight: 600 } }
        : { value: v, label: { formatter: text(values[i]) } }) }],
  });
}

/* ---------- slide ---------- */
const I = n => ' '.repeat(n);
const bulletsN = Number(opt('--bullets') || (lay === 'rows' ? 3 : 2));
const bulletLis = (n, ind) => Array.from({ length: n }, (_, i) => `${I(ind)}<li>WORD: bullet ${i + 1}: what to look at on the visual, with its number, and what it means</li>`).join('\n');
const span = data && isTime ? `${labels[0]} to ${labels[labels.length - 1]}` : '';
const yName = y ? y.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()) : '';
const footnote = `WORD: what is measured.${span ? ' ' + span + '.' : ''} Source: ${data ? data.src : 'WORD: finding n; report folder, section, table'}.`;
todo.push('footnote: what is measured');

function body() {
  if (lay === 'chart-commentary') {
    todo.push('chart heading', `${bulletsN} bullet${bulletsN === 1 ? '' : 's'}`);
    const json = chartJson().split('\n').map(l => I(14) + l).join('\n');
    const heading = `WORD: what is measured, the period${yName ? ` (${yName}, ${span})` : ''}`;
    const chart = `${I(10)}<div class="chart" data-echart>\n${I(12)}<script type="application/json">\n${json}\n${I(12)}</script>\n${I(10)}</div>`;
    if (data && labels.length > 12) {
      return `${I(8)}<div style="flex: 1; display: grid; grid-template-rows: 1fr auto; gap: 18px; min-height: 0; min-width: 0;">\n${chart}\n` +
        `${I(10)}<div class="commentary">\n${I(12)}<h3>${heading}</h3>\n${I(12)}<ul style="display: grid; grid-template-columns: repeat(${bulletsN}, 1fr); gap: 40px;">\n${bulletLis(bulletsN, 14)}\n${I(12)}</ul>\n${I(10)}</div>\n${I(8)}</div>`;
    }
    return `${I(8)}<div style="flex: 1; display: grid; grid-template-columns: 3fr 2fr; gap: 40px; min-height: 0; min-width: 0;">\n${chart}\n` +
      `${I(10)}<div class="commentary">\n${I(12)}<h3>${heading}</h3>\n${I(12)}<ul>\n${bulletLis(bulletsN, 14)}\n${I(12)}</ul>\n${I(10)}</div>\n${I(8)}</div>`;
  }
  if (lay === 'figures') {
    todo.push('three figures (value, label, comparison) and the callout');
    const stat = (k, cls) => `${I(12)}<div class="stat edge${k ? ' is-key' : ''}"><p class="stat-value${cls}">WORD 0</p><p class="stat-label">WORD: what it counts</p><p class="stat-note">WORD: what it compares to</p></div>`;
    return `${I(8)}<div class="figures">\n${I(10)}<div class="stats">\n${stat(true, '')}\n${stat(false, ' plain')}\n${stat(false, ' plain')}\n${I(10)}</div>\n` +
      `${I(10)}<div class="callout"><p class="text-lg">WORD: the one sentence that ties the figures to this audience.</p></div>\n${I(8)}</div>`;
  }
  if (lay === 'rows') {
    todo.push(`${bulletsN} rows (key, text, owner)`);
    const rows = Array.from({ length: bulletsN }, (_, i) => `${I(10)}<div><p class="row-key small">WORD key ${i + 1}</p><p>WORD: row ${i + 1}</p><p class="text-muted">WORD: owner or date</p></div>`).join('\n');
    return `${I(8)}<div class="rows" style="--rows-cols: 170px 1fr 220px;">\n${rows}\n${I(8)}</div>`;
  }
  if (lay === 'table') {
    todo.push(`${bulletsN} bullets`);
    const rows = data ? data.rows.slice(0, 5).map((r, i) => `${I(14)}<tr${i === values.indexOf(Math.max(...values.slice(0, 5))) ? ' class="is-key"' : ''}><td class="text">${esc(r[x])}</td><td>${text(Number(r[y]))}</td></tr>`).join('\n')
      : `${I(14)}<tr class="is-key"><td class="text">WORD</td><td>WORD</td></tr>\n${I(14)}<tr><td class="text">WORD</td><td>WORD</td></tr>`;
    if (data && data.rows.length > 5) todo.push(`table shows the first 5 of ${data.rows.length} rows: pick the rows the point needs`);
    if (!data) todo.push('table cells');
    return `${I(8)}<div style="flex: 1; display: grid; grid-template-columns: 3fr 2fr; gap: 44px; align-items: center;">\n${I(10)}<table class="data">\n` +
      `${I(12)}<thead><tr><th class="text">${esc(x || 'WORD')}</th><th>${esc(yName || 'WORD')}</th></tr></thead>\n${I(12)}<tbody>\n${rows}\n${I(12)}</tbody>\n${I(10)}</table>\n` +
      `${I(10)}<div class="commentary">\n${I(12)}<ul>\n${bulletLis(bulletsN, 14)}\n${I(12)}</ul>\n${I(10)}</div>\n${I(8)}</div>`;
  }
  todo.push('the statement and its source');
  return `${I(8)}<blockquote>\n${I(10)}<p>WORD: the one sentence the room should hear.</p>\n${I(10)}<cite>WORD: who said it, or where it is from</cite>\n${I(8)}</blockquote>`;
}

/* The design library, first that exists: the project map's "Design library:" line; design-library beside the
   .claude folder (an installed workspace, or the Toolkit Update bundle); Toolkit Update/design-library (this repo). */
function library() {
  for (let d = path.dirname(path.resolve(file)), i = 0; i < 6; i++, d = path.dirname(d)) {
    const map = path.join(d, 'CLAUDE.md');
    if (!fs.existsSync(map)) continue;
    const m = fs.readFileSync(map, 'utf8').match(/Design library:\s*\[?[^\]\n(]*\]?\(?([^)\s]+)\)?/);
    if (m && fs.existsSync(path.resolve(d, m[1].replace(/`/g, '')))) return path.resolve(d, m[1].replace(/`/g, ''));
    break;
  }
  const near = [path.join(SKILL, '..', '..', '..', 'design-library'), path.join(SKILL, '..', '..', '..', 'Toolkit Update', 'design-library')];
  return near.find(p => fs.existsSync(path.join(p, 'slides'))) || near[0];
}

function fromPattern(code) {
  const lib = path.join(library(), 'slides');
  if (!fs.existsSync(lib)) stop('no design library found (map line, design-library beside .claude, or Toolkit Update/design-library); use --layout');
  const f = fs.readdirSync(lib).find(x => x.startsWith(code + '-') && x.endsWith('.html'));
  if (f) {
    const h = fs.readFileSync(path.join(lib, f), 'utf8');
    const at = h.indexOf(`data-component="${code}"`);
    if (at === -1) stop(`${f} has no slide marked ${code}`);
    const open = h.lastIndexOf('<section', at), close = h.indexOf('</section>', at) + '</section>'.length;
    const keep = (h.slice(open, h.indexOf('>', open)).match(/\s(?:class|data-state|data-bar)="[^"]*"/g) || []).join('');
    let s = h.slice(open, close)
      .replace(/<section\b[^>]*>/, `<section id="${id}" data-section="${esc(section)}" data-layout="${code}"${descAttr}${keep}>`)
      .replace(/<p class="kicker">[\s\S]*?<\/p>/, `<p class="kicker">${esc(section)}</p>`)
      .replace(/<h([12])>[\s\S]*?<\/h\1>/, (all, n) => `<h${n}>${headline}</h${n}>`);
    todo.push(`every word and number in the body: they are the ${code} sample's`);
    return s;
  }
  stop(`no library slide with code ${code}; see the library index`);
}

id = uniqueId(id || slug(opt('--headline') || (y ? `${y} by ${isTime ? 'period' : x}` : (opt('--pattern') || lay))));
const words = t => t.replace(/<[^>]+>/g, '').split(/\s+/).filter(Boolean).slice(0, 10).join(' ');
const desc = opt('--desc') || (opt('--headline') ? words(opt('--headline'))
  : data && lay === 'chart-commentary' ? `${opt('--chart') || 'bar'} chart of ${yName} by ${isTime ? 'period' : x}${span ? ', ' + span : ''}`
  : `${opt('--pattern') || lay} slide in the ${section} section`);
const descAttr = ` data-desc="${esc(desc).replace(/"/g, '&quot;')}"`;
const piece = opt('--pattern') ? fromPattern(opt('--pattern')) :
  `<section id="${id}" data-section="${esc(section)}" data-layout="${lay}"${descAttr}>\n${I(8)}<p class="kicker">${esc(section)}</p>\n${I(8)}<h2>${headline}</h2>\n` +
  `${I(8)}<div class="content${lay === 'statement' ? ' middle' : ''}">\n${body().split('\n').map(l => '  ' + l).join('\n')}\n${I(8)}</div>\n` +
  `${I(8)}<div class="footnote">${esc(footnote)}</div>\n${I(6)}</section>`;

const html = synced(insertAfter(deck.html, after, piece));
fs.writeFileSync(file, html);

/* ---------- report ---------- */
const lines = html.split('\n');
const first = lines.findIndex(l => l.includes(`<section id="${id}"`)) + 1;
const last = first + piece.split('\n').length - 1;
const S = __dirname.replace(/\\/g, '/');
console.log(`Added ${id} after ${after < 0 ? 'the start' : deck.slides[after].id}, section "${section}", ${opt('--pattern') ? 'pattern ' + opt('--pattern') : lay}.`);
if (data && lay === 'chart-commentary') {
  console.log(`Chart: ${opt('--chart') || 'bar'}, ${labels.length} ${isTime ? 'periods' : 'points'} ${labels[0]}..${labels[labels.length - 1]}, ${y} by ${x}, labels as ${fmt}` +
    `${(opt('--chart') || 'bar') === 'bar' ? `, highlight ${labels[opt('--highlight') !== undefined ? labels.indexOf(opt('--highlight')) : values.indexOf(Math.max(...values))]}` : ''}. From: ${data.how}`);
  if (isTime && labels.length > 24) console.log('Over 24 periods: kept whole. Consider quarters in the analysis; never cut the window.');
  if (!opt('--format')) console.log('Label format guessed from the column name; --format $K|$M|$|%|n to change.');
}
if (data && values.length) {
  // Facts for wording the bullets and headline, formatted as on the chart: no need to read the data
  const order = values.map((v, i) => i).sort((a, b) => values[b] - values[a]);
  const at = i => `${text(values[i])} (${labels[i]})`;
  console.log(`Facts: largest ${at(order[0])}` + (order.length > 1 ? `; second ${at(order[1])}` : '') +
    `; smallest ${at(order[order.length - 1])}; latest ${at(values.length - 1)}; total ${text(values.reduce((a, b) => a + b, 0))}` +
    (order.length > 2 ? `; others ${text(values[order[order.length - 1]])} to ${text(values[order[1]])}` : '') + '.');
}
idNotes.forEach(n => console.log(n));
if (!opt('--desc')) console.log(`Description (default, change with slides.js --desc ${id} "..."): ${desc}`);
const mapNote = updateMapCount(file, parse(html).slides.length);
if (mapNote) console.log(mapNote);

/* The same table and measure already charted elsewhere in the deck: say so, once. */
if (data) {
  const mine = values.map(v => round(scale(v)));
  deck.slides.forEach((s, i) => {
    const sameSource = data.analytic && s.inner.includes(data.analytic) && (!data.table || s.inner.includes(data.table)) && /data-echart/.test(s.inner);
    let sameData = false;
    for (const m of s.inner.matchAll(/<script type="application\/json">([\s\S]*?)<\/script>/g)) {
      try {
        const o = JSON.parse(m[1]);
        const d = ([].concat(o.series || [])[0] || {}).data || [];
        const nums = d.map(v => (v && typeof v === 'object' ? v.value : v));
        sameData = sameData || (nums.length === mine.length && nums.every((v, k) => Math.abs(Number(v) - mine[k]) <= Math.max(0.6, Math.abs(mine[k]) * 0.01)));
      } catch (e) { /* not a chart this can read */ }
    }
    if (sameSource || sameData) console.log(`DUPLICATE: slide ${i + 1} (${s.id}) already charts this table and measure. Tell the user before keeping both.`);
  });
}

/* Only the lines left to word, with their line numbers: Read those, Edit those, nothing else. */
const wordLines = [];
for (let n = first; n <= last; n++) if (/WORD/.test(lines[n - 1])) wordLines.push(n);
const blocks = [];
wordLines.forEach(n => { const b = blocks[blocks.length - 1]; if (b && n === b[1] + 1) b[1] = n; else blocks.push([n, n]); });
console.log(`\nLeft to word: ${todo.join('; ')}. Edit only these lines; Read just them first (${blocks.map(b => `offset ${b[0]} limit ${b[1] - b[0] + 1}`).join(', ')}):`);
wordLines.forEach(n => console.log(`  ${n}: ${lines[n - 1].trim().slice(0, 150)}`));
console.log(`\nThen, in one command:\n  node "${S}/slides.js" ${file} && node "${S}/check-charts.js" ${file} && node "${S}/screenshot.js" ${file}\nRead sheet.png (the path it prints). slides.js flags anything still marked WORD.`);
