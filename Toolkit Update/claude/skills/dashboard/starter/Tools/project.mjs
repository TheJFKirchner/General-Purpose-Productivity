// Shared by check.mjs, status.mjs and export.mjs: load the project and validate it.
//   JSX side:      Src/Sections/index.js via Tools/registry.mjs (Vite SSR in its own process): section meta, notes, tabs
//   Analysis side: python Analysis/check.py: the analytics (filters, tables), their metrics with every
//                  filter at "All", filter values in the data, slow parameters, the manifest
//   commentary.json (optional): its items, so sections can be checked against their commentary ids
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import * as format from '../Src/Lib/format.js';
import { SAMPLE_WORDS, goodFormat, pretty } from '../Src/Lib/fill.js';
import { ROOT, pythonCommand, readJsonFile } from './py.mjs';

export { ROOT };
export const PYTHON = pythonCommand();
export const ALL = 'All';
export const LIBRARIES = ['echarts', 'none']; // the recommended ones; others are allowed
const ID = /^s(\d+)_[a-z0-9_]+$/;
// Report-only overrides: parts a report may hide; combination limits (sizes are enforced by precompute/export).
export const REPORT_PARTS = ['footer', 'source', 'notes', 'commentary', 'filters'];
export const MAX_COMBINATIONS = 500;
export const HARD_MAX_COMBINATIONS = 2000;
const REPORT_KEYS = ['title', 'audience', 'script', 'output', 'sections', 'tabs', 'reportTabs', 'parameters', 'filters', 'combinations',
  'maxCombinations', 'notes', 'theme', 'themeOverrides', 'hide', 'notice', 'inspect'];
const HEX = /^#[0-9a-fA-F]{6}$/;
const FONT = /^[\w\s,'"().-]{1,160}$/;
const V1_META = ['data', 'metrics', 'filters'];

export const readJson = (p) => readJsonFile(path.join(ROOT, p));
export const todayIso = () => new Date().toLocaleDateString('en-CA');
export const daysBetween = (a, b) => Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86_400_000);

/** Run a Python script from the project root; -> { code, stdout, stderr }. */
export function python(args, opts = {}) {
  const r = spawnSync(PYTHON, args, { cwd: ROOT, encoding: 'utf8', maxBuffer: 512 * 1024 * 1024, ...opts });
  if (r.error) return { code: 127, stdout: '', stderr: `could not run ${PYTHON}: ${r.error.message}` };
  return { code: r.status, stdout: r.stdout ?? '', stderr: r.stderr ?? '' };
}

/** python Analysis/check.py -> { cards (one per analytic), modules, filters, parameters, manifest } or { error }. */
export function analysisCheck(cards, { describe = false } = {}) {
  const r = python([path.join('Analysis', 'check.py'), ...(cards ? ['--cards', cards.join(',')] : []), ...(describe ? ['--describe'] : [])]);
  try {
    return JSON.parse(r.stdout);
  } catch {
    return { error: `python Analysis/check.py failed (exit ${r.code}): ${(r.stderr || r.stdout).trim().split('\n').slice(-6).join(' | ')}` };
  }
}

/** commentary.json items, or [] (no file). A broken file -> { error }. */
export function readCommentary() {
  const f = path.join(ROOT, 'commentary.json');
  if (!fs.existsSync(f)) return [];
  try {
    const raw = readJsonFile(f);
    return Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : { error: 'must be a list of items' };
  } catch (e) {
    return { error: e.message };
  }
}

/**
 * Everything check/status/export need:
 * { registry, tabs, format, commentaryItems, config, themes, analysis, manifest, cards, parameters, FILTERS, ALL, filterOptions(name) }
 *   analysis = check.py output; cards = analysis.cards ({id: {filters, tables, metrics, error}});
 *   FILTERS = dashboard.config.json fast filters ({name: {label, column, options}}, options from the data).
 */
export async function loadProject({ analysis: runAnalysis = true, describe = false } = {}) {
  // the registry is loaded in its own process (Tools/registry.mjs), so this one never starts Vite in dev mode
  const r = spawnSync(process.execPath, [path.join(ROOT, 'Tools', 'registry.mjs')], { cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  let registryModule;
  try {
    registryModule = JSON.parse((r.stdout ?? '').trim().split('\n').at(-1));
  } catch {
    throw new Error(((r.stderr || r.stdout || '').trim().split('\n').slice(-4).join(' | ')) || 'Tools/registry.mjs printed nothing');
  }
  if (registryModule.error) throw new Error(registryModule.error);
  registryModule.default = registryModule.sections;
  const config = readJson('dashboard.config.json');
  const themes = fs.readdirSync(path.join(ROOT, 'Themes')).filter((t) => fs.existsSync(path.join(ROOT, 'Themes', t, 'tokens.json')));
  const analysis = runAnalysis ? analysisCheck(null, { describe }) : { cards: {}, modules: {}, filters: {}, parameters: {}, manifest: null };
  const manifestFile = path.join(ROOT, 'Data', 'Current', 'manifest.json');
  const manifest = analysis.manifest ?? (fs.existsSync(manifestFile) ? readJsonFile(manifestFile) : null);
  const FILTERS = Object.fromEntries(
    Object.entries(config.filters ?? {})
      .filter(([k]) => !k.startsWith('_'))
      .map(([k, s]) => [k, { label: s.label ?? k, column: s.column ?? k, tab: s.tab ?? null, section: s.section ?? null, options: analysis.filters?.[k] ?? [ALL] }]),
  );
  return {
    registry: registryModule.default,
    tabs: registryModule.tabs ?? [],
    format,
    commentaryItems: readCommentary(),
    config,
    themes,
    analysis,
    manifest,
    cards: analysis.cards ?? {},
    parameters: analysis.parameters ?? {},
    FILTERS,
    ALL,
    filterOptions: (name) => FILTERS[name]?.options ?? [ALL],
  };
}

export const sectionPath = (id, ext = 'jsx') => path.join(ROOT, 'Src', 'Sections', `${id}.${ext}`);
/** A section's note: its `export const note` (trimmed), or null. */
export const sectionNote = (mod) => (typeof mod?.note === 'string' && mod.note.trim() ? mod.note.trim() : null);
const themeTokens = (name) => JSON.parse(fs.readFileSync(path.join(ROOT, 'Themes', name, 'tokens.json'), 'utf8'));
const tokenAt = (tokens, p) => p.split('.').reduce((node, k) => (node !== null && typeof node === 'object' ? node[k] : undefined), tokens);
const isNull = (v) => v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v));

/** Text and axis limits each library item shows as sample, so a copy still holding them can be flagged:
 *  { id: { texts: [...], limits: [[min, max]] } }. Empty when the library (config "library") is not there. */
function librarySamples(ids, config) {
  const lib = config.library ? path.resolve(ROOT, config.library) : null;
  const want = [...new Set(ids)].filter((i) => /^(CT|TB|HC)-\d\d$/.test(i ?? ''));
  if (!lib || !want.length || !fs.existsSync(path.join(lib, 'item.js'))) return {};
  const r = spawnSync(process.execPath, ['item.js', ...want, '--json'], { cwd: lib, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  let items = [];
  try {
    items = JSON.parse(r.stdout);
  } catch {
    return {};
  }
  const out = {};
  for (const it of items) {
    const texts = [];
    const limits = [];
    const html = String(it.html ?? '');
    const json = /<script type="application\/json">([\s\S]*?)<\/script>/.exec(html)?.[1];
    if (json) {
      const walk = (x, key) => {
        if (Array.isArray(x)) x.forEach((v) => walk(v, key));
        else if (x && typeof x === 'object') {
          if (/Axis$/.test(key ?? '') && typeof x.min === 'number' && typeof x.max === 'number') limits.push([x.min, x.max]);
          if (/Axis$/.test(key ?? '') && typeof x.name === 'string' && x.name.length > 3) texts.push(x.name);
          if (typeof x.formatter === 'string' && !x.formatter.includes('{') && x.formatter.length > 3) texts.push(x.formatter);
          for (const [k, v] of Object.entries(x)) if (k !== 'data') walk(v, /Axis$/.test(k) ? k : key);
        }
      };
      try {
        walk(JSON.parse(json), null);
      } catch { /* not readable: no chart samples */ }
    }
    // visible text outside slots and outside the repeated rows (those are replaced at every draw)
    const stack = [];
    let skip = 0;
    for (const m of html.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, '').matchAll(/<(\/?)([a-z0-9]+)([^>]*)>|([^<]+)/gi)) {
      if (m[4] !== undefined) {
        const t = m[4].replace(/\s+/g, ' ').trim();
        if (!skip && t.length > 3 && /[a-z]{3}/i.test(t) && !stack.at(-1)?.slot) texts.push(t);
        continue;
      }
      if (/^(br|img|input|hr|meta)$/i.test(m[2]) || m[3].endsWith('/')) continue;
      if (m[1]) {
        const top = stack.pop();
        if (top?.rows) skip -= 1;
      } else {
        const e = { slot: /data-slot/.test(m[3]), rows: /data-rows/.test(m[3]) };
        if (e.rows) skip += 1;
        stack.push(e);
      }
    }
    out[it.id] = { texts: [...new Set(texts)], limits };
  }
  return out;
}

/** Validate registry, section files, analytics, notes, commentary ids, config. -> { errors, warnings, cardErrors: {id: [msg]} } */
export function validateProject(p) {
  const errors = [];
  const warnings = [];
  const cardErrors = {};
  const cardError = (id, msg) => {
    errors.push(msg);
    (cardErrors[id] ??= []).push(msg);
  };
  const ids = new Set();
  const numbers = new Map();
  const a = p.analysis;
  const samples = librarySamples((p.registry ?? []).map((m) => m?.meta?.use), p.config);

  if (!p.themes.includes(p.config.theme)) errors.push(`dashboard.config.json: theme "${p.config.theme}" not found in Themes/`);
  const noCardsYet = Array.isArray(p.registry) && !p.registry.length;
  if (a.error) (noCardsYet && /^No data yet/.test(a.error) ? warnings : errors).push(`Analysis: ${a.error}`);
  for (const [mod, err] of Object.entries(a.modules ?? {})) if (err) errors.push(`Analysis/${mod}.py does not import, so its cards are missing: ${err}`);
  const noCards = Array.isArray(p.registry) && !p.registry.length;
  const items = p.commentaryItems;
  const commentaryIds = new Set(Array.isArray(items) ? items.map((it) => it?.id) : []);
  if (!Array.isArray(items)) warnings.push(`commentary.json: ${items.error}; no commentary will show`);
  else items.forEach((it, i) => {
    const bad = !it || typeof it.id !== 'string' || !Array.isArray(it.commentary) || (it.source !== undefined && typeof it.source !== 'string')
      || (it.filters !== undefined && (typeof it.filters !== 'object' || it.filters === null || Array.isArray(it.filters)));
    if (bad) warnings.push(`commentary.json item ${i + 1}: needs "id" (text), "commentary" (list of text), "source" (text), optional "filters" (object column: value); it is skipped`);
  });
  const noData = !a.error && (!p.manifest?.tables || !Object.keys(p.manifest.tables).length);
  // a brand-new project (no cards yet) is fine: say what's next instead of failing
  if (noData) (noCards ? warnings : errors).push('Data/Current has no tables yet (add write_source lines to Pipeline/sources.py, then npm run pipeline)');
  if (noCards) warnings.push('no sections yet: add one with npm run new-section -- <name>');
  if (!p.config.dataSource) warnings.push('dashboard.config.json: "dataSource" is empty, so the header names no source; set it (e.g. "Claims extract; months are the month care was given")');
  if (!a.error && p.manifest?.tables && Object.keys(p.manifest.tables).length && !Object.values(p.manifest.tables).some((t) => t.as_of)) {
    warnings.push('no table has an as-of date, so the header shows no "Data as of": load each input file in Pipeline/sources.py with write_source("<table>", "<file>", as_of_from="<date column>"), then npm run pipeline');
  }
  for (const [id, c] of Object.entries(p.cards)) for (const s of c.slices ?? []) warnings.push(`section ${id} fails on a single filter value: ${s}`);
  const knownColumns = new Set(Object.values(p.FILTERS).map((f) => f.column));
  if (Array.isArray(items)) for (const it of items) for (const col of Object.keys(it?.filters ?? {})) {
    if (!knownColumns.has(col)) warnings.push(`commentary.json ${it.id}: filter column "${col}" is not a fast filter's column in dashboard.config.json, so this item only shows when that is "All"`);
  }
  if (!Array.isArray(p.registry)) errors.push('Src/Sections/index.js must default-export an array of section modules');
  const tabIds = new Set();
  for (const t of p.tabs ?? []) {
    if (!/^[a-z][a-z0-9_-]*$/.test(t?.id ?? '') || !t.label) errors.push(`tabs: each tab needs { id: 'lowercase_id', label } (got ${JSON.stringify(t)})`);
    if (tabIds.has(t?.id)) errors.push(`tabs: duplicate id "${t.id}"`);
    tabIds.add(t?.id);
  }

  for (const mod of p.registry ?? []) {
    const meta = mod?.meta;
    const id = meta?.id ?? '(no meta.id)';
    const where = `section ${id}`;
    const err = (msg) => cardError(id, `${where}: ${msg}`);
    if (!meta || !mod.hasDefault) {
      err('must export `meta` and a default component');
      continue;
    }
    if (!ID.test(meta.id ?? '')) err('id must look like s2_revenue_trend (s + number, underscore, snake_case name)');
    if (ids.has(meta.id)) err('duplicate id');
    ids.add(meta.id);
    const number = ID.exec(meta.id ?? '')?.[1];
    if (number && numbers.has(number)) err(`number s${number} already used by ${numbers.get(number)} (numbers must be unique for ad hoc export)`);
    if (number) numbers.set(number, meta.id);
    if (mod.note !== undefined && typeof mod.note !== 'string') err('`export const note` must be a string (template literal)');
    if (mod.oldCommentary) err('`export const commentary` is now `export const note`; meta.commentary names a commentary.json id');
    if (meta.commentary !== undefined && typeof meta.commentary !== 'string') err('meta.commentary must be one commentary.json id, e.g. "C1"');
    else if (meta.commentary && !commentaryIds.has(meta.commentary)) warnings.push(`${where}: commentary id "${meta.commentary}" is not in commentary.json (nothing shows until it is)`);
    if (!fs.existsSync(sectionPath(meta.id))) err(`file Src/Sections/${meta.id}.jsx not found (file name must equal id)`);
    if (!meta.title) err('meta.title missing');
    if (!meta.description) warnings.push(`${where}: no meta.description (8 to 10 words on what it shows; npm run status lists it)`);
    // recommended: echarts; any other library is allowed (the dashboard skill, references/sections.md)
    if (!/^[a-z][a-z0-9_-]*$/.test(meta.library ?? '')) err(`meta.library must name the chart library (e.g. ${LIBRARIES.join(', ')})`);
    if (tabIds.size && !tabIds.has(meta.tab)) err(`meta.tab must be one of ${[...tabIds].join(', ')} (tabs are defined in Src/Sections/index.js)`);
    if (!tabIds.size && meta.tab) err('meta.tab set but Src/Sections/index.js exports no tabs');
    for (const k of V1_META) if (k in meta) err(`meta.${k} is a leftover: tables, filters and metrics come from the section's analytic (@section in Analysis/<tab>.py); remove it`);

    const src = fs.existsSync(sectionPath(meta.id)) ? fs.readFileSync(sectionPath(meta.id), 'utf8') : '';
    if (/\bfetch\s*\(|XMLHttpRequest|\/api\//.test(src)) err('fetches data; sections get { data, metrics } only via props (SectionFrame asks Src/Lib/source.js)');
    const dataImport = [...src.matchAll(/(?:from\s+|import\s*\(\s*|import\s+)['"]([^'"]+)['"]/g)].map((m) => m[1])
      .find((s) => /(^|\/)Data\/|\.json$|\.parquet$|\.csv$|@precomputed|Lib\/(source|useSection)(\.js)?$/i.test(s));
    if (dataImport) err(`imports "${dataImport}"; sections must not load data (they get { data, metrics } as props)`);
    const sample = samples[meta.use];
    const found = [...new Set([...SAMPLE_WORDS.filter((w) => src.includes(w)), ...(sample?.texts ?? []).filter((t) => src.includes(t) || src.includes(JSON.stringify(t).slice(1, -1)))])];
    const left = found.filter((t) => !found.some((o) => o !== t && o.includes(t)));
    if (left.length) warnings.push(`${where}: still has the library sample's words ("${left.slice(0, 3).map((t) => t.slice(0, 50)).join('", "')}"${left.length > 3 ? ` and ${left.length - 3} more` : ''}); write the real ones`);
    for (const [lo, hi] of sample?.limits ?? []) if (new RegExp(`\\bmin:\\s*${lo}\\b`).test(src) && new RegExp(`\\bmax:\\s*${hi}\\b`).test(src)) warnings.push(`${where}: an axis still has the sample's range (min ${lo}, max ${hi}); delete them so it fits the data`);
    for (const [c, n] of Object.entries(mod.names ?? {})) if (!['base', 'rise', 'fall', 'total', 'key', 'share', 'label', 'value'].includes(c) && typeof n === 'string' && (n === pretty(c) || n === c)) warnings.push(`${where}: names.${c} is "${n}", the column's own words; write what readers call it`);
    for (const [c, spec] of Object.entries(mod.format ?? {})) if (!goodFormat(spec)) warnings.push(`${where}: format ${c}: "${spec}" is not a known format ($short, short, comma, $comma, pct, .1%, month, or a pattern like '{value} days')`);

    if (a.error) continue; // Analysis didn't run (e.g. no data yet): its error above says why; section checks would only mislead
    const card = p.cards[meta.id];
    if (!card || card.module === null) {
      err(`no analytic: add @section("${meta.id}", tables=[...]) in Analysis/<tab>.py`);
      continue;
    }
    for (const t of card.tables ?? []) if (p.manifest?.tables && !p.manifest.tables[t]) err(`Analysis table "${t}" is not in Data/Current (pipeline table or .parquet/.csv file)`);
    for (const f of card.filters ?? []) if (!p.FILTERS[f]) err(`Analysis filter "${f}" is not defined in dashboard.config.json "filters"`);
    if (card.error) {
      err(`Analysis failed with every filter at All: ${card.error}`);
      continue;
    }
    if (mod.slots && card.columns) {
      for (const [slot, v] of Object.entries(mod.slots)) {
        for (const c of [].concat(v)) {
          if (typeof c === 'string' && c !== '*' && !/^-?\d+(\.\d+)?$/.test(c) && !card.columns.includes(c)) err(`slots.${slot}: "${c}" is not a column of its data (columns: ${card.columns.join(', ')})`);
        }
      }
    }
    const metrics = card.metrics ?? {};
    const md = sectionNote(mod);
    const refs = md ? new Set(p.format.parseRefs(md).map((r) => r.metric)) : new Set();
    if (md) for (const prob of p.format.renderNote(md, metrics).problems) err(`note ${prob}`);
    for (const [k, v] of Object.entries(metrics)) {
      if (isNull(v)) warnings.push(`${where}: metric "${k}" is null on unfiltered data${refs.has(k) ? ' (shows "n/a" in the note)' : ''}`);
    }
  }

  // where each filter lives: the whole dashboard (no tab/section), one tab, or one section
  const tabOf = Object.fromEntries((p.registry ?? []).map((m) => [m?.meta?.id, m?.meta?.tab]));
  const levelText = (f) => (f.section ? `section ${f.section}` : f.tab ? `tab ${f.tab}` : 'the whole dashboard');
  for (const [name, f] of Object.entries(p.FILTERS)) {
    const where = `dashboard.config.json filter "${name}"`;
    if (f.tab && f.section) errors.push(`${where}: give it "tab" or "section", not both`);
    else if (f.tab && !tabIds.has(f.tab)) errors.push(`${where}: tab "${f.tab}" doesn't exist (tabs: ${[...tabIds].join(', ') || 'none, this dashboard has one page'})`);
    else if (f.section && !ids.has(f.section)) errors.push(`${where}: section "${f.section}" doesn't exist`);
    else if (!a.error && ids.size && !Object.values(p.cards).some((c) => c.filters?.includes(name))) {
      errors.push(`${where} (${levelText(f)}) applies to no section: none of the sections it reaches reads a table with column "${f.column}"`);
    }
  }
  for (const [id, c] of Object.entries(p.cards)) {
    if (!c.declared) continue;
    for (const n of c.filters ?? []) {
      const f = p.FILTERS[n];
      if (f && ((f.section && f.section !== id) || (f.tab && f.tab !== tabOf[id]))) {
        warnings.push(`section ${id}: its @section line lists filter "${n}", which lives on ${levelText(f)}; remove filters=[...] from that line so the config decides`);
      }
    }
  }

  for (const id of Object.keys(p.cards)) if (!ids.has(id) && p.cards[id].module) warnings.push(`analytic for "${id}" (${p.cards[id].module === '(meta)' ? `Src/Sections/${id}.jsx meta` : `Analysis/${p.cards[id].module}.py`}) has no section in Src/Sections/index.js`);
  const dir = path.join(ROOT, 'Src', 'Sections');
  for (const f of fs.readdirSync(dir)) {
    if (f.endsWith('.md')) {
      warnings.push(`Src/Sections/${f}: a section's note lives in its .jsx file (export const note); this file is ignored`);
      continue;
    }
    const m = f.match(/^(.+)\.jsx$/);
    if (m && !ids.has(m[1])) warnings.push(`Src/Sections/${f}: not in the registry (Src/Sections/index.js)`);
  }
  return { errors, warnings, cardErrors };
}

/** Section ids a report includes: its "reportTabs" sections, its "sections" list, or every section in its "tabs" (registry order). */
export function reportSectionIds(report, p) {
  if (Array.isArray(report.reportTabs)) return report.reportTabs.flatMap((t) => (Array.isArray(t?.sections) ? t.sections : []));
  if (Array.isArray(report.tabs)) return p.registry.filter((m) => report.tabs.includes(m.meta.tab)).map((m) => m.meta.id);
  return Array.isArray(report.sections) ? report.sections : [];
}

const asList = (v) => (Array.isArray(v) ? v.map(String) : [String(v)]);

/**
 * The report's filters and allowed combinations (same rules as Analysis/precompute.py, which is authoritative):
 * -> { filters: {name: {value, locked, options}}, combos: [{name: value}], max, problems: [msg], notes: [msg] }
 * Only filters used by the report's sections count; unlisted ones are fixed at "All"; a filter without "options" is fixed.
 */
export function reportPlan(report, p) {
  const problems = [];
  const notes = [];
  const ids = reportSectionIds(report, p);
  const used = Object.keys(p.FILTERS).filter((f) => ids.some((id) => p.cards[id]?.filters?.includes(f)));
  const rf = report.filters && typeof report.filters === 'object' && !Array.isArray(report.filters) ? report.filters : {};
  if (report.filters !== undefined && rf !== report.filters) problems.push('"filters" must be an object {name: {value, locked | options}}');
  for (const [f, spec] of Object.entries(rf)) {
    if (!p.FILTERS[f]) problems.push(`filter "${f}" not defined in dashboard.config.json "filters" (${Object.keys(p.FILTERS).join(', ')})`);
    else if (!p.analysis?.error && !used.includes(f)) notes.push(`filter "${f}" is not used by any included section; ignored`);
    if (spec === null || typeof spec !== 'object' || Array.isArray(spec)) problems.push(`filter "${f}" must be {"value": ..., "locked": true} or {"value": ..., "options": [...]}`);
    else for (const k of Object.keys(spec)) if (!['value', 'locked', 'options'].includes(k)) problems.push(`filter "${f}": unknown key "${k}" (value, locked, options)`);
  }
  const filters = {};
  for (const f of used) {
    const spec = rf[f] && typeof rf[f] === 'object' ? rf[f] : {};
    const known = p.filterOptions(f);
    let value;
    let options;
    let locked;
    if (spec.options !== undefined) {
      options = Array.isArray(spec.options) ? spec.options.map(String) : [];
      if (!options.length) problems.push(`filter "${f}": "options" must be a non-empty list`);
      if (new Set(options).size !== options.length) problems.push(`filter "${f}": "options" has duplicates`);
      if (spec.locked) problems.push(`filter "${f}" is locked; "options" only applies to filters the viewer can change`);
      value = String(spec.value ?? options[0] ?? ALL);
      if (options.length && !options.includes(value)) problems.push(`filter "${f}" starts at "${value}", which is not in its options (${options.join(', ')})`);
      locked = false;
    } else {
      value = String(spec.value ?? ALL);
      options = [value];
      locked = true;
      if (spec.locked === false) notes.push(`filter "${f}" has no "options", so it is fixed at "${value}"; add "options" to let viewers choose`);
    }
    for (const o of options) if (!known.includes(o)) problems.push(`filter "${f}": "${o}" not found in the data (values: ${known.join(', ')})`);
    filters[f] = { value, locked, options };
  }

  const names = Object.keys(filters);
  let combos = names.reduce((acc, n) => acc.flatMap((c) => filters[n].options.map((o) => ({ ...c, [n]: o }))), [{}]);
  const rules = report.combinations;
  const matches = (c, rule) => Object.entries(rule).every(([k, v]) => asList(v).includes(c[k]));
  if (rules !== undefined) {
    if (!rules || typeof rules !== 'object' || Array.isArray(rules) || Object.keys(rules).some((k) => !['only', 'except'].includes(k))) {
      problems.push('"combinations" must be {"only": [rules], "except": [rules]}');
    } else {
      for (const kind of ['only', 'except']) {
        const list = rules[kind];
        if (list === undefined) continue;
        if (!Array.isArray(list) || !list.length) {
          problems.push(`combinations.${kind} must be a non-empty list of rules`);
          continue;
        }
        list.forEach((rule, i) => {
          const where = `combinations.${kind}[${i}]`;
          if (!rule || typeof rule !== 'object' || Array.isArray(rule) || !Object.keys(rule).length) return problems.push(`${where}: each rule is an object like {"region": ["East", "West"]}`);
          for (const [k, v] of Object.entries(rule)) {
            if (!filters[k]) problems.push(`${where}: filter "${k}" is not used by this report's sections (${names.join(', ') || 'none'})`);
            else for (const x of asList(v)) if (!filters[k].options.includes(x)) problems.push(`${where}: "${x}" is not one of filter "${k}"'s values in this report (${filters[k].options.join(', ')})`);
          }
          return null;
        });
      }
      if (!problems.length) {
        if (Array.isArray(rules.only)) combos = combos.filter((c) => rules.only.some((r) => matches(c, r)));
        if (Array.isArray(rules.except)) combos = combos.filter((c) => !rules.except.some((r) => matches(c, r)));
      }
    }
  }
  const max = report.maxCombinations ?? MAX_COMBINATIONS;
  if (!Number.isInteger(max) || max < 1 || max > HARD_MAX_COMBINATIONS) problems.push(`"maxCombinations" must be a whole number from 1 to ${HARD_MAX_COMBINATIONS}`);
  if (!problems.length) {
    const start = Object.fromEntries(names.map((n) => [n, filters[n].value]));
    if (!combos.length) problems.push('no filter combinations left after combinations.only / except');
    else if (!combos.some((c) => names.every((n) => c[n] === start[n]))) problems.push(`the starting values ${JSON.stringify(start)} are excluded by "combinations"; the report would open on an empty page`);
    if (Number.isInteger(max) && combos.length > max) {
      problems.push(`${combos.length} filter combinations is over the limit of ${max} (narrow "options", add "combinations", or raise "maxCombinations" up to ${HARD_MAX_COMBINATIONS})`);
    }
  }
  return { filters, combos, max, problems, notes };
}

/** Validate a report object against the project. Returns { errors, warnings }. */
export function validateReport(name, report, p) {
  const errors = [];
  const warnings = [];
  const E = (msg) => errors.push(`report ${name}: ${msg}`);
  const W = (msg) => warnings.push(`report ${name}: ${msg}`);
  if (!report || typeof report !== 'object' || Array.isArray(report)) {
    E('must be a JSON object');
    return { errors, warnings };
  }
  const byId = new Map((p.registry ?? []).map((m) => [m.meta.id, m]));
  for (const k of Object.keys(report)) if (!REPORT_KEYS.includes(k)) W(`unknown key "${k}" (ignored)`);
  if (!report.title) E('"title" missing');
  if (report.title !== undefined && (typeof report.title !== 'string' || report.title.length > 120)) E('"title" must be text up to 120 characters');
  if (report.audience !== undefined && report.audience !== null && (typeof report.audience !== 'string' || report.audience.length > 120)) E('"audience" must be text up to 120 characters');
  if (report.tabs && report.sections) E('use "tabs" or "sections", not both');
  if (report.sections !== undefined && !Array.isArray(report.sections)) E('"sections" must be a list of section ids');
  if (report.output !== undefined && (typeof report.output !== 'string' || !/^[A-Za-z0-9][\w.-]{0,80}$/.test(report.output))) E('"output" must be a file name stem (letters, numbers, - _ .)');
  if (report.script !== undefined && (typeof report.script !== 'string' || !/^[\w.-]+\.py$/.test(report.script))) E('"script" must be the report\'s Python file name in Reports/, e.g. "finance.py"');
  else if (report.script && !name.startsWith('_') && !fs.existsSync(path.join(ROOT, 'Reports', report.script))) W(`script Reports/${report.script} not found`);
  if (report.script === undefined && !name.startsWith('_')) W('no "script": a report runs as python Reports/<name>.py (see the dashboard skill, references/exports.md)');
  if (report.tabs !== undefined && !Array.isArray(report.tabs)) E('"tabs" must be a list of tab ids');
  if (report.reportTabs !== undefined) {
    if (report.tabs || report.sections) E('use "reportTabs" or "tabs" / "sections", not both');
    if (!Array.isArray(report.reportTabs) || !report.reportTabs.length) E('"reportTabs" must be a non-empty list');
    const seen = new Set();
    for (const [i, t] of (Array.isArray(report.reportTabs) ? report.reportTabs : []).entries()) {
      const where = `reportTabs[${i}]`;
      if (typeof t?.label !== 'string' || !t.label.trim() || t.label.length > 40) E(`${where}: needs a "label" (1-40 characters)`);
      const hasSections = Array.isArray(t?.sections) && t.sections.length > 0;
      const hasText = typeof t?.text === 'string' && t.text.trim().length > 0;
      if (hasSections === hasText) E(`${where}: needs either "sections" (section ids) or "text", not both`);
      if (hasText && (t.text.length > 2000 || /<[a-zA-Z/!]/.test(t.text))) E(`${where}: "text" is plain text, up to 2000 characters`);
      for (const id of hasSections ? t.sections : []) {
        if (seen.has(id)) E(`${where}: section "${id}" is already in another tab`);
        seen.add(id);
      }
    }
  }
  if (report.notice !== undefined && report.notice !== null && (typeof report.notice !== 'string' || report.notice.length > 300 || /<[a-zA-Z/!]/.test(report.notice))) E('"notice" must be plain text up to 300 characters');
  if (report.hide !== undefined && (!Array.isArray(report.hide) || report.hide.some((h) => !REPORT_PARTS.includes(h)))) E(`"hide" may list only ${REPORT_PARTS.join(', ')}`);
  if (report.themeOverrides !== undefined) {
    const theme = report.theme || p.config.theme;
    const tokens = p.themes.includes(theme) ? themeTokens(theme) : null;
    if (!tokens || !report.themeOverrides || typeof report.themeOverrides !== 'object' || Array.isArray(report.themeOverrides)) E('"themeOverrides" must map theme paths to values');
    for (const [key, v] of Object.entries(tokens && report.themeOverrides && typeof report.themeOverrides === 'object' ? report.themeOverrides : {})) {
      const bad = (why) => E(`themeOverrides "${key}": ${why}`);
      if (/^colors\.named\.[A-Za-z0-9][A-Za-z0-9 &/+'()_-]{0,39}$/.test(key)) {   // a category color (f.colorOf), may be new
        if (!HEX.test(String(v))) bad('must be a color like "#C62828"');
        continue;
      }
      const cur = tokenAt(tokens, key);
      if (key.split('.')[0] === 'name' || cur === undefined || (cur !== null && typeof cur === 'object')) bad('not a theme value (use a path like colors.accent or colors.series.0)');
      else if (typeof cur === 'boolean') typeof v !== 'boolean' && bad('must be true or false');
      else if (typeof cur === 'number') (typeof v !== 'number' || (key === 'font.size' && (v < 10 || v > 20))) && bad(key === 'font.size' ? 'must be a number 10-20' : 'must be a number');
      else if (HEX.test(cur)) !HEX.test(String(v)) && bad('must be a color like "#C62828"');
      else if (typeof v !== 'string' || !FONT.test(v)) bad('must be a plain font list');
    }
  }
  // a locked filter that doesn't narrow a section (e.g. a region comparison under a West report) reads oddly
  for (const [f, spec] of Object.entries(report.filters && typeof report.filters === 'object' ? report.filters : {})) {
    if (!spec?.locked || spec.value === undefined || String(spec.value) === ALL) continue;
    for (const id of reportSectionIds(report, p)) {
      if (p.cards[id] && !(p.cards[id].filters ?? []).includes(f)) W(`section ${id} is not narrowed by "${f}", which this report locks at ${spec.value}; leave it out or say so in the notice`);
    }
  }
  for (const t of Array.isArray(report.tabs) ? report.tabs : []) if (!p.tabs.some((x) => x.id === t)) E(`tab "${t}" not defined (tabs: ${p.tabs.map((x) => x.id).join(', ')})`);
  const ids = reportSectionIds(report, p);
  if (!ids.length) E('needs a non-empty "sections", "tabs" or "reportTabs" list');
  if (new Set(ids).size !== ids.length) E('a section is listed twice');
  for (const id of ids) {
    if (!byId.has(id)) E(`section "${id}" not in the registry (Src/Sections/index.js)`);
    else if (!p.analysis?.error && (!p.cards[id] || p.cards[id].module === null)) E(`section "${id}" has no analytic, so it can't be precomputed`);
  }
  if (report.inspect !== undefined && typeof report.inspect !== 'boolean') E('"inspect" must be true or false');
  if (report.theme !== undefined && !p.themes.includes(report.theme)) E(`theme "${report.theme}" not found in Themes/ (${p.themes.join(', ')})`);

  // slow parameters: pinned values must be allowed options (export re-runs the pipeline with them)
  if (report.parameters !== undefined) {
    if (!report.parameters || typeof report.parameters !== 'object' || Array.isArray(report.parameters)) E('"parameters" must be an object like {"as_of": "2026-07-31"}');
    else {
      for (const [k, v] of Object.entries(report.parameters)) {
        const spec = p.parameters[k];
        if (!spec) E(`parameter "${k}" is not defined in dashboard.config.json "parameters" (${Object.keys(p.parameters).join(', ') || 'none'})`);
        else if (!spec.options.some((o) => o.value === String(v))) E(`parameter "${k}": "${v}" is not allowed (${spec.options.map((o) => o.value).join(', ')})`);
      }
    }
  }

  // filters + combinations (only when the section list is sound; otherwise the plan is meaningless)
  if (!errors.length) {
    const plan = reportPlan(report, p);
    for (const prob of plan.problems) E(prob);
    for (const n of plan.notes) W(n);
  }

  if (report.notes !== undefined && (!report.notes || typeof report.notes !== 'object' || Array.isArray(report.notes))) E('"notes" must map section ids to true, false or text');
  for (const [id, v] of Object.entries(report.notes && typeof report.notes === 'object' ? report.notes : {})) {
    if (!ids.includes(id)) W(`notes key "${id}" is not a section in this report`);
    if (typeof v === 'string') {
      if (v.length > 1500 || /<[a-zA-Z/!]/.test(v)) E(`note for "${id}" is plain text up to 1500 characters`);
      else if (p.cards[id]?.metrics && !p.cards[id].error) {
        for (const prob of p.format.renderNote(v, p.cards[id].metrics).problems) E(`note for "${id}": ${prob}`);
      }
    } else if (typeof v !== 'boolean') E(`note for "${id}" must be true, false or text`);
  }
  return { errors, warnings };
}

export function printResults({ errors, warnings }) {
  for (const w of warnings) console.log(`WARN  ${w}`);
  for (const e of errors) console.log(`ERROR ${e}`);
}
