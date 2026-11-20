#!/usr/bin/env node

/**
 * Proves every library item can be added: makes a scratch report, deck and dashboard in a temp folder with made-up
 * data, adds every addable item by id through each skill's own add command (as a user would), builds, and prints one
 * line per case and a summary. Exit code 1 on any FAIL. No dependencies.
 *
 *   node sweep-add.js [--target report|deck|dashboard|all] [--only CT-34,TB-09] [--skills <.claude/skills>] [--shots]
 *
 * Cases for every chart, table and hero card: all slots given; optional slots left out; one required slot left out.
 * Decks also: every slide alone, a chart swapped into each slide with a chart spot, a chart given to each slide
 * without one, each animation as its own slide. Reports: every addable animation too.
 * Result: PASS (added, no MANUAL: line), MANUAL (added, with a MANUAL: line to edit by hand), FAIL (refused or broke).
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const S = require('./save-item.js');
const I = require('./item.js');

const args = process.argv.slice(2);
const opt = k => { const i = args.indexOf(k); return i === -1 ? undefined : args[i + 1]; };
const target = opt('--target') || 'all', only = opt('--only') ? opt('--only').split(',') : null, shots = args.includes('--shots');
const skills = opt('--skills') || [path.join(__dirname, '..', '..', '.claude', 'skills'), path.join(__dirname, '..', '.claude', 'skills')].find(d => fs.existsSync(d));
if (!skills) { console.error('STOP: no .claude/skills found beside the library; pass --skills <folder>'); process.exit(1); }
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'sweep-add-'));
const PY = ['python', 'python3', 'py'].find(p => !spawnSync(p, ['--version']).error) || 'python';

/* ---------- made-up data: 3 text columns, a date, 4 numbers, 72 rows ---------- */
const rows = [];
['North', 'South', 'East', 'West'].forEach((region, r) => ['Gold', 'Silver', 'Bronze'].forEach((product, p) => [1, 2, 3, 4, 5, 6].forEach(m => {
  const paid = 100 + r * 20 + p * 10 + m * 5;
  rows.push({ region, product, segment: m % 2 ? 'New' : 'Renewal', date: `2025-0${m}-15`, paid, allowed: paid + 15, members: 50 + r * 5 + m, plan: 110 + r * 15 });
})));
const csv = path.join(tmp, 'data.csv');
fs.writeFileSync(csv, ['region,product,segment,date,paid,allowed,members,plan'].concat(rows.map(o => Object.values(o).join(','))).join('\n') + '\n');

/* ---------- slots from a data note, by kind: text, number, figure ---------- */
function slotArgs(note, mode) {
  const text = ['region', 'product', 'segment'], nums = ['paid', 'allowed', 'members', 'plan'];
  let t = 0, n = 0;
  const req = note.filter(s => s.count === 'one' || s.count === 'one or more');
  const dropped = mode === 'required-out' ? (req[0] || {}).name : null;
  const out = [];
  note.forEach(s => {
    if (s.name === dropped) return;
    if (mode !== 'all' && (s.count === 'optional' || s.count === 'any') && mode === 'optional-out') return;
    let v;
    if (s.kind === 'figure') v = '100';
    else if (s.kind === 'text') v = /month|period|date|quarter|age|year/.test(s.name) ? 'date' : text[t++ % text.length];
    else v = s.count === 'one or more' || s.count === 'any' ? [nums[n++ % 4], nums[n++ % 4]].join(',') : nums[n++ % 4];
    out.push('--slot', `${s.name}=${v}`);
  });
  return out;
}
const items = S.items().filter(i => !only || only.includes(i.h.id));
const ofType = (...ts) => items.filter(i => ts.includes(i.h.type)).map(i => i.h.id);
const noteOf = id => I.copyOf(I.get(id)).data || [];
const addable = id => !/^none/.test(I.get(id).h.fits || '');
const variants = id => { const n = noteOf(id); return ['all'].concat(n.some(s => s.count === 'optional' || s.count === 'any') ? ['optional-out'] : [], n.some(s => s.count === 'one' || s.count === 'one or more') ? ['required-out'] : []); };

/* ---------- running a case ---------- */
const results = [];
const say = res => console.log(`${res.status.padEnd(6)} ${res.tgt.padEnd(9)} ${res.label}${res.why ? '  ' + res.why : ''}`);
/* refuse: the case should be refused (AN-09): a refusal passes, an add fails. Returns { ok, lines }. */
function run(tgt, label, exe, argv, cwd, refuse) {
  const r = spawnSync(exe, argv, { cwd, encoding: 'utf8', timeout: 600000, shell: false });
  const lines = `${r.stdout || ''}\n${r.stderr || ''}`.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const manual = lines.find(l => /^MANUAL:/.test(l));
  const bad = !!(r.error || r.status !== 0);
  const err = r.error ? String(r.error.message) : lines.find(l => /^(STOP|ERROR)\b/.test(l)) || (lines.some(l => /^Traceback/.test(l)) && lines[lines.length - 1]) ||
    lines.find(l => /Error|refus|cannot/.test(l)) || lines[lines.length - 1] || `exit ${r.status}`;
  const res = refuse ? { tgt, label, status: bad ? 'PASS' : 'FAIL', why: bad ? `refused as expected: ${err}` : 'added, but it should be refused' }
    : { tgt, label, status: bad ? 'FAIL' : manual ? 'MANUAL' : 'PASS', why: bad ? err : manual || '' };
  res.why = res.why.slice(0, 200);
  results.push(res);
  say(res);
  return { ok: !bad, lines, res };
}
const caseName = (id, v) => `${id.toLowerCase().replace('-', '')}_${v.replace('-', '_')}`;

/* ---------- report: analysis add-section --use ---------- */
function report() {
  const rep = path.join(tmp, 'report');
  if (!run('report', 'new report', PY, [path.join(skills, 'analysis', 'scripts', 'new_report.py'), tmp, 'report', '--title', 'Sweep', '--question', 'Can every item be added?', '--source', `data=${csv}`, '--library', __dirname], tmp).ok) return;
  ofType('chart', 'table', 'hero card').forEach(id => variants(id).forEach(v => run('report', `${id} ${v}`, PY, ['run.py', 'add-section', caseName(id, v), '--use', id, '--source', 'data', ...slotArgs(noteOf(id), v)], rep)));
  ofType('animation').forEach(id => run('report', `${id} ${addable(id) ? 'animation' : 'refused (expected)'}`, PY, ['run.py', 'add-section', caseName(id, 'anim'), '--use', id, '--source', 'data', ...slotArgs(noteOf(id), 'all')], rep, !addable(id)));
  // a user writes the headline and basis before building
  const rp = path.join(rep, 'report.py');
  fs.writeFileSync(rp, fs.readFileSync(rp, 'utf8').replace('"headline": "",', '"headline": "Every item can be added.",').replace('"basis": "",', '"basis": "Made-up data, six months.",'));
  run('report', 'build (run.py report)', PY, ['run.py', 'report'], rep);
  if (shots) run('report', 'shot', PY, ['run.py', 'shot'], rep);
}

/* ---------- deck: deck.js add / animate ---------- */
function deck() {
  const js = path.join(skills, 'presentation', 'scripts', 'deck.js'), d = path.join(tmp, 'deck');
  if (!run('deck', 'new deck', process.execPath, [js, 'new', d, '--title', 'Sweep'], tmp).ok) return;
  const add = (label, a, refuse) => run('deck', label, process.execPath, [js, ...a], tmp, refuse);
  const slides = ofType('slide'), withChart = slides.filter(id => I.spotsOf(I.blockOf(I.get(id).text)).includes('chart'));
  slides.forEach(id => add(`${id} alone`, ['add', d, id]));
  ofType('chart', 'table', 'hero card').forEach(id => variants(id).forEach(v => add(`${id} ${v}`, ['add', d, id, '--data', csv, ...slotArgs(noteOf(id), v)])));
  const charts = ['CT-34', 'CT-35', 'CT-36', 'CT-02', 'CT-06'].filter(c => S.items().some(i => i.h.id === c));
  withChart.forEach((id, k) => { const c = charts[k % charts.length]; add(`${id} + ${c}`, ['add', d, id, c, '--data', csv, ...slotArgs(noteOf(c), 'all')]); });
  slides.filter(id => !withChart.includes(id)).forEach(id => add(`${id} + CT-34 (no chart spot)`, ['add', d, id, 'CT-34', '--data', csv, ...slotArgs(noteOf('CT-34'), 'all')]));
  ofType('animation').forEach(id => add(`${id} ${addable(id) ? 'animation' : 'refused (expected)'}`, ['animate', d, id, '--data', csv, ...slotArgs(noteOf(id), 'all')], !addable(id)));
  add('build', ['build', d]);
  if (shots) add('check', ['check', d]);
}

/* ---------- dashboard: one scratch dashboard, every item, one check ---------- */
function dashboard() {
  const dash = path.join(tmp, 'dash');
  // one npm install for the whole sweep (the check loads the sections, which needs the packages)
  if (!run('dashboard', 'setup (one npm install)', PY, [path.join(skills, 'dashboard', 'tools', 'setup.py'), dash, '--title', 'Sweep', '--library', __dirname], tmp).ok) return;
  fs.mkdirSync(path.join(dash, 'Data', 'Current'), { recursive: true });
  fs.copyFileSync(csv, path.join(dash, 'Data', 'Current', 'data.csv'));
  const ns = path.join(dash, 'Tools', 'new-section.mjs');
  const cases = {};
  ofType('chart', 'table', 'hero card').forEach(id => variants(id).forEach(v => { cases[caseName(id, v)] = run('dashboard', `${id} ${v}`, process.execPath, [ns, caseName(id, v), '--use', id, '--page', 'overview', '--tables', 'data', ...slotArgs(noteOf(id), v)], dash).res; }));
  // the check's errors name their section: each one fails the case that added it
  const chk = run('dashboard', 'check', process.execPath, [path.join(dash, 'Tools', 'check.mjs')], dash);
  chk.lines.filter(l => /^ERROR section s\d+_/.test(l)).forEach(l => { const c = cases[l.match(/^ERROR section s\d+_(\w+)/)[1]]; if (c && c.status !== 'FAIL') { c.status = 'FAIL'; c.why = `check: ${l.replace(/^ERROR section \S+\s*/, '')}`.slice(0, 200); say(c); } });
  if (shots) run('dashboard', 'build', process.execPath, [path.join(dash, 'node_modules', 'vite', 'bin', 'vite.js'), 'build'], dash);
}

/* ---------- run, then summarise ---------- */
({ report, deck, dashboard, all: () => { report(); deck(); dashboard(); } }[target] || (() => { console.error(`STOP: --target is report, deck, dashboard or all`); process.exit(1); }))();
const lines = results.map(r => `${r.status}\t${r.tgt}\t${r.label}\t${r.why}`);
const summary = ['', 'target     pass  manual  fail'];
[...new Set(results.map(r => r.tgt))].forEach(t => { const c = s => results.filter(r => r.tgt === t && r.status === s).length; summary.push(`${t.padEnd(10)} ${String(c('PASS')).padStart(4)}  ${String(c('MANUAL')).padStart(6)}  ${String(c('FAIL')).padStart(4)}`); });
const causes = {};
results.filter(r => r.status === 'FAIL').forEach(r => { const k = `${r.tgt}: ${r.why.replace(/\b[A-Z]{2}-\d{2}\b/g, '<id>').replace(/\b\w+_(all|optional_out|required_out|anim)\b/g, '<case>').slice(0, 140)}`; (causes[k] = causes[k] || []).push(r.label.split(' ')[0]); });
const causeLines = Object.keys(causes).map(k => `FAIL ${causes[k].length}x ${k}\n     ${[...new Set(causes[k])].join(' ')}`);
const file = path.join(tmp, 'results.txt');
fs.writeFileSync(file, lines.concat(summary, '', causeLines).join('\n') + '\n');
console.log(summary.concat('', causeLines, '', `Results: ${file}`).join('\n'));
process.exit(results.some(r => r.status === 'FAIL') ? 1 : 0);
