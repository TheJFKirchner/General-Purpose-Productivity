#!/usr/bin/env node

/**
 * Screenshots every slide of a presentation with a headless Edge or Chrome already on the machine,
 * then joins them into one contact sheet, sheet.png: read that one image, not each slide.
 * No dependencies. Images are for checking the deck; keep them out of the presentation folder.
 *
 * Usage: node screenshot.js <path-to-html> [<output-dir> or -] [slide-id ...] [--browser <path>]
 * Default output: <system temp>/deck-shots/<deck folder name>/.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');

const BROWSERS = [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/usr/bin/microsoft-edge',
];

function main() {
  const args = process.argv.slice(2);
  const b = args.indexOf('--browser');
  const given = b !== -1 ? args.splice(b, 2)[1] : null;
  let [htmlPath, outDir, ...only] = args;
  if (!htmlPath) {
    console.error('Usage: node screenshot.js <path-to-html> [<output-dir> or -] [slide-id ...] [--browser <path>]');
    process.exit(1);
  }
  // default (no folder, or -): the system temp folder, deck-shots/<deck folder name>; for looking, not kept
  if (!outDir || outDir === '-') outDir = path.join(os.tmpdir(), 'deck-shots', path.basename(path.dirname(path.resolve(htmlPath))));
  const browser = [given, ...BROWSERS].filter(Boolean).find(p => fs.existsSync(p));
  if (!browser) {
    console.error('STOP: no Edge or Chrome found. Pass --browser <path to the browser>, or look at the deck in a browser instead.');
    process.exit(1);
  }

  const html = fs.readFileSync(htmlPath, 'utf8');
  const start = html.indexOf('<!-- SLIDES:START -->');
  const end = html.indexOf('<!-- SLIDES:END -->');
  const slidesHtml = start !== -1 && end !== -1 ? html.slice(start, end) : html;
  const ids = [...slidesHtml.matchAll(/<section\b[^>]*\bid="([^"]+)"/g)].map(m => m[1]);
  const wanted = only.length ? ids.filter(id => only.includes(id)) : ids;
  if (wanted.length === 0) {
    console.error('STOP: no slides with an id found' + (only.length ? ' matching ' + only.join(', ') : '') + '.');
    process.exit(1);
  }

  fs.mkdirSync(outDir, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'deck-shot-'));
  const base = pathToFileURL(path.resolve(htmlPath)).href;
  let failed = 0;

  wanted.forEach(id => {
    const n = String(ids.indexOf(id) + 1).padStart(2, '0');
    const file = path.resolve(outDir, `${n}-${id}.png`);
    if (fs.existsSync(file)) fs.rmSync(file);
    const result = spawnSync(browser, [
      '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
      `--user-data-dir=${profile}`,
      '--window-size=1280,720', '--virtual-time-budget=6000',
      `--screenshot=${file}`,
      `${base}?export#/${id}`,
    ], { stdio: 'ignore', timeout: 60000 });
    if (fs.existsSync(file)) {
      console.log(`${n}-${id}.png`);
    } else {
      failed++;
      console.log(`FAILED ${id}${result.error ? ': ' + result.error.message : ''}`);
    }
  });

  // Contact sheet: two slides a row at half size, each captioned with its number and id
  const shots = wanted.map(id => `${String(ids.indexOf(id) + 1).padStart(2, '0')}-${id}.png`).filter(f => fs.existsSync(path.resolve(outDir, f)));
  const sheet = path.resolve(outDir, 'sheet.png');
  if (fs.existsSync(sheet)) fs.rmSync(sheet);
  if (shots.length) {
    const page = path.resolve(outDir, 'sheet.html');
    const tiles = shots.map(f => `<figure><img src="${f}"><figcaption>${f.slice(0, -4)}</figcaption></figure>`).join('');
    fs.writeFileSync(page, '<!doctype html><html><body style="margin:0;padding:10px;background:#5B6770;font:600 13px Segoe UI,sans-serif;">' +
      '<style>div{display:grid;grid-template-columns:640px 640px;gap:10px}figure{margin:0;background:#fff}img{display:block;width:640px;height:360px}' +
      `figcaption{padding:3px 8px;color:#002D72}</style><div>${tiles}</div></body></html>`);
    spawnSync(browser, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', `--user-data-dir=${profile}`,
      `--window-size=1310,${20 + Math.ceil(shots.length / 2) * 394}`, '--virtual-time-budget=2000', `--screenshot=${sheet}`,
      pathToFileURL(page).href], { stdio: 'ignore', timeout: 60000 });
    try { fs.rmSync(page); } catch (e) { /* ignore */ }
  }

  try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* profile may still be locked */ }
  if (fs.existsSync(sheet)) console.log(`Contact sheet (read this one image): ${sheet}`);
  console.log(`\n${wanted.length - failed} of ${wanted.length} slides saved to ${path.resolve(outDir)}`);
  if (failed) process.exit(1);
}

main();
