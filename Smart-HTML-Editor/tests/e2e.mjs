// End-to-end check of the editor in a real browser, with the scripted test model (no tokens).
//   python editor/she.py open <copy of a sample>.html --no-open --fake --port 8790
//   node tests/e2e.mjs http://127.0.0.1:8790/ <that file> [screenshot.png]
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [url = 'http://127.0.0.1:8790/', file, shot] = process.argv.slice(2);
const original = fs.readFileSync(file, 'utf8');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('dialog', (d) => d.accept());
let failures = 0;
const check = (ok, what) => { console.log((ok ? 'ok   ' : 'FAIL ') + what); if (!ok) failures++; };
const frame = () => page.frameLocator('#page');
const settle = (ms = 1500) => page.waitForTimeout(ms);
const chat = async (steps) => {
  await page.fill('#prompt', 'FAKE: ' + JSON.stringify(steps));
  await page.click('#send');
  await page.waitForFunction(() => !document.querySelector('.msg.thinking'), null, { timeout: 15000 });
  return page.locator('.msg.bot, .msg.err').last().innerText();
};

await page.goto(url);
await frame().locator('h1').waitFor();
await settle(800);

// 1. click selects
await frame().locator('h1').click();
await settle(500);
check((await page.locator('#crumbs .current').innerText()) === 'h1', 'click selects the heading');

// 2. double-click and type
const sub = frame().locator('p.subtitle');
await sub.dblclick();
await frame().locator('p.subtitle[contenteditable]').waitFor();
await page.keyboard.press('End');
await page.keyboard.type(' (draft)');
await page.keyboard.press('Enter');
await settle(800);
let served = await (await page.request.get(url + 'doc/' + file.split('/').pop())).text();
check(served.includes('Prepared for the regional leadership team &amp; finance (draft)'), 'typed text reaches the document (entity kept escaped)');
check((await page.locator('#status').innerText()).includes('unsaved'), 'status shows unsaved changes');

// 3. typing that breaks structure is undone; typing in data cells is blocked in Hide data mode
await page.check('#hide-data');
await frame().locator('td').first().dblclick();
await settle(400);
check((await page.locator('#toast').innerText()).includes('Hide data'), 'Hide data blocks typing in table cells');
const blur = await frame().locator('td').first().evaluate((el) => getComputedStyle(el).filter);
check(blur.includes('blur'), 'Hide data blurs table cells');
await page.uncheck('#hide-data');

// 4. quick color on the selection
await frame().locator('#summary h2').click();
await settle(400);
await page.locator('#q-color').evaluate((el) => { el.value = '#b91c1c'; el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); });
await settle(600);
check((await frame().locator('#summary h2').evaluate((el) => getComputedStyle(el).color)) === 'rgb(185, 28, 28)', 'quick color applies live');

// 5. assistant: look at styles (answered by the page), step out, edit there
const sel = await (await page.request.get(url + 'api/state')).json();
let reply = await chat([{ styles: sel.selected }]);
check(/text #b91c1c/.test(reply) && /\.card h2/.test(reply), 'assistant gets computed looks and matching rules from the page');
check(!/12\.4|4\.2M|48,210/.test(reply), 'looks contain no data');
reply = await chat([{ select: 'n11' }, { style: ['n11', { background: '#fef3c7' }] }, { say: 'Done on the card around it.' }]);
check(reply.includes('Done on the card around it.'), 'assistant steps out and edits: ' + reply.slice(0, 80));
await settle(2500);
check((await frame().locator('#summary').evaluate((el) => getComputedStyle(el).backgroundColor)) === 'rgb(254, 243, 199)', 'page reloaded with the card background');
check((await page.locator('#crumbs .current').innerText()).startsWith('section#summary'), 'assistant selection shows in the panel');

// 6. assistant: text with number tokens; typed numbers refused
reply = await chat([{ text: ['t21', 'Sales rose {#1} to {#2} this quarter, led by the'] }, { text: ['t21', 'Sales rose 50% to {#2}'] }]);
check(reply.includes('text: Done') && reply.includes('typed number'), 'tokens keep numbers; invented numbers refused');
await settle(2000);
check((await frame().locator('#summary p').first().innerText()).startsWith('Sales rose 12.4% to $4.2M'), 'reworded text shows with real numbers');

// 7. theme panel
await page.click('[data-tab=theme]');
await settle(500);
const accent = page.locator('.var').first().locator('input[type=text]');
await accent.fill('#0f766e');
await accent.dispatchEvent('change');
await settle(2500);
check((await frame().locator('header.top').evaluate((el) => getComputedStyle(el).backgroundColor)) === 'rgb(15, 118, 110)', 'theme variable recolors the page');

// 8. page rule from the assistant
await page.click('[data-tab=assistant]');
reply = await chat([{ rule: ['.kpi .label', 'letter-spacing: .1em; color: #0f766e'] }]);
await settle(2500);
check((await frame().locator('.kpi .label').first().evaluate((el) => getComputedStyle(el).color)) === 'rgb(15, 118, 110)', 'page rule applies');

// 9. undo, then save
await page.click('#undo');
await settle(2500);
check((await frame().locator('.kpi .label').first().evaluate((el) => getComputedStyle(el).color)) !== 'rgb(15, 118, 110)', 'undo removes the last change');
if (shot) await page.screenshot({ path: shot });
await page.click('#save');
await settle(800);
const saved = fs.readFileSync(file, 'utf8');
check(saved.includes('Sales rose 12.4% to $4.2M') && saved.includes('--accent: #0f766e') && !saved.includes('data-she-id'), 'save writes the changes and nothing else of the editor');
check(saved.includes(original.slice(original.indexOf('<tbody>'), original.indexOf('</tbody>'))), 'data table bytes untouched');
check(fs.readdirSync(file.replace(/[^/]+$/, '') + '.smart-html-editor/backups').length >= 1, 'backup of the original exists');
check(errors.length === 0, 'no page errors ' + errors.join('; '));
await browser.close();
console.log(failures ? `${failures} failed` : 'all passed');
process.exit(failures ? 1 : 0);
