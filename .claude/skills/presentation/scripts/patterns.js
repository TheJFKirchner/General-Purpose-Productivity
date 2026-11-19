#!/usr/bin/env node

/**
 * Prints the named sample slides from the design library, each whole and nothing else,
 * so every pattern a deck needs comes back in one call. No dependencies.
 *
 * Usage: node patterns.js <design-library folder> <name> [<name> ...]
 *   names are slide ids from index.md, such as paired-bars-commentary
 */

const fs = require('fs');
const path = require('path');

const [lib, ...names] = process.argv.slice(2);
if (!lib || !names.length) {
  console.error('Usage: node patterns.js <design-library folder> <name> [<name> ...]');
  process.exit(1);
}
const dir = path.join(lib, 'slides');
if (!fs.existsSync(dir)) { console.error(`STOP: no slides folder in ${lib}`); process.exit(1); }

const found = {};
fs.readdirSync(dir, { withFileTypes: true }).filter(d => d.isDirectory()).forEach(d => {
  const file = path.join(dir, d.name, 'slides.html');
  if (!fs.existsSync(file)) return;
  const html = fs.readFileSync(file, 'utf8');
  names.forEach(name => {
    const at = html.indexOf(`<section id="${name}"`);
    if (at === -1 || found[name]) return;
    const end = html.indexOf('</section>', at);
    found[name] = `<!-- ${d.name}/slides.html#/${name} -->\n` + html.slice(at, end + '</section>'.length)
      .replace(/ data-component="[^"]*"/, '');
  });
});

names.forEach(name => console.log(found[name] ? found[name] + '\n' : `<!-- NOT FOUND: ${name} -->\n`));
if (names.some(n => !found[n])) process.exit(1);
