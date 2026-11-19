// npm run shot -- [tab] [out.png] [filter=value ...]
// A screenshot of the dashboard, e.g. npm run shot -- costs costs-west.png region=West
// Uses the running npm run dev, or starts one and stops it afterwards. Finds Edge or Chrome in the standard install
// places or on the path, waits until no section says Loading, and prints the file's path.
// Default file: Data/.shots/<tab>-<date-time>.png.
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
const tab = args.find((a) => !a.includes('=') && a !== out) ?? null;
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

const hash = new URLSearchParams({ ...(tab ? { tab } : {}), ...filters }).toString();
const url = `${page.replace(/\/$/, '/')}${hash ? `#${hash}` : ''}`;
const file = path.resolve(out ?? path.join(SHOTS, `${tab ?? 'page'}-${new Date().toISOString().replace(/[-:]/g, '').replace('T', '-').slice(0, 15)}.png`));
fs.mkdirSync(path.dirname(file), { recursive: true });
const base = ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--user-data-dir=${path.join(SHOTS, '.profile')}`, '--window-size=1280,1800'];
let budget = 15000;
for (let i = 0; i < 3; i++) {   // wait until no section says Loading
  const dom = spawnSync(exe, [...base, `--virtual-time-budget=${budget}`, '--dump-dom', url], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (!/Loading…/.test(dom.stdout ?? '')) break;
  budget *= 2;
}
spawnSync(exe, [...base, `--virtual-time-budget=${budget}`, `--screenshot=${file}`, url], { stdio: 'ignore' });

if (started) {
  const { pids = [] } = fs.existsSync(RUNNING) ? JSON.parse(fs.readFileSync(RUNNING, 'utf8')) : {};
  for (const pid of pids) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    else try { process.kill(pid); } catch { /* gone */ }
  }
  fs.rmSync(RUNNING, { force: true });
}
console.log(fs.existsSync(file) ? `shot: ${file} (${url})` : `shot: the browser wrote no file for ${url}`);
