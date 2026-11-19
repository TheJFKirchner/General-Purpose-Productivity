// npm run new-section -- <name> --page <tab> --tables <table> --chart bar|line|table|kpi --x <col> --y <col>
//                          [--agg sum|count|mean] [--by <col>] [--title "..."] [--desc "..."] [--bullets 2]
//                          [--note "first bullet | second bullet"] [--compare year|prev] [--keep-filter]
//                          [--size half] [--report <name>]
// Writes a WORKING section as one file, Src/Sections/<id>.jsx: its meta (title, tab, tables, description, and the
// numbers it needs: x, y, agg, by), a finished chart, table or KPI tiles in the house style, and a note of --bullets
// lines that already use real metrics; plus its line in Src/Sections/index.js. The numbers are worked out in Python
// from the meta (Analysis/Shared/shapes.py), so there is no Python to write. npm run check passes straight after.
// Left to do: reword the note.
//   --x        the category or month column (a month column gives a time axis and latest/change metrics)
//   --y        the value column (not needed with --agg count, which counts rows)
//   --by       a second column: one series per value (stacked bars, lines or table columns)
//   --desc     8 to 10 words on what it shows (default: made from the other options)
//   --note     the note's bullets, separated by " | " (spaces around); {metric|format} placeholders allowed
//   --compare  for a month x: change on the same month a year earlier (year; default when a year of history
//              exists) or on the month before (prev)
//   --keep-filter  let a filter on the --x or --by column narrow the section (by default it doesn't: the section
//              compares those values, and the page tags it "Region: all")
//   --report   also add the section to Reports/<name>.json
// Anything unusual (several tables, a report analytic, an odd calculation or chart) is a hand edit: without --x it
// writes a shell with an analytic stub; see dashboard-work references/sections.md, below STOP HERE.
// Never overwrites anything.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ROOT, pythonCommand, readJsonFile } from './py.mjs';

const SECTIONS = path.join(ROOT, 'Src', 'Sections');
const INDEX = path.join(SECTIONS, 'index.js');
const ANALYSIS = path.join(ROOT, 'Analysis');
const SHAPES = ['bar', 'line', 'table', 'kpi'];
const MONEY = /paid|amount|cost|revenue|price|spend|allowed|charge|premium|sales|value|usd|\$/i;

function fail(msg) {
  console.log(`new-section: ${msg}`);
  process.exit(1);
}

// ---- arguments
const argv = process.argv.slice(2);
const opts = {};
const positional = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a.startsWith('--')) {
    const [k, inline] = a.slice(2).split('=', 2);
    opts[k] = inline ?? (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true');
  } else positional.push(a);
}
if (!positional.length || opts.help) {
  console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').filter((l) => l.startsWith('//')).map((l) => l.slice(3)).join('\n'));
  process.exit(positional.length ? 0 : 1);
}
const val = (k) => (opts[k] && opts[k] !== 'true' ? String(opts[k]) : null);
const chart = (val('chart') ?? 'bar').toLowerCase();
if (!SHAPES.includes(chart)) fail(`--chart must be one of ${SHAPES.join(', ')} (got "${chart}"); other charts are a hand edit (dashboard-work references/sections.md)`);
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
const tables = (val('tables') ?? '').split(',').map((x) => slug(x.trim())).filter(Boolean);
const X = val('x');
const Y = val('y');
const BY = val('by');
const AGG = (val('agg') ?? (Y ? 'sum' : 'count')).toLowerCase();
const bullets = Math.max(0, Math.min(5, Number(val('bullets') ?? 2) || 0));
if (!['sum', 'count', 'mean'].includes(AGG)) fail(`--agg must be sum, count or mean (got "${AGG}")`);
const built = Boolean(X);
if (built && !tables.length) fail('--tables <table> is needed with --x');
if (built && AGG !== 'count' && !Y) fail('--y <column> is needed (or --agg count to count rows)');

// ---- the table and its columns (checked against the data)
let col = {};
if (built) {
  const r = spawnSync(pythonCommand(), [path.join('Analysis', 'check.py'), '--describe-only'], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  let described;
  try {
    described = JSON.parse(r.stdout).describe;
  } catch {
    fail(`could not read the tables: ${(r.stderr || r.stdout || '').trim().split('\n').slice(-2).join(' | ') || 'no output'}`);
  }
  if (!described) fail('no tables yet: load the data first (npm run pipeline)');
  const t = described[tables[0]];
  if (!t) fail(`no table "${tables[0]}" (tables: ${Object.keys(described).join(', ') || 'none'})`);
  for (const [flag, c] of [['--x', X], ['--y', AGG === 'count' ? null : Y], ['--by', BY]]) {
    if (c && !t.columns[c]) fail(`no column "${c}" (${flag}) in ${tables[0]} (columns: ${Object.keys(t.columns).join(', ')})`);
  }
  if (Y && AGG !== 'count' && t.columns[Y].type !== 'number') fail(`--y ${Y} is ${t.columns[Y].type}, not a number; use --agg count to count rows`);
  col = t.columns;
}
const isMonth = built && ['month', 'date'].includes(col[X]?.type);
const money = AGG !== 'count' && MONEY.test(Y ?? '');
const fmt = money ? 'compact' : AGG === 'mean' ? 'num' : AGG === 'count' ? 'int' : 'short';
const span = (() => {   // months covered by a month x, from its range
  const r = col[X]?.range;
  return isMonth && r ? (Number(r[1].slice(0, 4)) - Number(r[0].slice(0, 4))) * 12 + Number(r[1].slice(5, 7)) - Number(r[0].slice(5, 7)) + 1 : 0;
})();
const compare = isMonth ? (val('compare') ?? (span >= 13 ? 'year' : 'prev')).toLowerCase() : null;
if (compare && !['year', 'prev'].includes(compare)) fail(`--compare must be year or prev (got "${compare}")`);
const human = (s) => String(s).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
const valueLabel = AGG === 'count' ? human(tables[0] ?? 'rows') : `${AGG === 'mean' ? 'Average ' : ''}${AGG === 'mean' ? String(Y).replace(/_/g, ' ') : human(Y)}`;

// ---- what exists already
const fillBlock = (block, body) => block.slice(0, block.indexOf('[') + 1) + body + block.slice(block.lastIndexOf(']'));
const read = (f) => (fs.existsSync(f) ? fs.readFileSync(f, 'utf8').replace(/^\uFEFF/, '') : '');
const indexSrc = read(INDEX);
if (!indexSrc) fail('Src/Sections/index.js not found (run this inside a dashboard folder)');
const sectionFiles = fs.readdirSync(SECTIONS).filter((f) => /^s\d+_.*\.jsx$/.test(f));
const analysisFiles = fs.readdirSync(ANALYSIS).filter((f) => f.endsWith('.py'));
const analysisIds = analysisFiles.flatMap((f) => [...read(path.join(ANALYSIS, f)).matchAll(/@(?:card|section)\(\s*["'](s\d+_[a-z0-9_]+)["']/g)].map((m) => m[1]));
const usedIds = new Set([...sectionFiles.map((f) => f.replace(/\.jsx$/, '')), ...analysisIds]);
const usedNumbers = new Set([...usedIds].map((id) => Number(/^s(\d+)_/.exec(id)[1])));

// ---- the section id
let id = positional[0];
if (!/^s\d+_[a-z0-9_]+$/.test(id)) {
  const name = slug(id);
  if (!name) fail(`"${id}" doesn't make a usable name (use letters and numbers, e.g. paid_by_region)`);
  id = `s${Math.max(0, ...usedNumbers) + 1}_${name}`;
}
const number = Number(/^s(\d+)_/.exec(id)[1]);
if (usedIds.has(id)) fail(`${id} already exists (Src/Sections/${id}.jsx or an @section("${id}") in Analysis/)`);
if (usedNumbers.has(number)) fail(`the number s${number} is already used; leave the number off and one is picked`);
const shortName = id.replace(/^s\d+_/, '');
const title = val('title') ?? (built ? `${valueLabel} by ${String(X).replace(/_/g, ' ')}${BY ? ` and ${BY.replace(/_/g, ' ')}` : ''}` : human(shortName));

// ---- tabs
const tabsBlock = /export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]\s*;/.exec(indexSrc);
const tabIds = tabsBlock ? [...tabsBlock[1].matchAll(/id\s*:\s*['"]([^'"]+)['"]/g)].map((m) => m[1]) : [];
const defaultBlock = /export\s+default\s+\[([\s\S]*?)\]\s*;/.exec(indexSrc);
const hasSections = defaultBlock ? /[A-Za-z_]/.test(defaultBlock[1].replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '')) : sectionFiles.length > 0;
const page = val('page') ? slug(val('page')) : null;
let tab = null;
let addTab = null;
const notes = [];
if (tabIds.length) {
  tab = page ?? tabIds[0];
  if (!tabIds.includes(tab)) addTab = tab;
} else if (page) {
  if (hasSections) notes.push(`this dashboard has one page (no tabs), so the section goes on it; "${page}" only names its Analysis file.`);
  else (tab = page), (addTab = page);
}
const analysisName = page ?? tab ?? 'overview';
const analysisFile = path.join(ANALYSIS, `${analysisName}.py`);
if (['server', 'check', 'precompute'].includes(analysisName) || analysisName.startsWith('_')) fail(`"${analysisName}" can't be a tab name (it's reserved)`);
let config = {};
try {
  config = readJsonFile(path.join(ROOT, 'dashboard.config.json'));
} catch (e) {
  fail(e.message);
}
// a filter on the column the section compares would leave one bar: it doesn't narrow the section (unless --keep-filter)
// the same numbers already on the dashboard? (sections that declare them in their meta)
const metaVal = (body, k) => new RegExp(`(?<![\\w$])${k}\\s*:\\s*['"]([^'"]*)['"]`).exec(body)?.[1] ?? null;
const twin = !built ? null : sectionFiles.find((f) => {
  const body = /export\s+const\s+meta\s*=\s*\{([^}]*)\}/.exec(read(path.join(SECTIONS, f)))?.[1] ?? '';
  const tb = /(?<![\w$])tables\s*:\s*\[\s*['"]([^'"]+)['"]/.exec(body)?.[1];
  const agg = metaVal(body, 'agg') ?? (metaVal(body, 'y') ? 'sum' : 'count');
  return tb === tables[0] && metaVal(body, 'x') === X && agg === AGG && (AGG === 'count' || metaVal(body, 'y') === Y);
});
if (twin) notes.push(`${twin.replace(/\.jsx$/, '')} already shows ${AGG} of ${AGG === 'count' ? 'rows' : Y} by ${X} from ${tables[0]}; ask the user before keeping both`);
const ignore = built && opts['keep-filter'] === undefined
  ? Object.entries(config.filters ?? {}).filter(([k, f]) => !k.startsWith('_') && [X, BY].includes(f?.column ?? k)).map(([k]) => k)
  : [];

// ---- the analytic: none for a built section (its meta declares the numbers); a stub for a hand-written one
const py = (v) => JSON.stringify(v);
const pyList = (xs) => `[${xs.map(py).join(', ')}]`;
let analysisSrc = read(analysisFile);
const defNames = new Set([...analysisSrc.matchAll(/^def\s+([A-Za-z_]\w*)/gm)].map((m) => m[1]));
let fnName = /^[a-z_]/.test(shortName) ? shortName : `section_${shortName}`;
for (let i = 2; defNames.has(fnName); i++) fnName = `${shortName}_${i}`;
const header = analysisSrc ? '' : `"""${analysisName.replace(/_/g, ' ')}: the analytics for this tab's sections (one function per section)."""\nfrom Shared.registry import section\n`;
if (analysisSrc && !/from\s+Shared\.registry\s+import[^\n]*\bsection\b/.test(analysisSrc)) analysisSrc = `from Shared.registry import section\n${analysisSrc}`;
const fn = `\n\n@section("${id}", tables=${pyList(tables)})\ndef ${fnName}(t):\n    """${title}. Not built yet."""\n    # read tables as t.<table name> (pandas, filters already applied); see dashboard-work: references/sections.md\n    return {"data": {}, "metrics": {}}\n`;
const metricNames = !built ? [] : [
  AGG === 'mean' ? 'average' : 'total', 'largest', 'largest_label',
  ...(isMonth ? ['latest', 'latest_label', 'change', 'change_label'] : [...(AGG === 'mean' ? [] : ['largest_share']), 'smallest', 'smallest_label']),
  'count', ...(BY && AGG !== 'mean' ? ['top_series', 'top_series_share'] : []),
];
const aggWord = { sum: 'summed', count: 'counted', mean: 'averaged' }[AGG];
const desc = val('desc') ?? `${valueLabel} by ${String(X ?? shortName).replace(/_/g, ' ')}${BY ? ` and ${BY.replace(/_/g, ' ')}` : ''}, ${aggWord}, as ${{ bar: 'bars', line: 'a line', table: 'a table', kpi: 'KPI tiles' }[chart]}`;
if (desc.split(/\s+/).length > 14) notes.push('--desc is long; 8 to 10 words read best in npm run status');

// ---- the note: bullets that already use real metrics
const F = `|${fmt}${fmt === 'num' ? ':1' : ''}`;
const noun = AGG === 'count' ? ` ${String(tables[0]).replace(/_/g, ' ')}` : '';   // "195 claims"; amounts carry their own $
const v = (m) => `{${m}${F}}${noun}`;
const pool = isMonth
  ? [`${v('latest')} in {latest_label|month}, {change|change} {change_label|name}.`,
    `Highest: {largest_label|month}, with ${v('largest')}.`,
    ...(BY && AGG !== 'mean' ? ['{top_series|name} is the largest part, {top_series_share|pct:0} of the total.'] : []),
    AGG === 'mean' ? 'Across {count|int} months.' : `${v('total')} over {count|int} months.`]
  : [`{largest_label|name} is largest, with ${v('largest')}${AGG === 'mean' ? '' : ' ({largest_share|pct:0} of the total)'}.`,
    `{smallest_label|name} is smallest, with ${v('smallest')}.`,
    ...(BY && AGG !== 'mean' ? ['{top_series|name} is the largest part, {top_series_share|pct:0} of the total.'] : [])];
const given = val('note') ? val('note').split(/\s+\|\s+/).map((l) => l.trim()).filter(Boolean) : null;
const noteLines = !built ? [] : given ?? Array.from({ length: bullets }, (_, i) => pool[i] ?? pool.at(-1));
for (const l of given ?? []) {
  for (const [, ref] of l.matchAll(/\{([^{}|]+)\|[^{}]*\}/g)) {
    if (!metricNames.includes(ref.trim())) fail(`--note uses {${ref}}, not a metric of this section (metrics: ${metricNames.join(', ')})`);
  }
}

// ---- the look
const shapeKeys = built ? `, tables: ${py(tables.slice(0, 1))}, x: ${py(X)}${AGG !== 'count' ? `, y: ${py(Y)}` : ''}, agg: '${AGG}'${BY ? `, by: ${py(BY)}` : ''}${compare ? `, compare: '${compare}'` : ''}${ignore.length ? `, ignore: ${py(ignore)}` : ''}` : `, tables: ${py(tables)}`;
const meta = `export const meta = {\n  id: '${id}', title: ${py(title)}${tab ? `, tab: '${tab}'` : ''}, chart: '${chart}', library: '${built && (chart === 'bar' || chart === 'line') ? 'echarts' : built ? 'none' : 'echarts'}'${val('size') === 'half' ? ", size: 'half'" : ''},\n  description: ${py(desc)},\n  ${shapeKeys.slice(2)},\n};`;
const noteSrc = noteLines.length ? `export const note = \`\n${noteLines.map((l) => `- ${l.replace(/`/g, '\\`').replace(/\$\{/g, '\\${')}`).join('\n')}\n\`;` : 'export const note = ``;';
const horizontal = chart === 'bar' && !isMonth;
const looks = {
  bar: `export default function Section({ data }) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'axis', valueFormatter: fmt },${BY ? "\n    legend: { top: 0 }," : ''}
    grid: { left: ${horizontal ? 120 : 64}, right: 24, top: ${BY ? 32 : 12}, bottom: 28 },
    ${horizontal ? "yAxis: { type: 'category', inverse: true, data: data.x.map(label) },\n    xAxis: { type: 'value', axisLabel: { formatter: fmt } }," : `xAxis: { type: 'category', data: data.x.map(label) },\n    yAxis: { type: 'value', name: ${py(valueLabel)}, axisLabel: { formatter: fmt } },`}
    series: Object.entries(data.series).map(([name, values]) => ({ name, type: 'bar', data: values${BY ? ", stack: 'total'" : ''} })),
  }), [data]);
  return <ChartECharts option={option} height={${horizontal ? 'Math.max(160, data.x.length * 28 + 48)' : 300}} />;
}`,
  line: `export default function Section({ data }) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'axis', valueFormatter: fmt },${BY ? "\n    legend: { top: 0 }," : ''}
    grid: { left: 64, right: 24, top: ${BY ? 32 : 12}, bottom: 28 },
    xAxis: { type: 'category', data: data.x.map(label), boundaryGap: false },
    yAxis: { type: 'value', name: ${py(valueLabel)}, axisLabel: { formatter: fmt } },
    series: Object.entries(data.series).map(([name, values]) => ({ name, type: 'line', data: values, symbolSize: 5 })),
  }), [data]);
  return <ChartECharts option={option} height={300} />;
}`,
  table: `export default function Section({ data }) {
  const names = Object.keys(data.series);
  return (
    <table className="data">
      <thead><tr><th>${human(X)}</th>{names.map((n) => <th key={n} className="num">{n}</th>)}</tr></thead>
      <tbody>
        {data.x.map((x, i) => (
          <tr key={x}><td>{label(x)}</td>{names.map((n) => <td key={n} className="num">{fmt(data.series[n][i])}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}`,
  kpi: `export default function Section({ metrics }) {
  return (
    <div className="kpis">
      <KpiTile label=${py(AGG === 'mean' ? `Average ${String(Y).replace(/_/g, ' ')}` : `Total ${valueLabel.toLowerCase()}`)} value={metrics.${AGG === 'mean' ? 'average' : 'total'}} format={fmt} />
      <KpiTile label={\`Highest: \${label(metrics.largest_label)}\`} value={metrics.largest} format={fmt} />${isMonth ? `
      <KpiTile label={\`Latest: \${label(metrics.latest_label)}\`} value={metrics.latest} format={fmt} change={metrics.change} changeLabel={metrics.change_label} />` : ''}
    </div>
  );
}`,
};
const imports = {
  bar: "import { useMemo } from 'react';\nimport ChartECharts from '../Components/ChartECharts.jsx';\n",
  line: "import { useMemo } from 'react';\nimport ChartECharts from '../Components/ChartECharts.jsx';\n",
  table: '',
  kpi: "import KpiTile from '../Components/KpiTile.jsx';\n",
};
const jsx = built
  ? `// The section: its meta (x, y, agg, by declare the numbers, worked out in Python), the note and the ${chart}.
// Metrics for the note: ${metricNames.join(', ')}. Commentary (optional): add commentary: 'C1' to meta.
${imports[chart]}import { FORMATS } from '../Lib/format.js';

${meta}

// Reword these lines; keep the {metric|format} parts (they fill in the real numbers).
${noteSrc}

const fmt = (v) => FORMATS.${fmt}(v${fmt === 'num' ? ', 1' : ''});
const label = ${isMonth ? 'FORMATS.month' : '(v) => v'};

${looks[chart]}
`
  : `// Numbers: its analytic in Analysis/${analysisName}.py (${fnName}). A hand edit: dashboard-work references/sections.md.
${meta}

export const note = \`\`;

export default function Section({ data, metrics }) {
  return <p style={{ color: 'var(--text-muted)' }}>Not built yet.</p>;
}
`;

// ---- the registry (index.js)
let newIndex = null;
if (defaultBlock) {
  let src = indexSrc;
  const importLine = `import * as ${id} from './${id}.jsx';`;
  const importsFound = [...src.matchAll(/^import[^\n]*\n/gm)];
  const lead = /^(?:\s*\/\/[^\n]*\n)*/.exec(src)[0].length;
  const at = importsFound.length ? importsFound.at(-1).index + importsFound.at(-1)[0].length : lead;
  src = src.slice(0, at) + importLine + '\n' + src.slice(at);
  if (addTab) {
    const tb = /export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]\s*;/.exec(src);
    if (tb) {
      const inner = tb[1].replace(/\s+$/, '');
      const sep = inner.trim() && !inner.trim().endsWith(',') ? ',' : '';
      src = src.slice(0, tb.index) + fillBlock(tb[0], `${inner}${sep}\n  { id: '${addTab}', label: '${human(addTab)}' },\n`) + src.slice(tb.index + tb[0].length);
    } else notes.push(`add the tab to Src/Sections/index.js by hand: export const tabs = [{ id: '${addTab}', label: '...' }];`);
  }
  const db = /export\s+default\s+\[([\s\S]*?)\]\s*;/.exec(src);
  const inner = db[1].replace(/\s+$/, '');
  const sep = inner.replace(/\/\/.*$/gm, '').trim() && !inner.replace(/\/\/.*$/gm, '').trim().endsWith(',') ? ',' : '';
  src = src.slice(0, db.index) + fillBlock(db[0], `${inner}${sep}\n  ${id},\n`) + src.slice(db.index + db[0].length);
  newIndex = src;
}

// ---- a report (optional)
let reportNote = null;
if (val('report')) {
  const rf = path.join(ROOT, 'Reports', `${val('report')}.json`);
  if (!fs.existsSync(rf)) fail(`no report Reports/${val('report')}.json (nothing was written)`);
  const rep = readJsonFile(rf);
  if (!Array.isArray(rep.sections)) fail(`Reports/${val('report')}.json lists "tabs" or "reportTabs", not "sections"; add ${id} by hand (nothing was written)`);
  rep.sections.push(id);
  reportNote = [rf, `${JSON.stringify(rep, null, 2)}\n`];
}

// ---- write
fs.writeFileSync(path.join(SECTIONS, `${id}.jsx`), jsx);
if (!built) fs.writeFileSync(analysisFile, (analysisSrc ? analysisSrc.replace(/\s*$/, '\n') : header) + fn);
if (newIndex) fs.writeFileSync(INDEX, newIndex);
if (reportNote) fs.writeFileSync(...reportNote);

console.log(`new-section: ${id} "${title}"${tab ? ` on tab ${tab}` : ''}`);
console.log(`  Src/Sections/${id}.jsx   the section${built ? `: ${chart}, note, and numbers in its meta (${AGG} of ${AGG === 'count' ? 'rows' : Y} by ${X}${BY ? ` and ${BY}` : ''})` : ' (empty shell)'}`);
if (!built) console.log(`  Analysis/${analysisName}.py   its analytic stub ${fnName}()`);
console.log(`  Src/Sections/index.js   added${addTab ? `, new tab "${addTab}"` : ''}${newIndex ? '' : ' NOT: add the import and the list entry by hand'}`);
if (reportNote) console.log(`  Reports/${val('report')}.json   added to "sections"`);
for (const n of notes) console.log(`  note: ${n}`);
if (built) {
  if (ignore.length) console.log(`Filters: ${ignore.join(', ')} not applied (the section compares ${[X, BY].filter(Boolean).join(' and ')}; the page tags it "<filter>: all"); --keep-filter to apply`);
  if (compare) console.log(`Change: ${compare === 'year' ? 'on the same month a year earlier' : 'on the month before'} (--compare ${compare === 'year' ? 'prev' : 'year'} for the other)`);
  console.log(`Metrics: ${metricNames.join(', ')}`);
  console.log(`Note${given ? '' : ' (generated; reword with --note "a | b" on a new section, or in the .jsx)'}:`);
  for (const l of noteLines) console.log(`  - ${l}`);
} else {
  console.log('Left: write the analytic and the look by hand (dashboard-work references/sections.md, below STOP HERE).');
}
console.log(`Next (the id is ${id}):`);
console.log('  npm run check');
console.log(`  npm run shot -- ${id} ${id}.png`);
