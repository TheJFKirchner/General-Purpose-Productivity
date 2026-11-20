// npm run status [-- --json]
// A read-only map of this dashboard, enough to add or change a section without opening other files: each tab's
// sections in order (title, chart, analytic function and file, tables, filters, metric names, what its note says),
// every table's columns (type, a sample, the range of date and month columns), filters, commentary, reports (and
// which of their sections a locked filter does not narrow), and the check result. Notes that changed since the
// last status are listed (after a refresh: tell the user). Changes nothing.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, loadProject, readJson, reportSectionIds, validateProject } from './project.mjs';

const asJson = process.argv.includes('--json');
const problems = [];
const safe = (fn, fallback) => {
  try {
    return fn();
  } catch (e) {
    problems.push(e.message);
    return fallback;
  }
};
const config = safe(() => readJson('dashboard.config.json'), {});
let p = null;
try {
  p = await loadProject({ describe: true });
} catch (e) {
  problems.push(`could not load the sections (Src/Sections/index.js): ${e.message}`);
}

const render = (note, metrics) => p.format.renderNote(note.trim(), metrics).blocks
  .map((b) => (b.type === 'list' ? b.items.map((s) => `- ${s.map((x) => x.text).join('')}`).join(' ') : b.segments.map((x) => x.text).join(''))).join(' ');
const result = p ? validateProject(p) : { errors: [], warnings: [], cardErrors: {} };
const sections = (p?.registry ?? []).map((m) => {
  const id = m.meta?.id;
  const a = p.cards[id] ?? {};
  const src = safe(() => fs.readFileSync(path.join(ROOT, 'Src', 'Sections', `${id}.jsx`), 'utf8'), '');
  return {
    id, title: m.meta?.title, tab: m.meta?.tab ?? null, chart: m.meta?.library, size: m.meta?.size ?? 'full',
    analytic: a.module === '(meta)' ? 'numbers from its meta' : a.module ? `${a.function ?? '?'}() in Analysis/${a.module}.py` : '(no analytic)',
    chartKind: m.meta?.use ?? m.meta?.chart ?? m.meta?.library, description: m.meta?.description ?? '(no description)',
    tables: a.tables ?? [], filters: a.filters ?? [], metrics: Object.keys(a.metrics ?? {}), commentary: m.meta?.commentary ?? null,
    built: !/Not built yet\./.test(src), problems: result.cardErrors[id] ?? [],
    says: m.note && a.metrics && !a.error ? render(m.note, a.metrics) : null,
  };
});
const described = p?.analysis?.describe ?? {};
const manifest = p?.manifest?.tables ?? {};
const reports = [];
const rdir = path.join(ROOT, 'Reports');
for (const f of fs.existsSync(rdir) ? fs.readdirSync(rdir).filter((x) => x.endsWith('.json') && !x.startsWith('_')) : []) {
  const r = safe(() => readJson(`Reports/${f}`), null);
  if (!r) continue;
  const ids = p ? reportSectionIds(r, p) : r.sections ?? [];
  const locked = Object.entries(r.filters ?? {}).filter(([, s]) => s?.locked && s.value !== undefined && String(s.value) !== 'All');
  const notNarrowed = locked.flatMap(([n, s]) => ids.filter((id) => p?.cards[id] && !(p.cards[id].filters ?? []).includes(n)).map((id) => `${id} (${n}=${s.value})`));
  reports.push({ name: f.replace(/\.json$/, ''), sections: ids, script: r.script ?? null, locked: locked.map(([n, s]) => `${n}=${s.value}`), notNarrowed });
}

// notes that changed since the last status
const saidFile = path.join(ROOT, 'Data', '.status-notes.json');
const said = Object.fromEntries(sections.filter((s) => s.says).map((s) => [s.id, s.says]));
const before = fs.existsSync(saidFile) ? safe(() => JSON.parse(fs.readFileSync(saidFile, 'utf8')), null) : null;
const changed = before ? Object.entries(said).filter(([id, s]) => before[id] !== undefined && before[id] !== s) : [];
if (Object.keys(said).length && fs.existsSync(path.join(ROOT, 'Data'))) fs.writeFileSync(saidFile, `${JSON.stringify(said, null, 1)}\n`);

if (asJson) {
  console.log(JSON.stringify({ title: config.title, tabs: p?.tabs ?? [], sections, tables: described, filters: p?.FILTERS ?? {}, reports, changed, check: result, problems }, null, 2));
  process.exit(0);
}

const line = (s = '') => console.log(s);
line(`${config.title ?? '(untitled)'}   (theme ${config.theme}; analysis server port ${config.server?.port ?? 8765})`);
line(`Check: ${result.errors.length ? `${result.errors.length} error(s)` : 'OK'}, ${result.warnings.length} warning(s)`);
for (const e of result.errors) line(`  ERROR ${e}`);
for (const w of result.warnings.slice(0, 3)) line(`  warn  ${w}`);
if (result.warnings.length > 3) line(`  ... ${result.warnings.length - 3} more: npm run check`);
const groups = p?.tabs?.length ? p.tabs.map((t) => [`Tab ${t.id} "${t.label}"`, sections.filter((s) => s.tab === t.id)]) : [['Sections', sections]];
for (const [head, list] of groups) {
  line();
  line(head);
  if (!list.length) line('  none yet: npm run new-section -- <name> ...');
  for (const s of list) {
    const flags = [s.size === 'half' ? 'half' : null, s.built ? null : 'NOT BUILT', s.problems.length ? `${s.problems.length} problem(s)` : null, s.commentary ? `commentary ${s.commentary}` : null].filter(Boolean);
    line(`  ${s.id}  ${s.id}.jsx  "${s.title}"  ${s.chartKind}  ${s.tables.join(', ') || '-'}  ${s.description}${flags.length ? `  [${flags.join(', ')}]` : ''}`);
    line(`      ${s.analytic}; filters ${s.filters.join(', ') || 'none'}; metrics ${s.metrics.join(', ') || 'none'}`);
    if (s.says) line(`      says: ${s.says}`);
  }
}
line();
line('Tables');
if (!Object.keys(described).length) line('  none yet: one write_source line per input file in Pipeline/sources.py, then npm run pipeline');
for (const [name, t] of Object.entries(described)) {
  const e = manifest[name] ?? {};
  line(`  ${name}  ${t.rows.toLocaleString('en-US')} rows, as of ${e.as_of || 'none'}, ${e.script ? `from Pipeline/${e.script}` : `file ${e.path ?? '?'}`}${e.source && e.script ? ` (${e.source})` : ''}`);
  line(`      ${Object.entries(t.columns).map(([c, i]) => `${c} ${i.type} ${i.range ? `${i.range[0]}..${i.range[1]}` : i.sample}`).join('; ')}`);
}
line();
const F = p?.FILTERS ?? {};
line(`Filters: ${Object.keys(F).length ? Object.entries(F).map(([k, f]) => `${k} (${f.section ? `section ${f.section}` : f.tab ? `tab ${f.tab}` : 'dashboard'}, ${f.options.length - 1} values)`).join(', ') : 'none'}`);
const items = p?.commentaryItems;
line(`Commentary: ${Array.isArray(items) ? (items.length ? `${new Set(items.map((i) => i?.id)).size} id(s) in commentary.json` : 'none') : `commentary.json ${items?.error ?? 'unreadable'}`}`);
line(`Reports: ${reports.length ? '' : 'none'}`);
for (const r of reports) {
  line(`  ${r.name}: ${r.sections.join(', ')}${r.script ? `; python Reports/${r.script}` : ''}${r.locked.length ? `; locks ${r.locked.join(', ')}` : ''}`);
  if (r.notNarrowed.length) line(`      not narrowed by its locked filter: ${r.notNarrowed.join(', ')}`);
}
if (changed.length) {
  line();
  line('Changed since the last status (tell the user):');
  for (const [id, s] of changed) line(`  ${id}: was "${before[id]}"\n  ${''.padEnd(id.length)}  now "${s}"`);
}
for (const pr of problems) line(`PROBLEM ${pr}`);
