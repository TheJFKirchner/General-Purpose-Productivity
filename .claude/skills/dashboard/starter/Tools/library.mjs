// The design library, for npm run new-section -- --use and npm run theme. Found, in order: --library <folder>;
// "library" in dashboard.config.json (relative to this dashboard); then, walking up from this dashboard, a project
// CLAUDE.md line "Design library: <folder>", a design-library folder beside a .claude folder, or
// Toolkit Update/design-library. A folder found any other way than the config is saved there for next time.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { ROOT, readJsonFile } from './py.mjs';

const CONFIG = path.join(ROOT, 'dashboard.config.json');
const isLibrary = (d) => Boolean(d) && fs.existsSync(path.join(d, 'item.js'));

function* candidates(given) {
  if (given) yield ['--library', path.resolve(given)];
  const saved = readJsonFile(CONFIG).library;
  if (saved) yield ['dashboard.config.json', path.resolve(ROOT, saved)];
  for (let d = ROOT; ; d = path.dirname(d)) {
    const map = path.join(d, 'CLAUDE.md');
    if (fs.existsSync(map)) {
      const m = /Design library:\s*`?([^`\n]+?)`?\s*$/m.exec(fs.readFileSync(map, 'utf8'));
      if (m) yield ['CLAUDE.md', path.resolve(d, m[1].trim())];
    }
    if (fs.existsSync(path.join(d, '.claude'))) yield ['beside .claude', path.join(d, 'design-library')];
    yield ['Toolkit Update', path.join(d, 'Toolkit Update', 'design-library')];
    if (path.dirname(d) === d) break;
  }
}

/** The library folder, or exit with what was tried. */
export function findLibrary(given) {
  const tried = [];
  for (const [how, dir] of candidates(given)) {
    if (isLibrary(dir)) {
      if (how !== 'dashboard.config.json') save(dir);
      return dir;
    }
    if (how !== 'Toolkit Update' && how !== 'beside .claude') tried.push(`${dir} (${how})`);
  }
  console.log(`No design library found${tried.length ? `; tried ${tried.join(', ')}` : ''}. Give its folder once with --library <folder>.`);
  process.exit(1);
}

function save(dir) {
  const cfg = readJsonFile(CONFIG);
  const rel = path.relative(ROOT, dir);
  const near = rel && !path.isAbsolute(rel) && rel.split(path.sep).filter((x) => x === '..').length <= 3;   // a near folder moves with the project
  const value = (near ? rel : dir).split(path.sep).join('/');
  if (cfg.library === value) return;
  cfg.library = value;
  fs.writeFileSync(CONFIG, `${JSON.stringify(cfg, null, 2)}\n`);
}

/** node item.js <args> in the library; parsed JSON with --json. */
export function itemJs(lib, args) {
  const r = spawnSync(process.execPath, ['item.js', ...args], { cwd: lib, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) {
    console.log(`the library said: ${(r.stderr || r.stdout || '').trim().split('\n').slice(-3).join(' | ')}`);
    process.exit(1);
  }
  return args.includes('--json') ? JSON.parse(r.stdout) : r.stdout;
}

/** A library theme (item.js theme <id> --json) as this dashboard's Themes/<id>/tokens.json. */
export function tokensOf(th) {
  const v = th.css;
  const c = (k) => v[`--${k}`];
  const colors = {
    blue: c('blue'), navy: c('navy'), green: c('green'), teal: c('teal'), orange: c('orange'), ink: c('ink'),
    muted: c('muted'), rule: c('rule'), wash: c('wash'), paper: c('paper'), chartMuted: c('chart-muted'),
    chartGrid: c('chart-grid'), good: c('good'), bad: c('bad'), neutral: c('neutral'), track: c('track'), tint: c('tint'),
    shadow: c('shadow'), band: c('band'), onBand: c('on-band'), menu: c('menu'), onMenu: c('on-menu'),
    text: c('ink'), textMuted: c('muted'), background: c('paper'), surface: c('wash'), border: c('rule'),
    accent: c('blue'), heading: c('navy'), warning: c('orange'),
    series: th.series.map((n) => v[n]).filter(Boolean),
    sequential: [c('wash'), c('blue'), c('navy')],
    diverging: [c('blue'), c('wash'), c('orange')],
  };
  return {
    name: th.id,
    library: `${th.id} ${th.name}`,
    colors: Object.fromEntries(Object.entries(colors).filter(([, x]) => x !== undefined)),
    font: { family: c('body-font'), heading: c('heading-font'), size: 13 },
    effects: { glow: false, gradients: false, grid: false, animation: false },
    vars: { ...v, '--series': th.series.join(' ') },
  };
}

/** Writes Themes/<id>/ (tokens.json, and fonts.css with its licence for a theme that embeds a font). */
export function writeTheme(lib, id, root = ROOT) {
  const th = itemJs(lib, ['theme', id, '--json', '--fonts']);
  const dir = path.join(root, 'Themes', th.id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'tokens.json'), `${JSON.stringify(tokensOf(th), null, 2)}\n`);
  if (th.hasFonts && th.fonts) {
    fs.writeFileSync(path.join(dir, 'fonts.css'), `${th.fonts.trim()}\n`);
    if (th.licence && fs.existsSync(path.join(lib, th.licence))) fs.copyFileSync(path.join(lib, th.licence), path.join(dir, path.basename(th.licence)));
  }
  return th;
}
