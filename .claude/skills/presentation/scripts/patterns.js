#!/usr/bin/env node

/**
 * Prints the reusable part of the named design-library items (between ITEM:START and ITEM:END),
 * so every pattern a deck needs comes back in one call. No dependencies.
 *
 * Usage: node patterns.js <design-library folder> <id or name> [<id or name> ...]
 *   ids such as LV-05 or CT-03, from index.md; a slide's name (bars-highlight-commentary) works too
 */

const fs = require('fs');
const path = require('path');

const [lib, ...want] = process.argv.slice(2);
if (!lib || !want.length) {
  console.error('Usage: node patterns.js <design-library folder> <id or name> [<id or name> ...]');
  process.exit(1);
}
if (!fs.existsSync(lib)) { console.error(`STOP: no folder ${lib}`); process.exit(1); }

const found = {};
fs.readdirSync(lib, { withFileTypes: true }).filter(d => d.isDirectory()).forEach(d => {
  fs.readdirSync(path.join(lib, d.name)).filter(f => f.endsWith('.html')).forEach(f => {
    const text = fs.readFileSync(path.join(lib, d.name, f), 'utf8');
    const id = (text.match(/^id:\s*(\S+)/m) || [])[1];
    const name = (text.match(/^name:\s*(\S+)/m) || [])[1];
    const key = want.find(w => w === id || w === name);
    if (!key || found[key]) return;
    const a = text.indexOf('<!-- ITEM:START -->'), b = text.indexOf('<!-- ITEM:END -->');
    const part = a !== -1 && b !== -1 ? text.slice(a + '<!-- ITEM:START -->'.length, b).trim() : null;
    found[key] = `<!-- ${id} ${name} (${d.name}/${f}) -->\n` + (part || '(no ITEM:START/END block: open the file)')
      .replace(/ data-component="[^"]*"/, '');
  });
});

want.forEach(w => console.log(found[w] ? found[w] + '\n' : `<!-- NOT FOUND: ${w}; see index.md -->\n`));
if (want.some(w => !found[w])) process.exit(1);
