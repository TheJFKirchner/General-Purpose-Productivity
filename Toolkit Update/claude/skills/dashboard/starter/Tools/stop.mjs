// npm run stop: stops this dashboard's npm run dev (the page and the Python server), using the process ids
// npm run dev wrote to Data/.dev.json. Closing the window that started it does not always stop both.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, readJsonFile } from './py.mjs';

const RUNNING = path.join(ROOT, 'Data', '.dev.json');
if (!fs.existsSync(RUNNING)) {
  const port = readJsonFile(path.join(ROOT, 'dashboard.config.json')).server?.port ?? 8765;
  let answers = false;
  try {
    answers = (await fetch(`http://127.0.0.1:${port}/api/meta`, { signal: AbortSignal.timeout(1500) })).ok;
  } catch { /* nothing there */ }
  console.log(answers
    ? `stop: a server answers on port ${port}, but npm run dev here did not start it; close the window it runs in`
    : 'stop: no dashboard server is running (npm run shot stops the one it starts)');
  process.exit(0);
}
const { pids = [] } = JSON.parse(fs.readFileSync(RUNNING, 'utf8'));
for (const pid of pids) {
  if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
  else {
    try {
      process.kill(pid);
    } catch { /* already gone */ }
  }
}
fs.rmSync(RUNNING, { force: true });
console.log(`stop: stopped ${pids.length} process(es)`);
