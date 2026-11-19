// Prints the section registry (Src/Sections/index.js) as one JSON line: { sections: [{ meta, note, hasDefault,
// oldCommentary }], tabs } or { error }. Used by project.mjs, which runs it as its own process: loading JSX needs a
// Vite dev server, and that must not share a process with the export build (Vite would mark the build as dev).
import path from 'node:path';
import { createServer } from 'vite';
import { ROOT } from './py.mjs';

let out;
const vite = await createServer({
  root: ROOT,
  configFile: path.join(ROOT, 'vite.config.js'),
  logLevel: 'error',
  appType: 'custom',
  server: { middlewareMode: true, hmr: false, watch: null },
  // own dependency cache: sharing the running dashboard's (node_modules/.vite) would disturb it while it runs
  cacheDir: path.join(ROOT, 'node_modules', '.vite-scripts'),
});
try {
  const mod = await vite.ssrLoadModule('/Src/Sections/index.js');
  const list = Array.isArray(mod.default) ? mod.default : null;
  out = {
    sections: list?.map((m) => ({
      meta: m?.meta ?? null,
      note: m?.note,
      hasDefault: typeof m?.default === 'function',
      oldCommentary: m?.commentary !== undefined,
    })) ?? null,
    tabs: mod.tabs ?? [],
  };
} catch (e) {
  out = { error: e.message };
} finally {
  await vite.close();
}
console.log(`\n${JSON.stringify(out)}`);
