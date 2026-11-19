// The Python command for this dashboard: "python" in dashboard.config.json (default: python, or python3 off Windows).
// npm run pipeline / serve run Python through it:  node Tools/py.mjs <script> [args]
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** A JSON file as Windows tools write it too (byte-order mark, CRLF); a clear message naming the file when broken. */
export function readJsonFile(file) {
  const text = fs.readFileSync(file, 'utf8').replace(/^﻿/, '');
  try {
    return JSON.parse(text);
  } catch (e) {
    const pos = Number(/position (\d+)/.exec(e.message)?.[1]);
    const line = Number.isFinite(pos) ? text.slice(0, pos).split('\n').length : null;
    throw new Error(`${path.relative(ROOT, file) || file} is not valid JSON${line ? ` at line ${line}` : ''}: ${e.message}`);
  }
}

export function pythonCommand() {
  try {
    const c = readJsonFile(path.join(ROOT, 'dashboard.config.json'));
    if (typeof c.python === 'string' && c.python.trim()) return c.python.trim();
  } catch { /* no or broken config: the default */ }
  return process.platform === 'win32' ? 'python' : 'python3';
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const py = pythonCommand();
  const r = spawnSync(py, process.argv.slice(2), { cwd: ROOT, stdio: 'inherit' });
  if (r.error) console.log(`could not run "${py}": ${r.error.message}. Set "python" in dashboard.config.json to the Python to use.`);
  process.exit(r.status ?? 1);
}
