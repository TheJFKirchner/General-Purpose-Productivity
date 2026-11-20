// npm run new-section: writes one section file from a design library item (or a blank one). Usage: npm run
// new-section -- --help. Never overwrites anything.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, pythonCommand, readJsonFile } from './py.mjs';
import { findLibrary, itemJs } from './library.mjs';
import { SAMPLE_WORDS, checkSlots, fillChart } from '../Src/Lib/fill.js';

const SECTIONS = path.join(ROOT, 'Src', 'Sections');
const INDEX = path.join(SECTIONS, 'index.js');
const ANALYSIS = path.join(ROOT, 'Analysis');
const MONEY = /paid|amount|cost|revenue|price|spend|allowed|charge|premium|sales|billed|usd|\$/i;
const SHAPED = ['base', 'rise', 'fall', 'total', 'share'];

function fail(msg) {
  console.log(`new-section: ${msg} (nothing was written)`);
  process.exit(1);
}

// ---- arguments
const argv = process.argv.slice(2);
const opts = {};
const slotArgs = [];
const positional = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) {
    positional.push(a);
    continue;
  }
  const [k, inline] = a.slice(2).split(/=(.*)/s, 2);
  const v = inline ?? (argv[i + 1] !== undefined && !argv[i + 1].startsWith('--') ? argv[++i] : 'true');
  if (k === 'slot') slotArgs.push(v);
  else opts[k] = v;
}
const USAGE = `npm run new-section -- NAME --use <CT|TB|HC id> --page <tab> --tables <table> --slot <slot>=<column> ...
npm run new-section -- NAME --own chart|html --page <tab> --tables <table> [--slot ...]

Writes Src/Sections/sN_NAME.jsx: the library item wired to the table's columns, a title and a note, and adds it to
Src/Sections/index.js. Prints the lines to reword.

  --slot SLOT=COL[,COL]   which column fills a slot (the item's data: line in the library index); a number for a
                          figure (--slot target=80); the column "rows" counts rows
  --agg sum|mean|count    how a number column is added up (default sum)
  --by COL                one line, part or column per value of COL
  --month                 group the date column in the text slot by month (automatic for a daily date);
                          --period quarter|year for others
  --top N                 the N largest (with --by, --pareto or a waterfall the rest become "All other")
  --compare COL=A,B       two values side by side (2026-04,2026-05 for months): a waterfall bridges A to B,
                          figure tiles show A, B and the change, other items show A and B per group
  --share                 adds a share column (% of all rows); --pareto COL: largest first with the running share
  waterfall (CT-06)       --slot step=GROUP --slot total=AMOUNT builds up to a total; add --compare for a bridge
  --size half, --title "...", --note "first bullet | second", --keep-filter, --report NAME, --library FOLDER

No --slot: the copy plus an analytic stub in Analysis/<tab>.py returning rows with the slot names as columns.`;
if (!positional.length || opts.help) {
  console.log(USAGE);
  process.exit(opts.help ? 0 : 1);
}
const val = (k) => (opts[k] && opts[k] !== 'true' ? String(opts[k]) : null);
const flag = (k) => opts[k] !== undefined;
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
const human = (s) => String(s).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
const tables = (val('tables') ?? '').split(',').map((x) => x.trim()).filter(Boolean);
if (!val('use') && !val('own')) fail('say what to copy: --use <library id> (CT-34, TB-09, HC-15 ...) or --own chart|html for a blank one');
if (!tables.length) fail('--tables <table> is needed (npm run status lists the tables)');

// ---- the item
const OWN = {
  chart: {
    id: 'own-chart', type: 'chart', name: 'own chart', recipe: '',
    data: [{ name: 'label', kind: 'text', count: 'one' }, { name: 'value', kind: 'number', count: 'one or more' }],
    html: '<div class="chart" data-echart><script type="application/json">{"legend":{"top":0,"right":0},"grid":{"left":8,"right":8,"top":40,"bottom":8,"containLabel":true},"xAxis":{"slot":"label","type":"category","data":["Group A","Group B"]},"yAxis":{"type":"value"},"series":[{"slot":"value","type":"bar","barMaxWidth":64,"label":{"show":true,"position":"top"},"data":[60,45]}]}</script></div>\n<p class="basis">What is measured, the period and the basis.</p>',
  },
  html: {
    id: 'own-html', type: 'table', name: 'own html', recipe: '',
    data: [{ name: 'label', kind: 'text', count: 'one' }, { name: 'value', kind: 'number', count: 'one or more' }],
    html: '<div class="lib-panel">\n<p class="cap">Caption: the measure and the period</p>\n<table class="lib-table">\n<thead><tr><th class="left" data-slot="label">Label</th><th data-slot="value">Value</th></tr></thead>\n<tbody data-rows>\n<tr><td class="left" data-slot="label">Group A</td><td data-slot="value">60</td></tr>\n</tbody>\n</table>\n<p class="lib-source">Sample values</p>\n</div>',
  },
};
let item;
if (val('own')) {
  item = OWN[val('own')];
  if (!item) fail('--own takes chart or html');
} else {
  const id = val('use').toUpperCase();
  if (!/^(CT|TB|HC)-\d\d$/.test(id)) fail(`--use takes a chart, table or hero card id (CT-34, TB-09, HC-15), not "${val('use')}"`);
  item = itemJs(findLibrary(val('library')), [id, '--json'])[0];
  if (!item) fail(`no item ${id} in the library`);
}
const isChart = item.type === 'chart';
const note = item.data ?? [];
const kindOf = Object.fromEntries(note.map((s) => [s.name, s]));

// ---- the table and its columns
const r = spawnSync(pythonCommand(), [path.join('Analysis', 'check.py'), '--describe-only'], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
let described;
try {
  described = JSON.parse(r.stdout).describe;
} catch {
  fail(`could not read the tables: ${(r.stderr || r.stdout || '').trim().split('\n').slice(-2).join(' | ') || 'no output'}`);
}
if (!described) fail('no tables yet: load the data first (npm run pipeline)');
const table = tables[0];
const t = described[table];
if (!t) fail(`no table "${table}" (tables: ${Object.keys(described).join(', ') || 'none'})`);
const col = t.columns;
const hasCol = (c) => c === 'rows' || Boolean(col[c]);

// ---- slots: given, or defaults for --own
const slots = {};
for (const s of slotArgs) {
  const [k, v] = s.split(/=(.*)/s, 2);
  if (!k || v === undefined) fail(`--slot ${s}: write it as slot=column`);
  slots[k.trim()] = v.split(',').map((x) => x.trim()).filter(Boolean);
}
const AGG = (val('agg') ?? 'sum').toLowerCase();
if (!['sum', 'mean', 'count'].includes(AGG)) fail(`--agg must be sum, mean or count (got "${AGG}")`);
const BY = val('by');
let between = null;   // --compare COL=A,B: two values of one column side by side
if (val('compare')) {
  const m = /^([^=]+)=([^,]+),([^,]+)$/.exec(val('compare'));
  if (!m) fail('--compare takes COL=A,B, e.g. --compare service_date=2026-04,2026-05');
  between = { col: m[1].trim(), a: m[2].trim(), b: m[3].trim() };
  if (!hasCol(between.col)) fail(`--compare: no column "${between.col}" in ${table} (columns: ${Object.keys(col).join(', ')})`);
  if (BY) fail('--compare and --by both split the numbers; use one');
}
const waterfallItem = Boolean(kindOf.base && kindOf.total);
const textCol = (c) => Boolean(c) && c !== 'rows' && Boolean(col[c]) && col[c].type !== 'number';
if (waterfallItem && slots.total?.length && textCol(slots.total[0])) fail(`a waterfall's total takes the amount column (a number); ${slots.total[0]} is text. Write: --slot step=${slots.total[0]} --slot total=<amount column>`);
if (val('waterfall') && textCol(val('waterfall'))) fail(`--waterfall takes the amount column (a number); ${val('waterfall')} is text. Write: --slot step=${val('waterfall')} --slot total=<amount column>`);
const measure = val('pareto') ?? val('waterfall') ?? (waterfallItem && slots.total?.length ? slots.total[0] : null);
const shape = waterfallItem && measure ? 'waterfall' : val('pareto') ? 'pareto' : flag('share') ? 'share' : null;
if (val('own') && !slotArgs.length) {   // a blank section: the first text column and the first number column
  const text = Object.keys(col).find((c) => ['text', 'month', 'date'].includes(col[c].type));
  const num = Object.keys(col).find((c) => col[c].type === 'number');
  if (text) slots.label = [text];
  slots.value = [AGG === 'count' || !num ? 'rows' : num];
}
const stub = !Object.keys(slots).length && !measure && !between;
for (const k of Object.keys(slots)) if (!kindOf[k]) fail(`${k} is not a slot of ${item.id} (its slots: ${note.map((s) => s.name).join(', ')})`);
for (const s of note.filter((x) => x.kind === 'number' && slots[x.name])) {
  for (const c of slots[s.name]) {
    if (textCol(c)) fail(`slot ${s.name} takes a number column; ${c} is ${col[c].type}. Text columns go in ${note.filter((x) => x.kind === 'text').map((x) => x.name).join(' or ') || 'no slot of this item'}`);
  }
}

// ---- what Python works out: x (the text slot), y (the number columns), and the shape
const textSlots = note.filter((s) => s.kind === 'text' && slots[s.name]?.length);
const xCols = [...new Set(textSlots.flatMap((s) => slots[s.name]))];
if (xCols.length > 1) fail(`only one text column can be grouped by (${xCols.join(', ')}); for more, leave out --slot and write the analytic`);
const X = xCols[0] ?? null;
const xSlot = textSlots[0]?.name ?? null;
const made = shape === 'waterfall' ? ['base', 'rise', 'fall', 'total', 'key'] : shape ? ['share'] : [];
if (shape === 'waterfall') delete slots.total;
for (const s of made) if (kindOf[s] && !slots[s]) slots[s] = [s];   // the shape's own columns fill slots of the same name
if (measure && shape !== 'waterfall') {   // the measure goes in the first number slot still empty
  const open = note.find((s) => s.kind === 'number' && !slots[s.name] && s.count !== 'optional' && s.count !== 'any');
  if (open) slots[open.name] = [measure];
}
let ys = [];
for (const s of note) {
  if (s.kind === 'text' || !slots[s.name]) continue;
  for (const c of slots[s.name]) {
    if (/^-?\d+(\.\d+)?$/.test(c) || c === '*') continue;
    if ([...made, 'share'].includes(c) && !hasCol(c)) continue;
    if (!ys.includes(c)) ys.push(c);
  }
}
if (measure && !ys.includes(measure)) ys = [measure, ...ys];
if (AGG === 'count' && !ys.length) ys = ['rows'];
for (const c of [X, BY, ...ys]) if (c && !hasCol(c)) fail(`no column "${c}" in ${table} (columns: ${Object.keys(col).join(', ')}, or rows)`);
for (const c of ys) if (c !== 'rows' && col[c].type !== 'number') fail(`${c} is ${col[c].type}, not a number; use --agg count or the column "rows" to count`);
if ((BY || between) && ys.length > 1) fail(`${BY ? '--by' : '--compare'} takes one value column`);
const totals = !stub && !X;   // no text column: one row per measure (label, value), or A, B and the change
if (totals) {
  const label = note.find((s) => s.kind === 'text' && s.count === 'one');
  const value = note.find((s) => s.kind === 'number' && s.count !== 'any');
  if (!label || !value) fail(`${item.id} needs a text column (--slot ${note.find((s) => s.kind === 'text')?.name ?? 'label'}=<column>)`);
  slots[label.name] = ['label'];
  for (const s of note) if (s.kind === 'number' && slots[s.name] && s !== value) delete slots[s.name];
  slots[value.name] = ['value'];
}
if ((BY || between) && !totals && shape !== 'waterfall') {   // one value column per value of BY (or for A and for B)
  const s = note.find((x) => x.kind === 'number' && slots[x.name]?.includes(ys[0]));
  if (s) slots[s.name] = ['*'];
}
if (stub) for (const s of note) if (s.kind !== 'figure') slots[s.name] = [s.name];
const problems = stub ? [] : checkSlots(note, Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, v.length === 1 ? v[0] : v])));
if (problems.length) fail(`${item.id} ${problems.join('; ')} (its data: ${note.map((s) => `${s.name} (${s.kind}, ${s.count})`).join('; ')})`);

const asked = val('period') ?? (flag('month') ? 'month' : null);
if (asked && !['month', 'quarter', 'year'].includes(asked)) fail('--period takes month, quarter or year');
if (asked && !(X && ['date', 'month'].includes(col[X]?.type))) fail(`--${flag('month') ? 'month' : 'period'} groups the date column given to a text slot (e.g. --slot ${note.find((s) => s.kind === 'text')?.name ?? 'label'}=service_date)${X ? `; ${X} is ${col[X]?.type}` : ''}`);
const period = asked ?? (X && col[X]?.type === 'date' ? 'month' : null);
const isTime = Boolean(period) || col[X]?.type === 'month';
const top = val('top') ? Number(val('top')) : null;
if (top !== null && !(Number.isInteger(top) && top > 0)) fail('--top takes a whole number');

// ---- words and formats for the columns
const nameOf = (c) => (c === 'rows' ? human(table) : AGG === 'mean' ? `Average ${String(c).replace(/_/g, ' ')}` : human(c));
const formatOf = (c) => (c === 'rows' ? 'comma' : MONEY.test(c) ? (AGG === 'mean' ? '$comma' : '$short') : AGG === 'mean' ? 'comma' : 'short');
const names = {};
const format = {};
if (X) names[X] = human(X);
for (const c of ys) {
  names[c] = nameOf(c);
  format[c] = formatOf(c);
}
if (BY || between) format['*'] = formatOf(ys[0]);
if (shape === 'waterfall') {
  for (const k of ['base', 'rise', 'fall', 'total', 'key']) format[k] = formatOf(measure);
  Object.assign(names, { base: nameOf(measure), rise: 'Rise', fall: 'Fall', total: 'Total', key: 'Largest change' });
}
if (shape === 'share' || shape === 'pareto') format.share = 'pct';
if (X && isTime && period !== 'quarter' && period !== 'year') format[X] = 'month';
if (totals) format.value = between ? formatOf(ys[0]) : ys.every((c) => formatOf(c) === formatOf(ys[0])) ? formatOf(ys[0]) : 'short';
const did = stub ? null : [
  between ? `${between.a} against ${between.b} (${between.col})` : null,
  `${{ sum: 'sum', mean: 'average', count: 'count' }[AGG]} of ${ys.join(', ')}`,
  X ? `by ${period ? `${period} of ` : ''}${X} (slot ${xSlot})` : totals && !between ? 'one row per measure' : null,
  BY ? `one column per ${BY}` : null, top ? `top ${top}` : null, shape ? `as a ${shape}` : null,
].filter(Boolean).join(', ');

// ---- existing sections, the id, the tab
const read = (f) => (fs.existsSync(f) ? fs.readFileSync(f, 'utf8').replace(/^\uFEFF/, '') : '');
const indexSrc = read(INDEX);
if (!indexSrc) fail('Src/Sections/index.js not found (run this inside a dashboard folder)');
const sectionFiles = fs.readdirSync(SECTIONS).filter((f) => /^s\d+_.*\.jsx$/.test(f));
const analysisIds = fs.readdirSync(ANALYSIS).filter((f) => f.endsWith('.py')).flatMap((f) => [...read(path.join(ANALYSIS, f)).matchAll(/@(?:card|section)\(\s*["'](s\d+_[a-z0-9_]+)["']/g)].map((m) => m[1]));
const usedIds = new Set([...sectionFiles.map((f) => f.replace(/\.jsx$/, '')), ...analysisIds]);
const usedNumbers = new Set([...usedIds].map((i) => Number(/^s(\d+)_/.exec(i)[1])));
let id = positional[0];
if (!/^s\d+_[a-z0-9_]+$/.test(id)) {
  const name = slug(id);
  if (!name) fail(`"${id}" doesn't make a usable name (use letters and numbers, e.g. paid_by_region)`);
  id = `s${Math.max(0, ...usedNumbers) + 1}_${name}`;
}
if (usedIds.has(id)) fail(`${id} already exists`);
if (usedNumbers.has(Number(/^s(\d+)_/.exec(id)[1]))) fail(`the number in ${id} is already used; leave the number off and one is picked`);
const shortName = id.replace(/^s\d+_/, '');
const fillBlock = (block, body) => block.slice(0, block.indexOf('[') + 1) + body + block.slice(block.lastIndexOf(']'));
const tabsBlock = /export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]\s*;/.exec(indexSrc);
const tabIds = tabsBlock ? [...tabsBlock[1].matchAll(/id\s*:\s*['"]([^'"]+)['"]/g)].map((m) => m[1]) : [];
const defaultBlock = /export\s+default\s+\[([\s\S]*?)\]\s*;/.exec(indexSrc);
const hasSections = defaultBlock ? /[A-Za-z_]/.test(defaultBlock[1].replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '')) : sectionFiles.length > 0;
const page = val('page') ? slug(val('page')) : null;
let tab = null;
let addTab = null;
if (tabIds.length) {
  tab = page ?? tabIds[0];
  if (!tabIds.includes(tab)) addTab = tab;
} else if (page && !hasSections) (tab = page), (addTab = page);
const analysisName = page ?? tab ?? 'overview';
if (['server', 'check', 'precompute'].includes(analysisName) || analysisName.startsWith('_')) fail(`"${analysisName}" can't be a tab name (it's reserved)`);
const config = readJsonFile(path.join(ROOT, 'dashboard.config.json'));
const ignore = X && !flag('keep-filter')
  ? Object.entries(config.filters ?? {}).filter(([k, f]) => !k.startsWith('_') && [X, BY].includes(f?.column ?? k)).map(([k]) => k)
  : [];

// ---- the copy
const tl = (s) => `\`${String(s).replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$\{/g, '\\${')}\``;
const decode = (s) => s.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').trim();
let option = null;
let keyHtml = null;
let basis = null;
let html = null;
const block = String(item.html).replace(/^\s*<div data-item="[^"]*">\s*/, '').replace(/\s*<\/div>\s*$/, '');
if (isChart) {
  option = JSON.parse(/<script type="application\/json">([\s\S]*?)<\/script>/.exec(block)?.[1] ?? '{}');
  keyHtml = /<div class="key"[^>]*>([\s\S]*?)<\/div>/.exec(block)?.[1]?.trim() ?? null;
  basis = decode(/<p class="basis"[^>]*>([\s\S]*?)<\/p>/.exec(block)?.[1] ?? '') || null;
} else {
  html = block.replace(/(<div class="lib-panelhead">\s*<div>)\s*<h2>[\s\S]*?<\/h2>/, '$1');   // the section's title is the heading
}

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const when = (v) => (/^\d{4}-\d{2}$/.test(v) ? `${MON[Number(v.slice(5)) - 1]} ${v.slice(0, 4)}` : v);
const title = val('title') ?? (between ? `${nameOf(ys[0])}, ${when(between.a)} to ${when(between.b)}${X ? ` by ${X.replace(/_/g, ' ')}` : ''}` : totals ? human(shortName) : `${ys.length ? nameOf(ys[0]) : human(shortName)}${X ? ` by ${period ?? String(X).replace(/_/g, ' ')}` : ''}${BY ? ` and ${BY.replace(/_/g, ' ')}` : ''}`);
const desc = val('desc') ?? `${title}, ${{ sum: 'summed', mean: 'averaged', count: 'counted' }[AGG]}, as ${item.name}`;
const q = (s) => `'${String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`;
const list = (xs) => `[${xs.map(q).join(', ')}]`;
const wire = (o) => (!Object.keys(o).length ? '{}' : `{ ${Object.entries(o).map(([k, v]) => `${/^[a-z_$][\w$]*$/i.test(k) ? k : q(k)}: ${Array.isArray(v) ? (v.length === 1 && !kindOf[k]?.count?.includes('more') ? lit(v[0]) : `[${v.map(lit).join(', ')}]`) : lit(v)}`).join(', ')} }`);
const lit = (v) => (typeof v === 'number' || /^-?\d+(\.\d+)?$/.test(String(v)) ? String(v) : q(v));

function jsOf(v, ind = '') {
  const pad = `${ind}  `;
  const key = (k) => (/^[a-z_$][\w$]*$/i.test(k) ? k : JSON.stringify(k));
  if (Array.isArray(v)) {
    if (!v.length) return '[]';
    if (v.every((x) => x === null || typeof x !== 'object')) {
      const parts = v.map((x) => JSON.stringify(x));
      const one = `[${parts.join(', ')}]`;
      if (one.length <= 90) return one;
      const lines = [];
      for (let i = 0; i < parts.length; i += 10) lines.push(pad + parts.slice(i, i + 10).join(', '));
      return `[\n${lines.join(',\n')},\n${ind}]`;
    }
    return `[\n${v.map((x) => pad + jsOf(x, pad)).join(',\n')},\n${ind}]`;
  }
  if (v && typeof v === 'object') {
    const keys = Object.keys(v);
    if (!keys.length) return '{}';
    const one = `{ ${keys.map((k) => `${key(k)}: ${jsOf(v[k], pad)}`).join(', ')} }`;
    if (one.length <= 90 && !one.includes('\n')) return one;
    return `{\n${keys.map((k) => `${pad}${key(k)}: ${jsOf(v[k], pad)}`).join(',\n')},\n${ind}}`;
  }
  return JSON.stringify(v);
}

function sectionFile(noteLines) {
  const numbers = stub ? `tables: ${list(tables)}` : [
    `tables: ${list([table])}`, X ? `x: ${q(X)}` : null, period ? `period: ${q(period)}` : null,
    ys.length && !(AGG === 'count' && ys[0] === 'rows' && ys.length === 1) ? `y: ${list(ys)}` : null, `agg: ${q(AGG)}`, BY ? `by: ${q(BY)}` : null,
    top ? `top: ${top}` : null, totals ? "shape: 'totals'" : shape ? `shape: ${q(shape)}` : null,
    between ? `compare: ${q(`${between.col}=${between.a},${between.b}`)}` : null,
    ignore.length ? `ignore: ${list(ignore)}` : null,
  ].filter(Boolean).join(', ');
  const visual = isChart
    ? `const chart = ${jsOf(option)};`
    : `const html = ${tl(html)};`;
  const extras = [
    keyHtml ? `const keyHtml = ${tl(keyHtml)};` : null,
    item.css ? `const css = ${tl(item.css)};` : null,
    item.js ? `const script = ${tl(item.js)};` : null,
  ].filter(Boolean);
  const props = [
    `use="${item.id}"`, isChart ? 'chart={chart}' : 'html={html}', keyHtml ? 'keyHtml={keyHtml}' : null, item.css ? 'css={css}' : null,
    item.js ? 'script={script}' : null, basis !== null ? 'basis={basis}' : null,
  ].filter(Boolean).join(' ');
  return `// ${title}: ${item.id} ${item.name}, ${val('own') ? 'a blank item' : 'copied from the design library'}. Change anything in this file.
// The numbers are worked out in Python ${stub ? `by its analytic in Analysis/${analysisName}.py` : 'from the meta (tables, x, y, agg ...)'}. At every draw the
// data lists in the ${isChart ? 'chart' : 'html'} below are refilled; names, colours, labels and axis settings stay as written.
${item.recipe ? `// Shaping (the library's recipe): ${item.recipe}\n` : ''}import Item from '../Components/Item.jsx';

export const meta = {
  id: '${id}', title: ${q(title)}${tab ? `, tab: '${tab}'` : ''}, use: '${item.id}', library: '${isChart ? 'echarts' : 'none'}'${val('size') === 'half' ? ", size: 'half'" : ''},
  description: ${q(desc)},
  ${numbers},
};

// Which column fills which slot of the item; the words readers see for a column; number formats.
export const slots = ${wire(slots)};
export const names = ${wire(names)};
export const format = ${wire(format)};

// The text above the ${isChart ? 'chart' : 'item'}. Keep the {metric|format} parts: they fill in the real numbers.
export const note = \`${noteLines.length ? `\n${noteLines.map((l) => `- ${l.replace(/`/g, '\\`').replace(/\$\{/g, '\\${')}`).join('\n')}\n` : ''}\`;
${basis !== null ? `const basis = ${q(basis)};\n` : ''}
${visual}
${extras.length ? `\n${extras.join('\n')}\n` : ''}
export default function Section({ data, metrics }) {
  return <Item ${props} rows={data.rows} slots={slots} names={names} format={format} metrics={metrics} />;
}
`;
}

// ---- the registry (index.js)
let newIndex = null;
if (defaultBlock) {
  let src = indexSrc;
  const importsFound = [...src.matchAll(/^import[^\n]*\n/gm)];
  const lead = /^(?:\s*\/\/[^\n]*\n)*/.exec(src)[0].length;
  const at = importsFound.length ? importsFound.at(-1).index + importsFound.at(-1)[0].length : lead;
  src = `${src.slice(0, at)}import * as ${id} from './${id}.jsx';\n${src.slice(at)}`;
  if (addTab) {
    const tb = /export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]\s*;/.exec(src);
    if (tb) {
      const inner = tb[1].replace(/\s+$/, '');
      const sep = inner.trim() && !inner.trim().endsWith(',') ? ',' : '';
      src = src.slice(0, tb.index) + fillBlock(tb[0], `${inner}${sep}\n  { id: '${addTab}', label: '${human(addTab)}' },\n`) + src.slice(tb.index + tb[0].length);
    }
  }
  const db = /export\s+default\s+\[([\s\S]*?)\]\s*;/.exec(src);
  const inner = db[1].replace(/\s+$/, '');
  const bare = inner.replace(/\/\/.*$/gm, '').trim();
  src = src.slice(0, db.index) + fillBlock(db[0], `${inner}${bare && !bare.endsWith(',') ? ',' : ''}\n  ${id},\n`) + src.slice(db.index + db[0].length);
  newIndex = src;
}

// ---- the analytic stub (no --slot)
const analysisFile = path.join(ANALYSIS, `${analysisName}.py`);
let analysisSrc = read(analysisFile);
if (stub) {
  const defs = new Set([...analysisSrc.matchAll(/^def\s+([A-Za-z_]\w*)/gm)].map((m) => m[1]));
  let fn = /^[a-z_]/.test(shortName) ? shortName : `section_${shortName}`;
  for (let i = 2; defs.has(fn); i++) fn = `${shortName}_${i}`;
  const need = Object.keys(slots);
  const head = analysisSrc ? '' : `"""${analysisName.replace(/_/g, ' ')}: the analytics for this tab's sections (one function per section)."""\nfrom Shared.registry import section\n`;
  if (analysisSrc && !/from\s+Shared\.registry\s+import[^\n]*\bsection\b/.test(analysisSrc)) analysisSrc = `from Shared.registry import section\n${analysisSrc}`;
  analysisSrc = `${analysisSrc ? analysisSrc.replace(/\s*$/, '\n') : head}\n\n@section("${id}", tables=[${tables.map((x) => `"${x}"`).join(', ')}])\ndef ${fn}(t):\n    """${title}. Not built yet: return one row per ${isChart ? 'point' : 'row'} with the columns ${need.join(', ')}."""\n    # tables arrive filtered as t.<table> (pandas). ${item.recipe ? `Shaping: ${item.recipe}` : ''}\n    rows = []\n    return {"data": {"rows": rows}, "metrics": {}}\n`;
}

// ---- a report (optional)
let reportFile = null;
if (val('report')) {
  reportFile = path.join(ROOT, 'Reports', `${val('report')}.json`);
  if (!fs.existsSync(reportFile)) fail(`no report Reports/${val('report')}.json`);
  if (!Array.isArray(readJsonFile(reportFile).sections)) fail(`Reports/${val('report')}.json lists "tabs" or "reportTabs", not "sections"; add ${id} by hand`);
}

// ---- write, then fill the copy with the real numbers once
fs.writeFileSync(path.join(SECTIONS, `${id}.jsx`), sectionFile([]));
if (newIndex) fs.writeFileSync(INDEX, newIndex);
if (stub) fs.writeFileSync(analysisFile, analysisSrc);
if (reportFile) {
  const rep = readJsonFile(reportFile);
  rep.sections.push(id);
  fs.writeFileSync(reportFile, `${JSON.stringify(rep, null, 2)}\n`);
}

let result = {};
const shown = spawnSync(pythonCommand(), [path.join('Analysis', 'check.py'), '--show', id], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
try {
  result = JSON.parse(shown.stdout);
} catch {
  result = { error: (shown.stderr || shown.stdout || 'no output').trim().split('\n').slice(-2).join(' | ') };
}
const rows = result.data?.rows ?? [];
const metrics = result.metrics ?? {};
const warnings = [];
if (result.error) warnings.push(`the numbers failed: ${result.error}`);
if (isChart) warnings.push(...fillChart(option, stub ? [] : rows, { slots: Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, v.length === 1 && !kindOf[k]?.count?.includes('more') ? v[0] : v])), names, format }, { first: true }));

const fmt = format[ys[0]] === '$short' ? 'compact' : format[ys[0]] === 'comma' ? 'int' : format[ys[0]] === '$comma' ? 'money' : 'short';
const pool = between
  ? [`{end_label|name}: {end|${fmt}}, {change|change} on {start_label|name} ({start|${fmt}}).`,
    ...(shape === 'waterfall' ? [`{largest_step_label|name} moved most: {largest_step|${fmt}}.`] : [])]
  : totals ? [] : isTime
  ? [`{latest|${fmt}} in {latest_label|month}, {change|change} {change_label|name}.`, `Highest: {largest_label|month}, with {largest|${fmt}}.`]
  : [`{largest_label|name} is largest, with {largest|${fmt}}${AGG === 'mean' ? '' : ' ({largest_share|pct:0} of the total)'}.`, `{smallest_label|name} is smallest, with {smallest|${fmt}}.`];
const given = val('note') ? val('note').split(/\s+\|\s+/).map((l) => l.trim()).filter(Boolean) : null;
const noteLines = (given ?? pool).filter((l) => [...l.matchAll(/\{([^{}|]+)\|/g)].every((m) => m[1].trim() in metrics));
if (given && noteLines.length < given.length) warnings.push(`--note lines using metrics this section lacks were left out (metrics: ${Object.keys(metrics).join(', ') || 'none'})`);
fs.writeFileSync(path.join(SECTIONS, `${id}.jsx`), sectionFile(noteLines));

// ---- what to reword
const say = (s) => console.log(s);
say(`${id}: Src/Sections/${id}.jsx (${item.id} ${item.name}${tab ? `, tab ${tab}` : ''}${addTab ? ', a new tab' : ''})`);
if (stub) say(`  write its numbers: ${path.basename(analysisFile)} in Analysis/ (rows with the columns ${Object.keys(slots).join(', ')})`);
if (did) say(`  numbers: ${did}`);
say('Reword in that file:');
say(`  title: ${title}`);
for (const l of noteLines) say(`  note: - ${l}`);
for (const [c, n] of Object.entries(names)) if (!['base', 'rise', 'fall', 'total', 'key', 'share'].includes(c) && (n === human(c) || n === nameOf(c))) say(`  names: ${c} shows as "${n}" (column words; write the reader's)`);
if (basis) say(`  basis: ${basis}`);
for (const a of isChart ? ['xAxis', 'yAxis'].flatMap((k) => [].concat(option[k] ?? [])) : []) if (a?.name) say(`  axis name: ${a.name}`);
const literals = [];
const walk = (x) => {
  if (Array.isArray(x)) x.forEach(walk);
  else if (x && typeof x === 'object') for (const [k, v] of Object.entries(x)) if (k !== 'data') (k === 'formatter' && typeof v === 'string' && !v.includes('{') ? literals.push(v) : walk(v));
};
walk(option);
for (const l of new Set(literals)) say(`  label: ${l}`);
if (html) for (const w of SAMPLE_WORDS) for (const m of html.matchAll(new RegExp(`>([^<>]*${w}[^<>]*)<`, 'g'))) say(`  html: ${m[1].trim()}`);
for (const w of warnings) say(`  check: ${w}`);
if (!defaultBlock) say(`  check: add ${id} to Src/Sections/index.js by hand`);
