// npm run dev [-- --open] [-- --port 5173] [-- --host]      npm run stop stops it
//
// Keeps running. Prints the page address (Local: http://localhost:<port>/). Starts the Analysis server (Analysis/server.py, with the Python named in dashboard.config.json) first, then the
// dashboard (Vite), which forwards /api to it. Every setting comes from dashboard.config.json; nothing is read
// from environment variables. Closing this window (or Ctrl+C) stops both.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { createServer } from 'vite';
import { ROOT as root, pythonCommand, readJsonFile } from './py.mjs';

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const value = (name) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : null;
};
const config = readJsonFile(path.join(root, 'dashboard.config.json'));
const RUNNING = path.join(root, 'Data', '.dev.json'); // process ids, for npm run stop
let port = Number(config.server?.port || 8765);
const python = pythonCommand();

const inUse = (p) =>
  new Promise((resolve) => {
    const s = net.connect(p, '127.0.0.1');
    s.once('connect', () => (s.destroy(), resolve(true)));
    s.once('error', () => resolve(false));
  });

/** Is the server on this port this project's Analysis server? (anything else: another dashboard, another app) */
async function ours(p) {
  try {
    const r = await fetch(`http://127.0.0.1:${p}/api/project`, { signal: AbortSignal.timeout(1500) });
    const { root: theirs } = await r.json();
    return path.resolve(theirs).toLowerCase() === path.resolve(root).toLowerCase();
  } catch {
    return false;
  }
}

let reuse = false;
if (await inUse(port)) {
  if (await ours(port)) {
    reuse = true;
  } else {
    const wanted = port;
    let free = null;
    for (let p = wanted + 1; p <= wanted + 50 && free === null; p++) if (!(await inUse(p))) free = p;
    if (free === null) {
      console.log(`[analysis] port ${wanted} is used by something else and no free port was found nearby. Set "server": { "port": ... } in dashboard.config.json.`);
      process.exit(1);
    }
    console.log(`[analysis] port ${wanted} is used by something else (not this dashboard); using ${free} instead. To make it stick, set "server": { "port": ${free} } in dashboard.config.json.`);
    port = free;
  }
}

const children = [];
let server = null;
const stop = async (code = 0) => {
  for (const c of children) if (!c.killed) c.kill();
  fs.rmSync(RUNNING, { force: true });
  if (server) await server.close().catch(() => {});
  process.exit(code);
};

if (reuse) {
  console.log(`[analysis] this dashboard's server is already running on port ${port}; using it`);
} else {
  const api = spawn(python, [path.join(root, 'Analysis', 'server.py'), '--port', String(port)], { cwd: root, stdio: 'inherit' });
  api.on('error', (e) => console.log(`[analysis] could not start "${python}": ${e.message}. Set "python" in dashboard.config.json.`));
  api.on('exit', (code) => {
    if (code) console.log(`[analysis] server stopped (exit ${code}). Python 3 with fastapi, uvicorn, duckdb, pandas, pyarrow is needed.`);
  });
  children.push(api);
  for (let i = 0; i < 60 && !(await inUse(port)); i++) await new Promise((r) => setTimeout(r, 250));
}

server = await createServer({
  root,
  configFile: path.join(root, 'vite.config.js'),
  server: {
    proxy: { '/api': `http://127.0.0.1:${port}` },
    open: flag('open'),
    ...(value('port') ? { port: Number(value('port')) } : {}),
    ...(flag('host') ? { host: value('host') ?? true } : {}),
  },
});
await server.listen();
server.printUrls();
fs.mkdirSync(path.dirname(RUNNING), { recursive: true });
fs.writeFileSync(RUNNING, `${JSON.stringify({ pids: [process.pid, ...children.map((c) => c.pid)], page: server.resolvedUrls?.local?.[0] ?? null, apiPort: port })}
`);
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => stop(0));
