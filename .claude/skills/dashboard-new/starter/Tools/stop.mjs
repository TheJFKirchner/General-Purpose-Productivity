// npm run stop: stops this dashboard's npm run dev (the page and the Python server), using the process ids
// npm run dev wrote to Data/.dev.json. Closing the window that started it does not always stop both.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './py.mjs';

const RUNNING = path.join(ROOT, 'Data', '.dev.json');
if (!fs.existsSync(RUNNING)) {
  console.log('stop: nothing recorded as running (no Data/.dev.json)');
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
