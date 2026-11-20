// npm run shot -- [tab or section id] [out.png] [filter=value ...]
// A screenshot of the dashboard, e.g. npm run shot -- costs costs-west.png region=West, or of one section alone:
// npm run shot -- s8_paid_by_month s8.png
// Uses the running npm run dev, or starts its own and stops it afterwards (no npm run stop needed). Finds Edge or
// Chrome in the standard install places or on the path, waits until no section says Loading, crops to the page's
// height, and prints the file's path, then any drawing faults the page found (text cut off, labels overlapping).
// Default file: Data/.shots/<tab>-<date-time>.png; a bare out.png also lands in Data/.shots/. For looking, not kept.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ROOT } from './py.mjs';

const RUNNING = path.join(ROOT, 'Data', '.dev.json');
const SHOTS = path.join(ROOT, 'Data', '.shots');
const args = process.argv.slice(2);
const filters = Object.fromEntries(args.filter((a) => a.includes('=')).map((a) => a.split(/=(.*)/s).slice(0, 2)));
const out = args.find((a) => /\.png$/i.test(a));
const target = args.find((a) => !a.includes('=') && a !== out) ?? null;
const only = target && /^s\d+_/.test(target) ? target : null; // a section id: that section alone
let tab = only ? null : target;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function browser() {
  const home = os.homedir();
  const places = {
    win32: ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
      'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
      path.join(home, 'AppData/Local/Google/Chrome/Application/chrome.exe'), path.join(home, 'AppData/Local/Microsoft/Edge/Application/msedge.exe')],
    darwin: ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
  }[process.platform] ?? [];
  const found = places.find((p) => fs.existsSync(p));
  if (found) return found;
  const names = process.platform === 'win32' ? ['msedge', 'chrome'] : ['microsoft-edge', 'msedge', 'google-chrome', 'chromium', 'chromium-browser'];
  for (const n of names) {
    const r = spawnSync(process.platform === 'win32' ? 'where' : 'which', [n], { encoding: 'utf8' });
    const hit = r.status === 0 && r.stdout.trim().split(/\r?\n/)[0];
    if (hit) return hit;
  }
  console.log(`shot: no browser found. Looked for Edge or Chrome in ${places.join(', ') || 'the standard places'} and for ${names.join(', ')} on the path.`);
  process.exit(1);
}

const pageUp = async (url) => {
  try {
    return (await fetch(url, { signal: AbortSignal.timeout(2000) })).ok;
  } catch {
    return false;
  }
};

// the tab or section must exist: a wrong one would only give a useless picture
const indexSrc = fs.readFileSync(path.join(ROOT, 'Src', 'Sections', 'index.js'), 'utf8');
const sectionIds = [...indexSrc.matchAll(/import\s+\*\s+as\s+(s\d+_\w+)\s+from/g)].map((m) => m[1]);
const tabIds = [.../export\s+const\s+tabs\s*=\s*\[([\s\S]*?)\]/.exec(indexSrc)?.[1].matchAll(/id\s*:\s*['"]([^'"]+)['"]/g) ?? []].map((m) => m[1]);
if (only && !sectionIds.includes(only)) {
  console.log(`shot: no section ${only} (sections: ${sectionIds.join(', ') || 'none'})`);
  process.exit(1);
}
if (tab && !tabIds.length) {   // no tabs yet (or one page): the whole page
  console.log(`shot: no tabs yet, so the whole page${sectionIds.length ? '' : ' (no sections yet)'}`);
  tab = null;
}
if (tab && !tabIds.includes(tab)) {
  console.log(`shot: no tab or section "${tab}" (tabs: ${tabIds.join(', ') || 'none, one page'}; sections: ${sectionIds.join(', ')})`);
  process.exit(1);
}

const exe = browser();
let started = null;
let page = fs.existsSync(RUNNING) ? JSON.parse(fs.readFileSync(RUNNING, 'utf8')).page : null;
if (!page || !(await pageUp(page))) {
  console.log('shot: starting npm run dev for this shot');
  fs.rmSync(RUNNING, { force: true });
  started = spawn(process.execPath, [path.join(ROOT, 'Tools', 'dev.mjs')], { cwd: ROOT, stdio: 'ignore' });
  for (let i = 0; i < 120 && !fs.existsSync(RUNNING); i++) await sleep(500);
  page = fs.existsSync(RUNNING) ? JSON.parse(fs.readFileSync(RUNNING, 'utf8')).page : null;
  if (!page) {
    started.kill();
    console.log('shot: npm run dev did not start; run it yourself to see why');
    process.exit(1);
  }
}

const hash = new URLSearchParams({ ...(only ? { only } : {}), ...(tab ? { tab } : {}), ...filters }).toString();
const url = `${page.replace(/\/$/, '/')}${hash ? `#${hash}` : ''}`;
// a bare file name goes in Data/.shots/ too (git-ignored); a path with a folder is used as given
const file = path.resolve(out ? (/[\\/]/.test(out) ? out : path.join(SHOTS, out)) : path.join(SHOTS,`${target ?? 'page'}-${new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15)}.png`));
fs.mkdirSync(path.dirname(file), { recursive: true });
const base = ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--user-data-dir=${path.join(SHOTS, '.profile')}`];
let budget = 15000;
let height = 1800;
let dom = null;
for (let i = 0; i < 3; i++) {   // wait until no section says Loading; read the page's height
  dom = spawnSync(exe, [...base, '--window-size=1280,1800', `--virtual-time-budget=${budget}`, '--dump-dom', url], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  const h = Number(/data-height="(\d+)"/.exec(dom.stdout ?? '')?.[1]);
  if (h) height = Math.min(Math.max(h, 400), 12000);
  if (!/Loading…/.test(dom.stdout ?? '')) break;
  budget *= 2;
}
spawnSync(exe, [...base, `--window-size=1280,${height}`, `--virtual-time-budget=${budget}`, `--screenshot=${file}`, url], { stdio: 'ignore' });

if (started) {
  const { pids = [] } = fs.existsSync(RUNNING) ? JSON.parse(fs.readFileSync(RUNNING, 'utf8')) : {};
  for (const pid of pids) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    else try { process.kill(pid); } catch { /* gone */ }
  }
  fs.rmSync(RUNNING, { force: true });
}
console.log(fs.existsSync(file) ? `shot: ${file} (${url})` : `shot: the browser wrote no file for ${url}`);
// drawing faults the page found in library items (text cut off at a chart's edge, labels on top of each other,
// slots naming a missing column): one line per section
const unescape = (t) => t.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
for (const m of (dom?.stdout ?? '').matchAll(/<section\b[^>]*>/g)) {
  const sid = /\bid="([^"]+)"/.exec(m[0])?.[1];
  const faults = /\bdata-faults="([^"]*)"/.exec(m[0])?.[1];
  if (sid && faults) console.log(`check ${sid}: ${unescape(faults)}`);
}
