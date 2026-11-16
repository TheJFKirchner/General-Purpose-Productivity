#!/usr/bin/env node

/**
 * Screenshots every slide of a presentation with a headless Edge or Chrome already on the machine.
 * No dependencies. Images are for checking the deck; keep them out of the presentation folder.
 *
 * Usage: node screenshot.js <path-to-html> <output-dir> [slide-id ...]
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { pathToFileURL } = require('url');

const BROWSERS = [
  process.env.DECK_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/usr/bin/microsoft-edge',
].filter(Boolean);

function main() {
  const [htmlPath, outDir, ...only] = process.argv.slice(2);
  if (!htmlPath || !outDir) {
    console.error('Usage: node screenshot.js <path-to-html> <output-dir> [slide-id ...]');
    process.exit(1);
  }
  const browser = BROWSERS.find(p => fs.existsSync(p));
  if (!browser) {
    console.error('STOP: no Edge or Chrome found. Set DECK_BROWSER to the browser path, or look at the deck in a browser instead.');
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

  try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* profile may still be locked */ }
  console.log(`\n${wanted.length - failed} of ${wanted.length} slides saved to ${path.resolve(outDir)}`);
  if (failed) process.exit(1);
}

main();
