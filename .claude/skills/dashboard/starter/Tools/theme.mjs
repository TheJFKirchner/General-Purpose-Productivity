// npm run theme -- TH-02 [--library <folder>]
// Takes a theme from the design library by its id, writes it to Themes/<id>/ and makes it the dashboard's theme
// ("theme" in dashboard.config.json). Without an id: lists the library's themes.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, readJsonFile } from './py.mjs';
import { findLibrary, writeTheme } from './library.mjs';

const argv = process.argv.slice(2);
const at = argv.indexOf('--library');
const given = at >= 0 ? argv[at + 1] : null;
const id = argv.find((a, i) => /^TH-\d\d$/i.test(a) && argv[i - 1] !== '--library')?.toUpperCase();
const lib = findLibrary(given);
if (!id) {
  const list = path.join(lib, 'index', 'themes.md');
  console.log(fs.existsSync(list) ? fs.readFileSync(list, 'utf8').split('\n').filter((l) => l.startsWith('- TH')).join('\n') : 'Give a theme id, e.g. npm run theme -- TH-02');
  process.exit(id === undefined && argv.length ? 1 : 0);
}
const th = writeTheme(lib, id);
const file = path.join(ROOT, 'dashboard.config.json');
const cfg = readJsonFile(file);
cfg.theme = th.id;
fs.writeFileSync(file, `${JSON.stringify(cfg, null, 2)}\n`);
console.log(`theme: ${th.id} ${th.name} (Themes/${th.id}/), now the dashboard's theme. A running npm run dev picks it up on reload.`);
