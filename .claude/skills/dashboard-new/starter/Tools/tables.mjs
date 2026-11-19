// npm run tables -- --sections <id,id> [--by <filter column,column>] [--out <file>]
// Scenario tables for the commentary skill: for each section and each scenario (every value of the --by filters
// that reach it, plus "all"), its data and metrics, the scenario's filters, and already_on_page: the notes a reader
// already sees on that tab in that scenario (so commentary adds to them instead of repeating them).
// Default file: Data/.tables/tables-<date-time>-<process id>.json (a new name each run). Prints its path.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import * as format from '../Src/Lib/format.js';
import { ROOT, pythonCommand } from './py.mjs';

const argv = process.argv.slice(2);
const opt = (name) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : null;
};
const fail = (msg) => {
  console.log(`tables: ${msg}`);
  process.exit(1);
};
if (!opt('sections')) fail('npm run tables -- --sections <id,id> [--by <filter column,column>] [--out <file>]');

const py = spawnSync(pythonCommand(), [path.join('Analysis', 'check.py'), '--tables', '--sections', opt('sections'), '--by', opt('by') ?? ''],
  { cwd: ROOT, encoding: 'utf8', maxBuffer: 512 * 1024 * 1024 });
let data;
try {
  data = JSON.parse(py.stdout);
} catch {
  fail((py.stderr || py.stdout || 'no output').trim().split('\n').slice(-3).join(' | '));
}
if (data.error) fail(data.error);

const reg = spawnSync(process.execPath, [path.join(ROOT, 'Tools', 'registry.mjs')], { cwd: ROOT, encoding: 'utf8' });
const sections = JSON.parse(reg.stdout.trim().split('\n').at(-1)).sections ?? [];
const notes = Object.fromEntries(sections.filter((s) => typeof s.note === 'string' && s.note.trim()).map((s) => [s.meta.id, s.note.trim()]));
const render = (md, metrics) => format.renderNote(md, metrics).blocks
  .map((b) => (b.type === 'list' ? b.items.map((segs) => segs.map((s) => s.text).join('')).join(' ') : b.segments.map((s) => s.text).join('')))
  .join(' ');

let count = 0;
for (const sec of Object.values(data.sections)) {
  for (const sc of sec.scenarios) {
    count += 1;
    sc.already_on_page = Object.fromEntries(Object.entries(sc.on_page ?? {}).filter(([id]) => notes[id]).map(([id, m]) => [id, render(notes[id], m)]));
    delete sc.on_page;
  }
}

const stamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15);
const out = path.resolve(ROOT, opt('out') ?? path.join('Data', '.tables', `tables-${stamp}-${process.pid}.json`));
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, `${JSON.stringify(data, null, 1)}\n`);
console.log(`tables: wrote ${out} (${Object.keys(data.sections).length} section(s), ${count} scenario(s))`);
