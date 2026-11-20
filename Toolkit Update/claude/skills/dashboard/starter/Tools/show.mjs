// npm run show -- <ID> [--library <folder>]
// One design library item's parts, never its code: what it is, each part (slot) it takes, its recipe, the columns of
// this dashboard's tables that fit each part, and a new-section command ready to copy.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, pythonCommand } from './py.mjs';
import { findLibrary, itemJs } from './library.mjs';

const argv = process.argv.slice(2);
const at = argv.indexOf('--library');
const id = argv.find((a, i) => !a.startsWith('--') && argv[i - 1] !== '--library')?.toUpperCase();
if (!id || !/^(CT|TB|HC)-\d\d$/.test(id)) {
  console.log('show: give a chart, table or hero card id, e.g. npm run show -- CT-34 (the ids are in the library\'s index/charts.md, index/tables.md, index/hero-cards.md)');
  process.exit(1);
}
const lib = findLibrary(at >= 0 ? argv[at + 1] : null);
const item = itemJs(lib, [id, '--json'])[0];
if (!item) {
  console.log(`show: no item ${id} in the library`);
  process.exit(1);
}
const say = (s = '') => console.log(s);
const cut = (s, n) => (s.length > n ? `${s.slice(0, n - 3)}...` : s);
const note = item.data ?? [];
const pad = Math.max(6, ...note.map((s) => s.name.length)) + 2;
const kindText = { text: 'text', number: 'number', figure: 'one number' };
const countText = {
  one: 'required, one column', 'one or more': 'required, one or more columns', optional: 'optional, one column', any: 'optional, any number of columns',
};
// slots the recipe gives a rule for: worked out first, by new-section where it can (the same list as new-section's)
const kinds = Object.fromEntries(note.map((s) => [s.name, s]));
const rules = {};
for (const part of String(item.recipe ?? '').split(';')) {
  const m = /^\s*([a-z][a-z0-9-]*(?:\s*,\s*[a-z][a-z0-9-]*)*)\s*[:=]\s*(.+)$/.exec(part);
  if (m) for (const n of m[1].split(',').map((x) => x.trim())) if (kinds[n]) rules[n] = m[2].trim();
}
const waterfall = Boolean(kinds.base && kinds.total);
const auto = {};   // slot -> how new-section works it out
if (waterfall) for (const k of ['base', 'rise', 'fall', 'key']) if (kinds[k]) auto[k] = 'worked out by new-section from step and total';
if (rules.low && rules.gap) for (const k of ['low', 'gap', 'high', 'range']) if (kinds[k]) auto[k] = 'worked out by new-section from start and end';
if (rules.running) auto.running = 'worked out by new-section from variance (a running total)';
if (rules.share && /running/.test(rules.share)) auto.share = 'worked out by new-section from value (the running share)';
const percent = Boolean(rules.part && /%/.test(rules.part));
say(`${item.id} ${item.name} (${item.type})`);
say(cut(String(item.purpose ?? '').replace(/^Use (it )?to /i, 'For: ').replace(/^Use for /i, 'For: '), 118));
say('Parts (each is a --slot):');
for (const s of note) {
  const how = auto[s.name] ? ` - ${auto[s.name]}` : percent && s.name === 'part' ? ' - give the amounts; new-section turns them into % of each period'
    : rules[s.name] ? ` - WORK OUT FIRST: ${cut(rules[s.name], 70)}` : '';
  say(`  ${s.name.padEnd(pad)}${kindText[s.kind]}, ${s.kind === 'figure' ? (s.count === 'optional' ? 'optional' : 'required') + ': a number, or a column whose first value is used' : countText[s.count]}${how}`);
}
const manualSlots = note.filter((s) => rules[s.name] && !auto[s.name] && !(percent && s.name === 'part') && s.kind !== 'text');
if (manualSlots.length) say(`  (${manualSlots.map((s) => s.name).join(', ')}: a column holding that already, or numbers written by hand; add-a-section.md)`);
else if (item.recipe && !Object.keys(rules).length) say(`Recipe: ${cut(item.recipe, 110)}`);

// this dashboard's tables
const r = spawnSync(pythonCommand(), [path.join('Analysis', 'check.py'), '--describe-only'], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
let tables = null;
try {
  tables = JSON.parse(r.stdout).describe;
} catch { /* no data yet */ }
if (!tables || !Object.keys(tables).length) {
  say('No tables in this dashboard yet: load data first (add-data-and-filters.md), then run this again for columns.');
  process.exit(0);
}
const [table, t] = Object.entries(tables)[0];
const cols = t.columns;
const rank = (c) => (cols[c].type !== 'text' ? 100 : cols[c].distinct > 200 ? 100000 + cols[c].distinct : cols[c].distinct);
const text = Object.keys(cols).filter((c) => ['text', 'date', 'month'].includes(cols[c].type)).sort((a, b) => rank(a) - rank(b));
const timeSlot = (name) => /period|month|quarter|year|date|week|day/.test(name);
const nums = Object.keys(cols).filter((c) => cols[c].type === 'number');
const textLabel = (c) => (cols[c].type === 'text' ? `${c} (${cols[c].distinct ?? '?'} values${cols[c].distinct > 200 ? ', add --top N' : ''})` : `${c} (${cols[c].type}${cols[c].type === 'date' ? ', grouped by month' : ''})`);
const others = Object.keys(tables).slice(1);
say(`Columns that fit, from table ${table}${others.length ? ` (other tables: ${others.join(', ')}; npm run status lists theirs)` : ''}:`);
for (const s of note) {
  if (auto[s.name]) continue;
  const order = s.kind === 'text' && timeSlot(s.name) ? [...text].sort((a, b) => (cols[a].type === 'text') - (cols[b].type === 'text')) : text;
  const fit = s.kind === 'text' ? order.map(textLabel) : [...nums, s.kind === 'number' ? 'rows (counts rows)' : null].filter(Boolean);
  say(`  ${s.name.padEnd(pad)}${cut(fit.join(', ') || '(none)', 104)}`);
}


// a command to copy: required parts only, the best-fitting column for each
const index = fs.existsSync(path.join(ROOT, 'Src', 'Sections', 'index.js')) ? fs.readFileSync(path.join(ROOT, 'Src', 'Sections', 'index.js'), 'utf8') : '';
const tab = /id\s*:\s*['"]([^'"]+)['"]/.exec(/export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]/.exec(index)?.[1] ?? '')?.[1] ?? 'overview';
const goodText = text.find((c) => cols[c].type === 'text' && cols[c].distinct > 1 && cols[c].distinct <= 50) ?? text[0];
const parts = [];
let n = 0;
for (const s of note) {
  const required = s.count === 'one' || s.count === 'one or more';
  if (!required || auto[s.name] || (rules[s.name] && s.kind !== 'text' && !(percent && s.name === 'part'))) continue;   // never a raw column on a worked-out part
  if (s.kind === 'text') parts.push(`--slot ${s.name}=${(timeSlot(s.name) && text.find((c) => cols[c].type !== 'text')) || goodText || '<text column>'}`);
  else if (s.kind === 'figure') parts.push(`--slot ${s.name}=<number>`);
  else parts.push(`--slot ${s.name}=${nums[n++] ?? nums[0] ?? 'rows'}`);
}
say(`Copy (change the name and columns as needed; optional parts${manualSlots.some((s) => s.count === 'one' || s.count === 'one or more') ? ' and parts to work out first' : ''} are left out):`);
say(`  npm run new-section -- ${item.name.replace(/[^a-z0-9]+/gi, '_')} --use ${item.id} --page ${tab} --tables ${table} ${parts.join(' ')}`);
