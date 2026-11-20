#!/usr/bin/env node

/**
 * Writes one library item: a single HTML file that renders by itself. No dependencies.
 * Used by the design-librarian agent, and by build-index.js to keep every item's shared blocks in step.
 *
 *   node save-item.js slide             --deck <deck.html> --slide <id|n> --group <FR|EX|LV|CH|CP|BD|UN|DE|BK>
 *   node save-item.js chart             --deck <deck.html> --slide <id|n>          (the slide's first chart)
 *   node save-item.js report-section    --report <report folder> --section <sN_name.py, path or name>
 *   node save-item.js dashboard-section --dashboard <dashboard folder> --section <section id, file or path>
 *   node save-item.js theme             --from <theme item id> --name <name>        (a copy to edit)
 *   any of them: --name <neutral-name> (default: the layout or chart kind; never a project word)
 *   node save-item.js purpose <id> "<one sentence>"                                 (sets a saved item's purpose line)
 *   node save-item.js recipe <id> "<one line>"                                      (sets a saved item's recipe line)
 *   node save-item.js new <chart|table|hero-card|animation|layout|slide> --name <name> [--group XX]   (a shell to fill by hand)
 *
 * Each save prints a "Preview:" description (layout, what the chart or table shows, the highlight, bullets
 * or note lines, what was not copied): the purpose sentence is written from it, without opening the item.
 *
 * A slide or chart is copied with a small made-up sample and neutral wording. A report or dashboard
 * section becomes the chart, table or hero card it showed, on sample data (never the project's own
 * calculation). Charts, tables and hero cards get a data note and slots (a chart's guessed from its shape),
 * slides their spots (AUTHORING.md). Project names (columns, tables, values) are recorded as hashes in
 * denylist.json so the index check can catch any that survive. The next free id; one line left to write:
 * "purpose: WRITE ...". Never writes to the source project. Use forward slashes.
 */

const fs = require('fs');
const path = require('path');

const LIB = __dirname;
const ECHARTS = 'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js';
const TYPES = { slide: 'slides', chart: 'charts', table: 'tables', 'hero card': 'hero-cards', animation: 'animations', layout: 'layout', theme: 'themes' };
const PREFIX = { chart: 'CT', table: 'TB', 'hero card': 'HC', animation: 'AN', layout: 'LY', theme: 'TH' };
const GROUPS = ['FR', 'EX', 'LV', 'CH', 'CP', 'BD', 'UN', 'DE', 'BK'];
const DEFAULT_THEME = 'TH-01';

/* ---------- header ---------- */
function readHeader(text) {
  const m = text.match(/<!-- ITEM\n([\s\S]*?)-->/);
  if (!m) return null;
  const h = {};
  m[1].split('\n').forEach(l => { const k = l.match(/^(\w+):\s*(.*)$/); if (k) h[k[1]] = k[2].trim(); });
  return h;
}
/* data: the data note (charts, tables, hero cards), recipe: how to shape the data first, when it needs it. AUTHORING.md. */
const header = h => `<!-- ITEM\nid: ${h.id}\ntype: ${h.type}\nname: ${h.name}\npurpose: ${h.purpose}\nfrom: ${h.from}\n${h.data ? `data: ${h.data}\n` : ''}${h.recipe ? `recipe: ${h.recipe}\n` : ''}-->`;

/* ---------- items on disk ---------- */
function items() {
  const out = [];
  Object.values(TYPES).forEach(dir => {
    const d = path.join(LIB, dir);
    if (!fs.existsSync(d)) return;
    fs.readdirSync(d).filter(f => f.endsWith('.html')).sort().forEach(f => {
      const file = path.join(d, f);
      const text = fs.readFileSync(file, 'utf8').split('\r\n').join('\n');   // a git checkout may give CRLF
      out.push({ file, rel: `${dir}/${f}`, text, h: readHeader(text) || {} });
    });
  });
  return out;
}

function nextId(prefix) {
  const used = items().map(i => i.h.id).filter(id => id && id.startsWith(prefix + '-')).map(id => Number(id.split('-')[1]));
  const retired = fs.existsSync(path.join(LIB, 'retired-ids.txt')) ? fs.readFileSync(path.join(LIB, 'retired-ids.txt'), 'utf8') : '';
  let n = used.length ? Math.max(...used) + 1 : 1;
  while (retired.includes(`${prefix}-${String(n).padStart(2, '0')}`)) n++;
  return `${prefix}-${String(n).padStart(2, '0')}`;
}

/* ---------- theme ---------- */
function themeOf(id = DEFAULT_THEME) {
  const it = items().find(i => i.h.id === id);
  if (!it) throw new Error(`no theme ${id}`);
  return JSON.parse(it.text.match(/<script type="application\/json" id="theme">([\s\S]*?)<\/script>/)[1]);
}
/* A theme's embedded font faces (the inside of its <style id="theme-fonts">), or '' when it has none. Held only in the theme item. */
function fontsOf(id = DEFAULT_THEME) {
  const it = items().find(i => i.h.id === id);
  return it ? ((it.text.match(/<style id="theme-fonts">\n?([\s\S]*?)\n?<\/style>/) || [])[1] || '') : '';
}
const tokensBlock = theme => `<style id="tokens">:root {\n${Object.entries(theme.css).map(([k, v]) => `  ${k}: ${v};`).join('\n')}\n  --series: ${theme.series.join(' ')};\n}</style>`;

/* The deck stylesheet without its colour and font tokens (those come from the theme). */
function deckCss(theme) {
  // the presentation skill's stylesheet, first that exists: beside the library in an installed workspace (.claude),
  // the repo's working copy (the library lives in Toolkit Update/), the bundle's copy (claude, no dot)
  const ref = ['skills', 'presentation', 'references', 'base-styles.css'];
  const skillCss = [path.join(LIB, '..', '.claude', ...ref), path.join(LIB, '..', '..', '.claude', ...ref), path.join(LIB, '..', 'claude', ...ref)].find(p => fs.existsSync(p));
  if (!skillCss) {
    // a copy of the library without the skill beside it: reuse the stylesheet a slide item already carries
    const one = items().find(i => i.h.type === 'slide');
    if (!one) throw new Error('no presentation skill beside the library and no slide item to take the stylesheet from');
    return one.text.match(/<style id="deck-css">\n([\s\S]*?)\n<\/style>/)[1];
  }
  const base = fs.readFileSync(skillCss, 'utf8').split('\r\n').join('\n');   // a git checkout may give CRLF
  return base.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^:root \{[\s\S]*?^\}/m, block =>
    block.split('\n').filter(l => !Object.keys(theme.css).some(k => l.trim().startsWith(k + ':'))).join('\n'))
    .replace(/\n\s*\n+/g, '\n').trim();
}

/* ---------- the shared lines every item carries: fit, theme, charts, and motion when asked ---------- */
/* host-runtime.js draws the charts (tokens, theme, hover, default grid, table tips); this engine adds what only the
   library page needs: fit to the frame, motion and Replay, theme fonts, and the messages from index.html. */
const RUNTIME = fs.readFileSync(path.join(LIB, 'host-runtime.js'), 'utf8').split('\r\n').join('\n').trim();
const ENGINE = `window.ItemEngineInside = true;
${RUNTIME}
(function () {
  var root = document.documentElement, body = document.body, H = window.ItemHost;
  /* Motion only for items marked data-animate (body or one element). Reduced motion means no AUTOPLAY:
     load, scroll into view and theme changes show the finished state. An explicit action (Replay, an item's
     own Play or step control, opening the item in the index popup) always plays: it sets forced. */
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches, forced = false;
  function marked(box) { return body.hasAttribute('data-animate') || !!(box && box.hasAttribute('data-animate')); }
  function moves(box) { return (forced || !still) && marked(box); }
  function force() { forced = true; root.classList.add('forced'); if (!root.classList.contains('play')) root.classList.add('play'); }
  function draw(play) { H.draw(play ? moves : null); }
  /* Count-up: <span data-tick-up="1240" data-prefix="$" data-suffix="K" data-decimals="0">$1,240K</span>.
     The written text is the final value, so the item reads right with motion off. */
  function show(el, v) {
    var d = +(el.getAttribute('data-decimals') || 0);
    el.textContent = (el.getAttribute('data-prefix') || '') + v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) + (el.getAttribute('data-suffix') || '');
  }
  function tickUp() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-tick-up]'), function (el) {
      var to = +el.getAttribute('data-tick-up'), from = to * 0.9, t0 = null, ms = 800;
      if (!moves(el.closest('[data-animate]'))) { show(el, to); return; }
      function step(ts) { if (t0 === null) t0 = ts; var k = Math.min(1, (ts - t0) / ms), e = 1 - Math.pow(1 - k, 3); show(el, k < 1 ? from + (to - from) * e : to); if (k < 1) requestAnimationFrame(step); }
      requestAnimationFrame(step);
    });
  }
  /* A theme may embed its typeface as @font-face rules with data: URIs, held only in the theme item (style#theme-fonts).
     They travel with its tokens (index message or #theme= link) into style#theme-fonts-live. Charts and Replay wait
     until the faces have loaded, so ECharts measures its labels in that font. A theme without fonts removes them. */
  var fontWait = null;
  function facesLoaded(style) {
    if (!style || !style.sheet || !document.fonts || !document.fonts.load) return Promise.resolve();
    var asks = Array.prototype.filter.call(style.sheet.cssRules, function (r) { return r.type === 5; }).map(function (r) {
      return document.fonts.load((r.style.getPropertyValue('font-weight') || '400') + ' 16px ' + r.style.getPropertyValue('font-family')).catch(function () {});
    });
    return Promise.all(asks).then(function () { return document.fonts.ready; });
  }
  function waitFor(style) { var w = fontWait = facesLoaded(style).then(function () { if (fontWait === w) fontWait = null; }); return w; }
  function faces(text) {
    var s = document.getElementById('theme-fonts-live');
    if (!text) { if (s) s.parentNode.removeChild(s); return null; }
    if (!s) { s = document.createElement('style'); s.id = 'theme-fonts-live'; document.head.appendChild(s); }
    if (s.textContent !== text) s.textContent = text;
    return waitFor(s);
  }
  if (document.getElementById('theme-fonts')) waitFor(document.getElementById('theme-fonts'));   /* a theme item showing its own font */
  /* Replay: charts draw in again, numbers count up again, CSS motion under html.play runs again. Never loops. */
  function replay(explicit) {
    if (fontWait) { fontWait.then(function () { fit(); replay(explicit); }); return; }   /* draw once the theme's font is in */
    forced = !!explicit; root.classList.toggle('forced', forced);
    draw(true); tickUp();
    if (moves(document.querySelector('[data-animate]'))) { root.classList.remove('play'); void root.offsetWidth; root.classList.add('play'); }
    window.dispatchEvent(new CustomEvent('item:replay', { detail: { explicit: forced } }));
  }
  /* phones: lay the item out at the device width (items carry no viewport tag of their own) */
  if (!document.querySelector('meta[name="viewport"]')) { var vp = document.createElement('meta'); vp.name = 'viewport'; vp.content = 'width=device-width, initial-scale=1'; document.head.appendChild(vp); }
  var texty = !!document.querySelector('.lib-table, .lib-cards');
  function fit() {
    var f = document.querySelector('.fit');
    if (!f) return;
    /* reflow at readable size only when opened by itself on a narrow screen; inside a frame (index grid, popup) always scale */
    var narrow = texty && window.self === window.top && window.innerWidth < 720;
    root.classList.toggle('narrow', narrow);
    Array.prototype.forEach.call(document.querySelectorAll('.lib-table'), function (t) { t.parentElement.classList.toggle('lib-scroll', narrow); });
    if (narrow) { f.style.transform = 'none'; return; }
    var s = Math.min(window.innerWidth / f.offsetWidth, (window.innerHeight - strip) / f.offsetHeight);
    f.style.transform = 'scale(' + s + ')';
  }
  /* From the index: {theme} restyles; {replay: true} replays (scroll into view: autoplay rules); {replay: true, explicit: true}
     plays whatever the motion setting (the popup was opened). Alone, an item keeps its own look. */
  /* Escape inside an item opened in the index popup closes the popup; an item that handles Escape itself calls preventDefault */
  if (window.parent !== window) window.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !e.defaultPrevented) window.parent.postMessage({ escape: true }, '*'); });
  window.addEventListener('message', function (e) {
    if (e.data && e.data.replay) return replay(!!e.data.explicit);
    var t = e.data && e.data.theme;
    if (!t || body.hasAttribute('data-own-theme')) return;
    Object.keys(t.css || {}).forEach(function (k) { root.style.setProperty(k, t.css[k]); });
    if (t.series) root.style.setProperty('--series', t.series.join(' '));
    var w = faces(t.fonts);
    if (w) w.then(function () { fit(); draw(false); }); else draw(false);
  });
  /* Any item that opts into motion (body or one element marked data-animate) gets the Replay control, in a strip
     of its own above the content (never on it). In the index grid (#grid) the strip is left out: cards are clicked. */
  var strip = 0, grid = /(^|[#&])grid(&|$)/.test(location.hash);
  var linked = (location.hash.match(/(?:^#|&)theme=([^&]+)/) || [])[1];
  if (linked && !body.hasAttribute('data-own-theme')) {
    try { var lt = JSON.parse(decodeURIComponent(linked)); Object.keys(lt.css || {}).forEach(function (k) { root.style.setProperty(k, lt.css[k]); }); if (lt.series) root.style.setProperty('--series', lt.series.join(' ')); faces(lt.fonts); } catch (e) { /* a theme id, not tokens: keep the default */ }
  }
  if (document.querySelector('[data-animate]') && !grid) {
    strip = 40;
    var bar = document.createElement('div');
    bar.className = 'item-strip';
    bar.style.cssText = 'position:fixed;left:0;right:0;top:0;height:40px;z-index:9;box-sizing:border-box;display:flex;align-items:center;justify-content:flex-end;gap:12px;padding:0 10px;background:var(--paper);border-bottom:1px solid var(--rule);';
    if (still) {
      var n = document.createElement('span');
      n.className = 'item-motion-note'; n.textContent = 'Motion is reduced on this device. Press Replay to play.';
      n.style.cssText = 'font:12px var(--body-font);color:var(--muted);';
      bar.appendChild(n);
    }
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'item-replay'; b.textContent = 'Replay';
    b.style.cssText = 'font:600 13px var(--body-font);padding:5px 12px;border:1.5px solid var(--navy);border-radius:var(--radius);background:var(--paper);color:var(--navy);cursor:pointer;';
    b.addEventListener('click', function () { replay(true); });
    bar.appendChild(b);
    body.appendChild(bar);
    body.style.paddingTop = strip + 'px'; body.style.boxSizing = 'border-box';
  }
  /* The public hook for an item's own script (AUTHORING.md): the chart instance holding an element, and a redraw.
     Events on window: item:draw after every redraw (theme, resize), item:replay after every replay (load, Replay, index). */
  window.ItemEngine = {
    motion: function () { return forced || !still; },   /* may motion run now: true unless reduced and no explicit action */
    play: function () { replay(true); },                 /* an item's own Play control: a full explicit replay */
    force: function () { force(); },                     /* an item's own step or switch control: let its motion run */
    chart: H.chart,
    redraw: function () { draw(false); }
  };
  window.itemRedraw = window.ItemEngine.redraw;
  window.addEventListener('beforeprint', function () { Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (b) { if (b._chart) b._chart.dispatchAction({ type: 'hideTip' }); }); });
  window.addEventListener('resize', function () { fit(); draw(false); });
  H.tableTips(); fit(); replay();
})();`;

const page = (h, theme, head, body, animate) => `<!doctype html>
${header(h)}
<html lang="en">
<head>
<meta charset="utf-8">
<title>${h.id} ${h.name}</title>
${tokensBlock(theme)}
${head}
<script src="${ECHARTS}"></script>
</head>
<body${h.type === 'theme' ? ' data-own-theme' : ''}${animate || h.type === 'animation' ? ' data-animate' : ''}>
${body}
<script id="item-engine">
${ENGINE}
</script>
</body>
</html>
`;

const FRAME_SLIDE = `<style id="frame">
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--paper); }
.fit { width: 1280px; height: 720px; transform-origin: 0 0; position: relative; overflow: hidden; background: var(--paper); }
.reveal .slides { position: absolute; inset: 0; }
.reveal .slides section { position: absolute; inset: 0; }
</style>`;

const FRAME_BLOCK = `<style id="frame">
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--paper); color: var(--ink); font-family: var(--body-font); }
.fit { width: 960px; height: 540px; transform-origin: 0 0; box-sizing: border-box; padding: 28px 36px; display: flex; flex-direction: column; gap: 10px; }
.fit h2 { margin: 0; font: var(--heading-weight) 24px var(--heading-font); color: var(--navy); }
.fit p { margin: 0; font-size: 15px; color: var(--muted); }
.chart { position: relative; flex: 1; min-height: 0; }
.source { display: none; }
</style>`;

/* A chart block's own pieces besides its options: the basis line and an optional key (line swatches).
   In every chart item under .fit (build-index.js keeps it in step) and in host.css under [data-item]. */
const CHART_CSS = p => `${p} > p.basis { margin: 0; font-size: 13px; line-height: 1.4; color: var(--muted); }
${p} > .key { display: flex; flex-wrap: wrap; gap: 4px 22px; font-size: 13px; color: var(--muted); }
${p} > .key span { display: inline-flex; align-items: center; gap: 7px; }
${p} > .key i { display: inline-block; width: 28px; border-top: 3px solid var(--blue); }
${p} > .key i.dash { border-top-style: dashed; } ${p} > .key i.dot { border-top-style: dotted; } ${p} > .key i.thin { border-top-width: 2px; }
${p} > .key i.mid { border-top-color: var(--muted); } ${p} > .key i.lite { border-top-color: var(--chart-muted); } ${p} > .key i.good { border-top-color: var(--good); }
${p} > .key i.box { width: 16px; height: 10px; border: 0; border-radius: 3px; background: var(--blue); } ${p} > .key i.box.lite { background: var(--chart-muted); } ${p} > .key i.box.empty { background: transparent; box-shadow: inset 0 0 0 1.5px var(--chart-muted); }`;

/* ---------- the kit: one stylesheet for cards, deltas, meters, tables, controls and page pieces ----------
   Carried by every table, hero card, animation and layout item (build-index.js keeps it in step).
   Tokens only; ported from the james-themes components (jt- classes became lib- classes). */
const KIT_CSS = `.fit { font-family: var(--body-font); color: var(--ink); }
.lib-lab { font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.lib-card { background: var(--paper); color: var(--ink); border: 1.5px solid var(--navy); border-top: 8px solid var(--blue); border-radius: var(--radius); padding: 18px 22px 20px; min-width: 0; transition: box-shadow .15s; }
.lib-card:hover { box-shadow: 3px 3px 0 var(--shadow); }
.lib-card.good { border-top-color: var(--good); } .lib-card.bad { border-top-color: var(--bad); } .lib-card.neutral { border-top-color: var(--neutral); }
.lib-card.lead { background: var(--tint); border-color: var(--tint); }
.lib-big { font: var(--heading-weight) 52px/1 var(--heading-font); color: var(--navy); font-variant-numeric: tabular-nums; margin: 8px 0; }
.lib-sub { font-size: 14px; color: var(--muted); font-variant-numeric: tabular-nums; }
.lib-said { font-size: 15px; color: var(--muted); margin: 8px 0 14px; }
.lib-foot { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 13px; margin-top: 12px; color: var(--muted); }
.lib-delta { font-weight: 700; white-space: nowrap; font-variant-numeric: tabular-nums; }
.lib-delta.good, .lib-good { color: var(--good); } .lib-delta.bad, .lib-bad { color: var(--bad); } .lib-delta.neutral { color: var(--neutral); }
.lib-meter { display: inline-block; vertical-align: middle; width: 130px; height: 12px; background: var(--track); margin-right: 10px; }
.lib-meter b { display: block; height: 12px; background: var(--blue); } .lib-meter b.bad { background: var(--bad); } .lib-meter b.good { background: var(--good); }
.lib-tick { position: relative; height: 18px; background: var(--track); }
.lib-tick .a { position: absolute; left: 0; top: 4px; height: 10px; background: var(--good); } .lib-tick .a.bad { background: var(--bad); }
.lib-tick .p { position: absolute; top: -4px; width: 3px; height: 26px; background: var(--navy); }
.lib-tick .l { position: absolute; top: 4px; width: 2px; height: 10px; background: var(--chart-muted); }
.lib-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
.lib-table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.lib-table th { font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); padding: 10px 12px; border-bottom: 2px solid var(--navy); text-align: right; }
.lib-table td { font-size: 15px; padding: 12px; border-bottom: 1px solid var(--rule); text-align: right; }
.lib-table .left { text-align: left; }
.lib-table tbody tr { transition: background .12s; }
.lib-table tbody tr:hover, .lib-table tr.on { background: var(--tint); }
.lib-table tr.on td:first-child { box-shadow: inset 4px 0 0 var(--blue); }
.lib-table tbody td:hover { box-shadow: inset 0 0 0 1.5px var(--navy); }
@media print { .lib-table tbody td:hover { box-shadow: none; } }
.lib-table tfoot td { font-weight: 700; border-top: 2px solid var(--navy); border-bottom: none; background: var(--tint); }
.lib-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.lib-btn { font: inherit; font-size: 14px; font-weight: 600; min-height: 44px; padding: 8px 18px; border-radius: var(--radius); border: 1.5px solid; cursor: pointer; transition: background .12s, color .12s; }
.lib-btn.pri { background: var(--blue); color: var(--paper); border-color: var(--blue); } .lib-btn.pri:hover { background: var(--navy); border-color: var(--navy); }
.lib-btn.sec { background: var(--paper); color: var(--blue); border-color: var(--blue); } .lib-btn.sec:hover { background: var(--tint); }
.lib-btn.solid { background: var(--on-band); color: var(--band); border-color: var(--on-band); } .lib-btn.solid:hover { background: var(--tint); border-color: var(--tint); }
.lib-btn.line { background: transparent; color: var(--on-band); border-color: var(--on-band); } .lib-btn.line:hover { background: var(--tint); color: var(--navy); }
.lib-mini { font: inherit; font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; min-height: 32px; padding: 4px 10px; border-radius: var(--radius); border: 1.5px solid var(--blue); background: var(--paper); color: var(--blue); cursor: pointer; }
.lib-mini:hover { background: var(--tint); }
.lib-seg { display: inline-flex; flex-wrap: wrap; } .lib-seg button { font: inherit; font-size: 13px; font-weight: 600; min-height: 44px; padding: 6px 14px; cursor: pointer; background: var(--paper); color: var(--navy); border: 1.5px solid var(--navy); }
.lib-seg button + button { margin-left: -1.5px; } .lib-seg button[aria-pressed="true"] { background: var(--navy); color: var(--paper); }
.lib-chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.lib-chip { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 6px 0 14px; border: 1.5px solid currentColor; border-radius: var(--radius); font-size: 14px; font-weight: 600; }
.lib-chip button { font: inherit; font-size: 16px; width: 32px; height: 32px; border: none; background: transparent; color: inherit; cursor: pointer; border-radius: var(--radius); } .lib-chip button:hover { background: var(--tint); color: var(--navy); }
.lib-gate { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; font-size: 13px; color: var(--muted); }
.lib-gate label { display: inline-flex; align-items: center; gap: 8px; min-height: 44px; font-weight: 600; color: var(--navy); }
.lib-gate input[type="range"] { width: 150px; accent-color: var(--blue); } .lib-gate output { min-width: 52px; font-weight: 700; color: var(--navy); font-variant-numeric: tabular-nums; }
.lib-panel { min-width: 0; background: var(--paper); border: 1.5px solid var(--navy); border-top: 8px solid var(--blue); border-radius: var(--radius); padding: 18px 22px; transition: box-shadow .15s; }
.lib-panel:hover { box-shadow: 3px 3px 0 var(--shadow); }
.lib-panel h2 { margin: 0; font: var(--heading-weight) 18px var(--heading-font); color: var(--navy); } .lib-panel .cap { margin: 3px 0 10px; font-size: 14px; color: var(--muted); }
.lib-panelhead { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.lib-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 18px; }
.lib-note { margin: 12px 0 0; padding-top: 10px; border-top: 1px solid var(--rule); font-size: 13px; line-height: 1.45; color: var(--muted); }
.lib-source { margin: 8px 0 0; font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.lib-band { background: var(--band); color: var(--on-band); padding: 26px 28px; }
.lib-band h1 { margin: 6px 0 0; font: var(--heading-weight) 28px/1.15 var(--heading-font); color: var(--on-band); } .lib-band .lib-lab { color: var(--on-band); }
.lib-rail { background: var(--menu); color: var(--on-menu); border-right: 1.5px solid var(--on-menu); padding: 26px 14px; display: flex; flex-direction: column; gap: 6px; }
.lib-rail .brand { font: var(--heading-weight) 20px var(--heading-font); padding: 0 12px 16px; }
.lib-rail a { display: block; min-height: 40px; padding: 10px 12px; border-radius: var(--radius); font-size: 15px; font-weight: 600; text-decoration: none; color: var(--on-menu); transition: background .15s, padding-left .15s; }
.lib-rail a[aria-current="page"] { background: var(--on-menu); color: var(--menu); } .lib-rail a:not([aria-current]):hover { background: var(--tint); color: var(--navy); padding-left: 20px; }
.lib-btnrow { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
:focus-visible { outline: 3px solid var(--ink); outline-offset: 2px; }
.lib-band :focus-visible { outline-color: var(--on-band); }
html.narrow, html.narrow body { height: auto; overflow: auto; }
html.narrow .fit { width: auto; height: auto; padding: 16px; }
.lib-scroll { overflow-x: auto; } .lib-scroll .lib-table { min-width: 560px; }
@media (prefers-reduced-motion: reduce) { html:not(.forced) * { transition: none !important; animation: none !important; } }`;

const FRAME_KIT = `<style id="frame">
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--wash); }
.fit { width: 960px; height: 540px; transform-origin: 0 0; box-sizing: border-box; padding: 28px 32px; display: flex; flex-direction: column; gap: 14px; }
.chart { position: relative; flex: 1; min-height: 0; }
.source { display: none; }
</style>`;

/* One shell for tables, hero cards, animations and layout pieces: the kit, the item's own CSS (tokens only),
   its markup between ITEM:START and ITEM:END, and its own script if it needs one. */
function kitItem(h, theme, { body, css = '', js = '', after = '', animate = false }) {
  return page(h, theme, `<style id="kit-css">\n${KIT_CSS}\n</style>\n${FRAME_KIT}\n<style id="item-css">\n${css.trim()}\n</style>`,
    `<div class="fit">\n<!-- ITEM:START -->\n${body.trim()}\n<!-- ITEM:END -->\n</div>\n${after}${js ? `<script id="item-js">\n${js.trim()}\n</script>\n` : ''}`, animate);
}

function slideItem(h, theme, sectionHtml) {
  return page(h, theme, `<style id="deck-css">\n${deckCss(theme)}\n</style>\n${FRAME_SLIDE}`,
    `<div class="fit reveal"><div class="slides">\n<!-- ITEM:START -->\n${sectionHtml.trim()}\n<!-- ITEM:END -->\n</div></div>`);
}

/* A chart block holds only its options, an optional key and a basis line (build-index.js checks it). */
function chartItem(h, theme, optionJson, title, basis) {
  return page(h, theme, `${FRAME_BLOCK}\n<style id="chart-css">\n${CHART_CSS('.fit')}\n</style>\n<style id="item-css">\n</style>`,
    `<div class="fit">\n<h2>${title || 'Heading: what is measured, the period'}</h2>\n<!-- ITEM:START -->\n<div class="chart" data-echart>\n<script type="application/json">\n${optionJson.trim()}\n</script>\n</div>\n` +
    `<p class="basis">${basis || 'What is measured, the period and the basis. Sample values.'}</p>\n<!-- ITEM:END -->\n</div>`);
}

/* Chart JSON as the library writes it: an object or array on one line when it fits in 110 characters, else one entry a line. */
function prettyJson(v, ind = '') {
  const one = JSON.stringify(v, null, 1).replace(/\n\s*/g, ' ').replace(/\[ /g, '[').replace(/ \]/g, ']');
  if (v === null || typeof v !== 'object' || one.length + ind.length <= 110) return one;
  const next = ind + '  ';
  if (Array.isArray(v)) return `[\n${v.map(x => next + prettyJson(x, next)).join(',\n')}\n${ind}]`;
  return `{\n${Object.keys(v).map(k => `${next}${JSON.stringify(k)}: ${prettyJson(v[k], next)}`).join(',\n')}\n${ind}}`;
}

/* What a project's page carries once to draw copied items: written to host.css by build-index.js. */
const HOST_CSS = () => `/* host.css: the styles a page needs for copied design-library items. Written by build-index.js; do not edit.
   Copy it once into the page, with the theme tokens (node item.js theme <id>) and host-runtime.js. */
[data-item] { display: flex; flex-direction: column; gap: 10px; min-width: 0; min-height: 0; }
[data-item] .chart[data-echart] { position: relative; flex: 1 1 auto; height: var(--chart-height, 340px); min-height: 0; min-width: 0; }
${CHART_CSS('[data-item]')}
${KIT_CSS.split('\n').filter(l => !/^(\.fit\b|html\.narrow)/.test(l)).join('\n')}
`;

function themeItem(h, theme, fonts = '') {
  const sw = Object.keys(theme.css).filter(k => !/font|weight|radius/.test(k))
    .map(k => `<div class="sw"><i style="background: var(${k})"></i><span>${k}</span></div>`).join('\n');
  const option = { xAxis: { type: 'category', data: ['A', 'B', 'C', 'D', 'E', 'F'] }, yAxis: { type: 'value', show: false },
    series: theme.series.map((t, i) => ({ type: 'bar', name: t, data: [3, 5, 4, 6, 5, 7].map(v => v + i) })) };
  return page(h, theme, `${fonts ? `<style id="theme-fonts">\n${fonts}\n</style>\n` : ''}${FRAME_BLOCK}\n<style id="theme-page">
.sw { display: inline-flex; align-items: center; gap: 6px; margin: 0 14px 6px 0; font-size: 13px; color: var(--muted); }
.sw i { width: 22px; height: 22px; border: 1px solid var(--rule); display: inline-block; }
</style>`,
  `<div class="fit">\n<h2>Theme ${h.name}: headings in the heading font</h2>\n<p>Body text in the body font. Swatches are the tokens; bars are the series order.</p>\n<div>${sw}</div>\n` +
  `<div class="chart" data-echart>\n<script type="application/json">\n${JSON.stringify(option)}\n</script>\n</div>\n</div>\n` +
  `<!-- THEME: the tokens. css: CSS variables every item uses; series: the chart colours, in order, as token names -->\n<script type="application/json" id="theme">\n${JSON.stringify(theme, null, 1)}\n</script>`);
}

/* ---------- neutral sample data and wording ---------- */
const PERIOD = /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(\s*'?\d{2,4})?$|^\d{4}[-/]\d{1,2}$|^q[1-4]\s*'?\d{2,4}$|^\d{4}\s*q[1-4]$|^\d{4}$/i;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/* Keep the chart's shape (kind, highlight, series count) but at most 6 points, with made-up round
   values and neutral labels, and no figure from the project anywhere in it. */
function neutralChart(o) {
  const cats = [].concat(o.xAxis || [], o.yAxis || []).find(a => a && a.type === 'category' && Array.isArray(a.data));
  const series = [].concat(o.series || []);
  let keep = null;
  if (cats && cats.data.length > 6) {
    let hi = 0;
    series.forEach(s => (s.data || []).forEach((d, i) => { if (d && typeof d === 'object' && d.itemStyle && /--blue/.test(String(d.itemStyle.color))) hi = i; }));
    const start = Math.max(0, Math.min(hi - 3, cats.data.length - 6));
    keep = [start, start + 6];
  }
  if (cats) {
    const time = cats.data.filter(c => PERIOD.test(String(c))).length >= cats.data.length / 2;
    const n = keep ? 6 : cats.data.length;
    cats.data = Array.from({ length: n }, (_, i) => time ? MONTHS[i % 12] : `Group ${String.fromCharCode(65 + i)}`);
  }
  let max = 0;
  const num = v => typeof v === 'number' && isFinite(v);
  const scan = v => { if (num(v)) max = Math.max(max, Math.abs(v)); else if (Array.isArray(v)) v.forEach(scan); else if (v && typeof v === 'object' && 'value' in v) scan(v.value); };
  series.forEach(s => (s.data || []).forEach(scan));
  const f = max ? 100 / max : 1;
  const sc = v => num(v) ? Math.round(v * f / 5) * 5 : v;
  const scaleVal = v => Array.isArray(v) ? v.map(x => (num(x) ? sc(x) : PERIOD.test(String(x)) || typeof x !== 'string' ? x : 'Group')) : sc(v);
  series.forEach(s => {
    if (Array.isArray(s.data)) {
      if (keep && s.type !== 'scatter' && s.type !== 'heatmap') s.data = s.data.slice(keep[0], keep[1]);
      s.data = s.data.map(d => (d && typeof d === 'object' && !Array.isArray(d)) ? Object.assign(d, { value: scaleVal(d.value) }) : scaleVal(d));
    }
    if (s.name) s.name = `Series ${series.indexOf(s) + 1}`;
  });
  [].concat(o.xAxis || [], o.yAxis || []).forEach(a => { if (a && a.type === 'value') { ['min', 'max', 'interval'].forEach(k => { if (num(a[k])) a[k] = k === 'interval' ? 25 : sc(a[k]); }); } });
  // any text with a digit or a project word in a label: back to the plain value
  const walk = (x, key) => {
    if (Array.isArray(x)) return x.forEach(v => walk(v, key));
    if (!x || typeof x !== 'object') return;
    Object.keys(x).forEach(k => {
      const v = x[k];
      if (k === 'formatter' && typeof v === 'string' && !/^\{[a-z@\[\]0-9]*\}%?$/.test(v)) x[k] = /%/.test(v) ? '{c}%' : '{c}';
      else if ((k === 'xAxis' || k === 'yAxis') && num(v) && key === 'markLine') x[k] = sc(v);
      else walk(v, k === 'markLine' ? 'markLine' : key);
    });
  };
  walk(o, '');
  // one series with one highlighted point: a made-up, readable shape (the point at 100, the rest 35 to 60), not the project's proportions
  const one = series.length === 1 && ['bar', 'line'].includes(series[0].type) && Array.isArray(series[0].data) && series[0].data.length <= 6 ? series[0] : null;
  const hiAt = one ? one.data.findIndex(d => d && typeof d === 'object' && d.itemStyle && /--blue/.test(String(d.itemStyle.color))) : -1;
  if (one && hiAt !== -1) {
    const P = [40, 55, 35, 60, 50, 45];
    one.data = one.data.map((d, i) => { const v = i === hiAt ? 100 : P[i]; return d && typeof d === 'object' && !Array.isArray(d) ? Object.assign(d, { value: v }) : v; });
    if (one.markLine && Array.isArray(one.markLine.data)) one.markLine.data.forEach(d => { if (d && num(d.yAxis)) d.yAxis = 45; if (d && num(d.xAxis)) d.xAxis = 45; });
    [].concat(o.xAxis || [], o.yAxis || []).forEach(a => { if (a && a.type === 'value') { delete a.min; if (num(a.max)) a.max = 100; } });
  }
  return o;
}

/* ---------- what the preview shows, in words: the librarian writes the purpose from this and never opens the item ---------- */
function describeChart(o) {
  if (!o) return 'no chart';
  const series = [].concat(o.series || []).filter(s => s && !s.silent && !/^_/.test(s.name || ''));
  const axes = [].concat(o.xAxis || []), yAxes = [].concat(o.yAxis || []);
  const cat = axes.concat(yAxes).find(a => a && a.type === 'category' && Array.isArray(a.data));
  const horizontal = !!yAxes.find(a => a && a.type === 'category');
  const kinds = [...new Set(series.map(s => s.type))];
  const word = { bar: horizontal ? 'horizontal bars' : 'columns', line: 'a line', scatter: 'dots', pie: 'a pie', heatmap: 'a heat grid', funnel: 'a funnel', gauge: 'a gauge' };
  let t = kinds.map(k => (k === 'line' && series.filter(s => s.type === 'line').length > 1 ? 'lines' : word[k] || k)).join(' with ');
  if (series.some(s => s.stack)) t = 'stacked ' + t;
  if (cat) t += ` over ${cat.data.length} ${cat.data.filter(c => PERIOD.test(String(c))).length >= cat.data.length / 2 ? 'months' : 'groups'}`;
  if (series.length > 1) t += `, ${series.length} series${o.legend ? ' with a legend' : ''}`;
  if (yAxes.filter(a => a && a.type === 'value').length > 1) t += ', two value axes';
  const hi = [];
  series.forEach(s => (s.data || []).forEach((d, i) => { if (d && typeof d === 'object' && d.itemStyle && /--(blue|orange|bad|good)/.test(String(d.itemStyle.color))) hi.push(cat ? cat.data[i] : `point ${i + 1}`); }));
  t += hi.length ? `; highlighted: ${[...new Set(hi)].join(', ')} (the rest muted)` : '; no single mark highlighted';
  if (series.some(s => s.markLine)) t += '; a reference line';
  if (series.some(s => s.endLabel && s.endLabel.show)) t += '; end label on the line';
  else if (series.some(s => s.label && s.label.show)) t += '; value labels on the marks';
  return t;
}
function describeSlide(html, group, option, layout) {
  const n = re => (html.match(re) || []).length;
  const parts = [`slide, group ${group}${layout ? `, layout "${layout}"` : ''}`];
  const bits = [];
  if (/class="kicker"/.test(html)) bits.push('a kicker');
  if (/<h[12]\b/.test(html)) bits.push('a headline');
  if (option) bits.push(`a chart (${describeChart(option)})`);
  if (/<table/.test(html)) bits.push(`a table of ${n(/<tr\b/g) - 1} rows`);
  if (n(/<li\b/g)) bits.push(`${n(/<li\b/g)} bullets`);
  if (/stat-value/.test(html)) bits.push(`${n(/stat-value/g)} big numbers`);
  if (/class="commentary/.test(html)) bits.push('a commentary panel');
  if (/class="callout/.test(html) || /<blockquote/.test(html)) bits.push('a callout');
  if (/class="footnote"/.test(html)) bits.push('a footnote');
  parts.push('holds ' + bits.join(', '));
  parts.push('not copied: every sentence (placeholders say what goes there), the real values and labels, the speaker notes');
  return parts;
}

/* Every visible sentence in a slide becomes a placeholder that says what belongs there. */
function neutralHtml(html) {
  const say = { h1: 'Headline: the answer as a sentence', h2: 'Headline: the point as a sentence, with its number', h3: 'Label',
    li: 'Bullet: what to look at, with its number, and what it means', td: 'Cell', th: 'Column', cite: 'Source', blockquote: 'The one sentence the room should hear.' };
  return html
    .replace(/<script type="application\/json">([\s\S]*?)<\/script>/g, (all, j) => {
      try { return `<script type="application/json">\n${JSON.stringify(neutralChart(JSON.parse(j)), null, 1)}\n</script>`; } catch (e) { return all; }
    })
    .replace(/<(h1|h2|h3|li|td|th|cite)\b([^>]*)>([\s\S]*?)<\/\1>/g, (all, t, a, inner) => /<(div|ul|p|span)\b/.test(inner) ? all : `<${t}${a}>${say[t]}</${t}>`)
    .replace(/<p\b([^>]*)>([^<]*)<\/p>/g, (all, a, txt) => {
      if (!txt.trim()) return all;
      if (/stat-value|row-key/.test(a)) return `<p${a}>${/%/.test(txt) ? '00%' : /\$/.test(txt) ? '$00' : '00'}</p>`;
      if (/kicker/.test(a)) return `<p${a}>Section</p>`;
      return `<p${a}>Supporting sentence: one fact, with its number.</p>`;
    })
    .replace(/<div class="footnote">[\s\S]*?<\/div>/, '<div class="footnote">What is measured, the period, the source.</div>')
    .replace(/<aside class="notes">[\s\S]*?<\/aside>/g, '')
    .replace(/ data-(section|desc|layout|component)="[^"]*"/g, '');
}

/* ---------- slots: where a project's data goes (AUTHORING.md, "Adding an item to a project") ---------- */
/* Marks an object with "slot" as its first key. */
function tag(obj, spec) { const keep = Object.assign({}, obj); Object.keys(obj).forEach(k => delete obj[k]); obj.slot = spec; Object.assign(obj, keep); }
/* A saved chart's slots, guessed from its shape: category axes, each series (an invisible one is a base), a reference
   line as a figure. Marks the option in place; returns the data note and recipe. */
function autoSlots(o) {
  const slots = [], recipe = [];
  const add = (name, kind, count = 'one') => { if (!slots.some(s => s.startsWith(name + ' '))) slots.push(`${name} (${kind}, ${count})`); return name; };
  const cats = { x: [].concat(o.xAxis || []).filter(a => a && a.type === 'category'), y: [].concat(o.yAxis || []).filter(a => a && a.type === 'category') };
  const grid2 = cats.x.length && cats.y.length;   // a heat grid: categories both ways
  if (grid2) { cats.x.forEach(a => tag(a, add('column', 'text'))); cats.y.forEach(a => tag(a, add('row', 'text'))); }
  else cats.x.concat(cats.y).forEach(a => tag(a, add('label', 'text')));
  const series = [].concat(o.series || []).filter(s => s && Array.isArray(s.data));
  const hidden = s => s.silent === true || (s.itemStyle && s.itemStyle.opacity === 0);
  const shown = series.filter(s => !hidden(s));
  let bases = 0, lines = 0;
  series.forEach(s => {
    const first = s.data.find(d => d != null), v = first && typeof first === 'object' && !Array.isArray(first) ? first.value : first;
    const base = hidden(s);
    const name = base ? (bases++ ? `base-${bases}` : 'base') : shown.length === 1 ? 'value' : `value-${shown.indexOf(s) + 1}`;
    if (base) recipe.push(`${name}: the invisible bar under the visible one (the running total before each step, or the low end of a range)`);
    if (Array.isArray(v)) {
      const parts = v.map((x, i) => (s.type === 'heatmap' ? ['column', 'row', 'value'][i] || `value-${i}` : typeof x === 'string' ? 'label' : cats.x.length + cats.y.length ? name : `${name}-${'xyz'[i] || i}`));
      parts.forEach(p => add(p, ['label', 'column', 'row'].includes(p) ? 'text' : 'number'));
      tag(s, parts.join(','));
    } else if (s.type === 'pie') { tag(s, add(name, 'number')); recipe.push(`${name}: one value a slice; give each entry its name by hand`); }
    else tag(s, add(name, 'number'));
    (s.markLine && Array.isArray(s.markLine.data) ? s.markLine.data : []).forEach(d => {
      const k = d && !Array.isArray(d) && ['yAxis', 'xAxis'].find(a => typeof d[a] === 'number');
      if (k) tag(d, `${add(lines++ ? `line-${lines}` : 'line', 'figure', 'optional')}:${k}`);
    });
  });
  return { data: slots.join('; '), recipe: recipe.join('; ') };
}
/* Plain sample blocks, also what `new` writes: a chart's option with slots; a table and tiles in kit markup with slots. */
const PLAIN_TABLE = (labels, vals) => `<div class="lib-panel">
<div class="lib-panelhead"><div><h2>Heading: what the table shows</h2><p class="cap">Caption: the measure and the period</p></div><button type="button" class="lib-mini" data-csv>CSV</button></div>
<table class="lib-table">
<thead><tr><th class="left" data-slot="label">Group</th><th data-slot="value">Value</th></tr></thead>
<tbody data-rows>
${labels.map((l, i) => `<tr><td class="left" data-slot="label">${l}</td><td data-slot="value">${vals[i]}</td></tr>`).join('\n')}
</tbody>
</table>
<p class="lib-source">Sample values</p>
</div>`;
/* The CSV button of any table item: reads the table as shown, so it still works after the rows are replaced. */
const CSV_JS = `/* CSV of the rows as shown: every button[data-csv] downloads the table in its panel */
Array.prototype.forEach.call(document.querySelectorAll('button[data-csv]'), function (b) {
  if (b._csv) return;
  b._csv = true;
  b.addEventListener('click', function () {
    var t = b.closest('.lib-panel').querySelector('table'), cell = function (s) { s = s.trim(); return /[",\\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    var text = Array.prototype.map.call(t.rows, function (r) { return Array.prototype.map.call(r.cells, function (c) { return cell(c.innerText); }).join(','); }).join('\\n');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\\ufeff' + text], { type: 'text/csv;charset=utf-8' }));
    a.download = 'table.csv'; document.body.appendChild(a); a.click(); a.remove();
  });
});`;
const PLAIN_TILES = (labels, vals) => `<div class="lib-cards" data-rows>
${labels.map((l, i) => `<div class="lib-card" data-slot="status@class">\n<div class="lib-lab" data-slot="label">${l}</div>\n<div class="lib-big" data-slot="value">${vals[i]}</div>\n<div class="lib-sub" data-slot="note">Note: what the figure is, against what</div>\n</div>`).join('\n')}
</div>
<p class="lib-source">Sample values</p>`;
const plainBar = (labels, vals) => ({ xAxis: { slot: 'label', type: 'category', data: labels }, yAxis: { type: 'value' },
  series: [{ slot: 'value', type: 'bar', name: 'Value', barMaxWidth: 64, label: { show: true, position: 'top' }, data: vals }] });
const PLAIN_NOTES = {
  chart: 'label (text, one); value (number, one or more)',
  table: 'label (text, one); value (number, one or more)',
  tiles: 'label (text, one); value (number, one); note (text, optional); status (text, optional)',
};

/* ---------- report and dashboard sections: a clean generic definition for the shape, never the project's code ---------- */

const BULLET_SETS = {
  time: [['Highest', '{largest_label}', '{largest:$short}'], ['Latest', '{latest_label}', '{latest:$short}'], ['Lowest', '{smallest_label}', '{smallest:$short}'], ['Total', 'all months', '{total:$short}']],
  group: [['Largest', '{largest_label}', '{largest:$short}'], ['Smallest', '{smallest_label}', '{smallest:$short}'], ['Total', 'all groups', '{total:$short}'], ['Groups', 'count', '{groups}']],
};

/* The sample the preview shows, and its metrics filled into the same sentences the source writes. */
function sample(time) {
  const labels = time ? MONTHS.slice(0, 6) : ['Group A', 'Group B', 'Group C', 'Group D'];
  const vals = time ? [40, 55, 35, 70, 50, 60] : [60, 45, 80, 35];
  const hi = vals.indexOf(Math.max(...vals)), lo = vals.indexOf(Math.min(...vals));
  const m = { largest: vals[hi], largest_label: labels[hi], smallest: vals[lo], smallest_label: labels[lo],
    latest: vals[vals.length - 1], latest_label: labels[labels.length - 1], total: vals.reduce((a, b) => a + b, 0), groups: vals.length };
  return { labels, vals, hi, m };
}
const fill = (t, m, money) => t.replace(/\{(\w+)(?::[^}]*)?\}/g, (a, k) => (m[k] === undefined ? a : (money && typeof m[k] === 'number' && k !== 'groups' ? `$${m[k]}K` : String(m[k]))));

function sampleOption(kind, time, money) {
  const s = sample(time);
  const lab = money ? '${c}K' : '{c}';
  if (kind === 'line') return { xAxis: { type: 'category', boundaryGap: false, data: s.labels }, yAxis: { type: 'value', axisLabel: { formatter: money ? '${value}K' : '{value}' } },
    grid: { left: 8, right: 70, top: 20, bottom: 8, containLabel: true },
    series: [{ type: 'line', name: 'Value', data: s.vals, itemStyle: { color: 'var(--blue)' }, lineStyle: { width: 4 }, showSymbol: false, label: { formatter: lab }, endLabel: { show: true, formatter: lab, color: 'var(--blue)' } }] };
  return { xAxis: { type: 'category', data: s.labels }, yAxis: { type: 'value', show: false, max: Math.max(...s.vals) },
    grid: { left: 8, right: 8, top: 26, bottom: 8, containLabel: true },
    series: [{ type: 'bar', barWidth: '58%', itemStyle: { color: 'var(--chart-muted)' }, label: { show: true, position: 'top', formatter: lab },
      data: s.vals.map((v, i) => i === s.hi ? { value: v, itemStyle: { color: 'var(--blue)' }, label: { color: 'var(--blue)' } } : v) }] };
}

/* The generic report section for the shape: what `python run.py add-section` writes. */
function reportSource(shape) {
  const { kind, time, n, wide, format } = shape;
  const bullets = BULLET_SETS[time ? 'time' : 'group'].slice(0, n).map(([k, l, v]) => `    "**${k}.** ${l}, at ${v}.",`).join('\n');
  return `"""Section NAME: VALUE summed by GROUP, shown as a ${kind}. Save as sections/sN_NAME.py and add it to SECTIONS."""
import pandas as pd

DATA, GROUP, VALUE = "DATA", "GROUP", "VALUE"   # CHANGE THESE: the source name, the ${time ? 'date' : 'category'} column, the number column
DESCRIPTION = "What this section shows, in 8 to 10 words"


def NAME(src, params):
    """Sum of VALUE by GROUP."""
    df = src(DATA)
${time ? '    df[GROUP] = pd.to_datetime(df[GROUP], errors="coerce").dt.to_period("M")\n    df = df.dropna(subset=[GROUP])\n' : ''}    t = df.groupby(GROUP, as_index=False)[VALUE].sum()
    t = t.sort_values(${time ? 'GROUP' : 'VALUE, ascending=False'}).reset_index(drop=True)
${time ? '    t[GROUP] = t[GROUP].dt.strftime("%b %Y")\n' : ''}    labels, vals = t[GROUP].astype(str), t[VALUE]
    m = dict.fromkeys(["total", "largest", "largest_label", "smallest", "smallest_label", ${time ? '"latest", "latest_label", ' : ''}"groups"])
    if len(t):
        m.update(total=vals.sum(), largest=vals.max(), largest_label=labels[vals.idxmax()], smallest=vals.min(),
                 smallest_label=labels[vals.idxmin()], ${time ? 'latest=vals.iloc[-1], latest_label=labels.iloc[-1], ' : ''}groups=len(t))
    return {"question": "How does VALUE vary by GROUP?", "tables": {"by_group": t}, "metrics": m, "notes": ""}


TITLE = "{largest_label} had the ${time ? 'highest' : 'largest'} value, {largest:$short}"   # reword: the finding, as a sentence
BULLETS = [   # reword each; keep the {placeholders}
${bullets}
]
CHART = {"type": "${kind}", "table": "by_group", "x": GROUP, "y": VALUE, "axis": "Value", "format": "${format}"}
${wide ? 'LAYOUT = "wide"\n' : ''}`;
}

/* The generic dashboard section for the shape: what `npm run new-section` writes. Charts in full;
   for a table or a KPI the command writes the component, so only its meta and note are given. */
function dashboardSource(shape) {
  const { kind, time, n } = shape;
  const notes = BULLET_SETS[time ? 'time' : 'group'].slice(0, n)
    .map(([k, l, v]) => `- ${k}: ${l.replace(/\{(\w+)\}/, time ? '{$1|month}' : '{$1}')} at ${v.replace(/\{(\w+)(?::[^}]*)?\}/, k === 'Groups' ? '{$1|int}' : '{$1|compact}')}.`).join('\n');
  const head = `// Save as Src/Sections/NAME.jsx and add it to index.js.
export const meta = {
  id: 'NAME', title: "Title: what is measured", tab: 'TAB', chart: '${kind}', library: 'echarts',
  description: "What this section shows, in 8 to 10 words",
  tables: ["DATA"], x: "GROUP", y: "VALUE", agg: 'sum',
};

// Reword these lines; keep the {metric|format} parts (they fill in the real numbers).
export const note = \`
${notes}
\`;
`;
  if (kind !== 'bar' && kind !== 'line') return head + `\n// The component for a ${kind}: npm run new-section writes it from the meta above.\n`;
  return `import { useMemo } from 'react';
import ChartECharts from '../Components/ChartECharts.jsx';
import { FORMATS } from '../Lib/format.js';

${head}
const fmt = (v) => FORMATS.compact(v);
const label = ${time ? 'FORMATS.month' : '(v) => v'};

export default function Section({ data }) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'axis', valueFormatter: fmt },
    grid: { left: 64, right: 24, top: 12, bottom: 28 },
    xAxis: { type: 'category', data: data.x.map(label) },
    yAxis: { type: 'value', name: "Value", axisLabel: { formatter: fmt } },
    series: Object.entries(data.series).map(([name, values]) => ({ name, type: '${kind === 'line' ? 'line' : 'bar'}', data: values })),
  }), [data]);
  return <ChartECharts option={option} height={300} />;
}
`;
}

/* The words for a saved section's preview (same shapes as sectionItem below). */
function describeSection(type, shape, from) {
  const s = sample(shape.time), by = shape.time ? 'month' : 'group';
  const out = [];
  if (type === 'table') out.push(`table in a panel: amount by ${by}, ${s.labels.length} rows, columns ${shape.time ? 'Month' : 'Group'} / Value / a meter of the share of the largest; a CSV button`);
  else if (type === 'hero card') out.push('hero card: one tile with the latest amount as a big number and a note line under it');
  else out.push(`chart: ${shape.kind === 'line' ? 'a line with an end label' : 'columns with value labels'} by ${by} (${s.labels.length} points), a basis line under it`);
  out.push('data note and slots: where a project\'s columns go (AUTHORING.md)');
  out.push(`not copied: the ${from} section's own calculation, names, wording, bullets and numbers (made-up round values instead)`);
  return out;
}

/* A liked section, saved as what it shows: a chart, a table or a hero card, each with its data note and slots. */
function sectionItem(h, theme, shape) {
  const s = sample(shape.time), money = /\$/.test(shape.format || '$');
  const show = v => (money ? `$${v}K` : String(v));
  if (h.type === 'table') {
    h.data = 'label (text, one); value (number, one); share (number, one)';
    h.recipe = 'share: value as a % of the largest value (the meter\'s width)';
    const rows = s.labels.map((l, i) => `<tr><td class="left" data-slot="label">${l}</td><td data-slot="value">${show(s.vals[i])}</td>` +
      `<td class="left"><span class="lib-meter"><b data-slot="share@width" style="width: ${Math.round(100 * s.vals[i] / s.m.largest)}%;"></b></span></td></tr>`).join('\n');
    return kitItem(h, theme, { js: CSV_JS, body: `<div class="lib-panel">\n<div class="lib-panelhead"><div><h2>${shape.time ? 'Amount by month' : 'Amount by group'}</h2><p class="cap">Total, with each row's share of the largest</p></div><button type="button" class="lib-mini" data-csv>CSV</button></div>\n` +
      `<table class="lib-table">\n<thead><tr><th class="left" data-slot="label">${shape.time ? 'Month' : 'Group'}</th><th data-slot="value">Value</th><th class="left">Share of largest</th></tr></thead>\n<tbody data-rows>\n${rows}\n</tbody>\n</table>\n<p class="lib-source">Sample values</p>\n</div>` });
  }
  if (h.type === 'hero card') {
    h.data = PLAIN_NOTES.tiles;
    return kitItem(h, theme, { body: PLAIN_TILES(['Amount, latest period'], [show(s.m.latest)]) });
  }
  const o = sampleOption(shape.kind, shape.time, money);
  const auto = autoSlots(o);
  Object.assign(h, auto.data ? { data: auto.data } : {}, auto.recipe ? { recipe: auto.recipe } : {});
  return chartItem(h, theme, prettyJson(o));
}

/* ---------- project words: recorded as hashes, so the library never stores them ---------- */
const crypto = require('crypto');
const hash = w => crypto.createHash('sha256').update(String(w).trim().toLowerCase()).digest('hex').slice(0, 16);
/* Quoted names and values from a source: columns, tables, ids, category values (1 to 3 words). */
function projectWords(text, generic) {
  const out = new Set();
  for (const m of text.matchAll(/(["'`])((?:(?!\1)[^\\\n]){2,40})\1/g)) {
    const v = m[2].trim();
    if (!/[A-Za-z]/.test(v) || /^[\s{$%.#:-]/.test(v) || /[{}<>=()]/.test(v) || v.split(/\s+/).length > 3) continue;
    if (generic.has(v.toLowerCase())) continue;
    out.add(v);
  }
  return [...out];
}
/* Every quoted string and word in a generic definition: never a project word. */
function genericWords() {
  const g = new Set(['bar', 'line', 'table', 'kpi', 'sum', 'mean', 'count', 'wide', 'echarts', 'value', 'values', 'series', 'name', 'month', 'compact', 'int', 'axis', 'item', 'category', 'time', 'none', 'auto', 'right', 'left', 'top', 'bottom', 'center', 'inside', 'insideright', 'insidetop', 'dashed', 'solid', 'circle', 'rect']);
  const add = t => { for (const m of t.matchAll(/(["'`])((?:(?!\1)[^\\\n]){1,60})\1/g)) g.add(m[2].trim().toLowerCase()); for (const w of t.match(/\w+/g) || []) g.add(w.toLowerCase()); };
  [true, false].forEach(time => ['bar', 'line'].forEach(kind => { add(reportSource({ kind, time, n: 4, wide: true, format: '$short' })); add(dashboardSource({ kind, time, n: 4 })); }));
  return g;
}
function recordWords(id, words) {
  const f = path.join(LIB, 'denylist.json');
  const d = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : {};
  d[id] = [...new Set(words.map(hash))];
  fs.writeFileSync(f, JSON.stringify(d, null, 1) + '\n');
}

/* ---------- CLI ---------- */
function cli() {
  const args = process.argv.slice(2);
  const kind = args[0];
  const opt = k => { const i = args.indexOf(k); return i === -1 ? undefined : args[i + 1]; };
  const stop = m => { console.error('STOP: ' + m); process.exit(1); };
  const theme = themeOf();
  const slug = t => String(t).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'item';
  const names = items().map(i => i.h.name);
  /* A name says the visual's kind and shape; never a name already in the library. */
  const nameFor = auto => {
    if (opt('--name')) {
      const n = slug(opt('--name'));
      if (names.includes(n)) stop(`the name "${n}" is already used in the library; pass another --name`);
      return n;
    }
    let n = auto, k = 2;
    while (names.includes(n)) n = `${auto}-${k++}`;
    return n;
  };
  /* Prints what the preview shows, so the purpose sentence is written from this output, not by opening the item. */
  const write = (h, html, words, preview) => {
    const dir = path.join(LIB, TYPES[h.type]);
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${h.id}-${h.name}.html`);
    if (fs.existsSync(file)) stop(`${file} exists`);
    fs.writeFileSync(file, html);
    if (words) recordWords(h.id, words);
    console.log(`Saved ${h.id} (${h.type}) as ${path.relative(process.cwd(), file).split(path.sep).join('/')}.`);
    if (preview && preview.length) console.log('Preview:\n' + preview.map(l => '  - ' + l).join('\n'));
    console.log(`Next: node save-item.js purpose ${h.id} "<one sentence from the preview above: what it shows and when to use it>", then node build-index.js.`);
  };
  /* A file given as a path with / or \, a bare file name, or a section id; a path whose \ the shell ate still matches. */
  const findIn = (dir, given, ext) => {
    if (!fs.existsSync(dir)) stop(`no folder ${dir}`);
    const files = fs.readdirSync(dir).filter(f => f.endsWith(ext));
    const g = String(given).trim().replace(/\\/g, '/');
    const hit = files.find(f => g === f || g.endsWith('/' + f) || g === f.slice(0, -ext.length) || f.replace(/^s\d+_/, '').slice(0, -ext.length) === g) ||
      files.find(f => g.endsWith(f) || g.endsWith(f.slice(0, -ext.length)));
    if (!hit) stop(`no "${given}" in ${dir}. There: ${files.join(', ')}`);
    return path.join(dir, hit);
  };
  const isTime = col => /month|date|period|week|year|quarter|day/i.test(String(col || ''));
  const base = { purpose: 'WRITE one sentence: what the preview shows and when to use it', from: '' };
  const generic = genericWords();

  if (kind === 'slide' || kind === 'chart') {
    const deckFile = opt('--deck'), sid = opt('--slide');
    if (!deckFile || !sid) stop(`${kind} needs --deck <deck.html> --slide <id|n>`);
    if (!fs.existsSync(deckFile)) stop(`${deckFile} not found (use forward slashes)`);
    const deckHtml = fs.readFileSync(deckFile, 'utf8');
    const body = deckHtml.slice(deckHtml.indexOf('<!-- SLIDES:START -->'), deckHtml.indexOf('<!-- SLIDES:END -->'));
    const opens = [...body.matchAll(/<section\b[^>]*>/g)];
    const at = /^\d+$/.test(sid) ? opens[Number(sid) - 1] : opens.find(m => m[0].includes(`id="${sid}"`));
    if (!at) stop(`no slide "${sid}" in ${deckFile}. Ids: ${opens.map(m => (m[0].match(/id="([^"]*)"/) || [])[1]).join(', ')}`);
    const section = body.slice(at.index, body.indexOf('</section>', at.index) + '</section>'.length);
    const j = section.match(/<script type="application\/json">([\s\S]*?)<\/script>/);
    const option = j ? JSON.parse(j[1]) : null;
    const cat = option && [].concat(option.xAxis || [], option.yAxis || []).find(a => a && a.type === 'category' && Array.isArray(a.data));
    const time = !!cat && cat.data.filter(c => PERIOD.test(String(c))).length >= cat.data.length / 2;
    const kinds = option ? [...new Set([].concat(option.series || []).map(x => x.type))].join('-') : '';
    const plural = k => ({ bar: 'bars', line: 'line', scatter: 'dots', pie: 'pie', heatmap: 'grid' }[k] || k);
    const shapeName = option ? `${kinds.split('-').map(plural).join('-')}-by-${time ? 'month' : 'group'}` : '';
    // project words: the slide id, its chart's category labels and series names, its section name
    const words = [(at[0].match(/id="([^"]*)"/) || [])[1], (at[0].match(/data-section="([^"]*)"/) || [])[1]]
      .concat(cat ? cat.data.map(String) : [], option ? [].concat(option.series || []).map(x => x.name).filter(Boolean) : [])
      .filter(w => w && !PERIOD.test(w) && !generic.has(String(w).toLowerCase()));
    if (kind === 'slide') {
      const layout = (section.match(/data-layout="([^"]*)"/) || [])[1] || '';
      let g = (opt('--group') || '').toUpperCase();
      if (!g) {
        g = option ? (time ? 'CH' : 'LV') : /section-divider/.test(section) ? 'FR' : /class="rows/.test(section) ? 'DE' : /<table/.test(section) ? 'CP' : 'LV';
        console.log(`Group ${g} chosen from the slide's shape (${option ? (time ? 'a time chart' : 'a chart by group') : 'no chart'}); pass --group to change.`);
      }
      if (!GROUPS.includes(g)) stop(`--group is one of ${GROUPS.join(' ')}`);
      const tail = /commentary/.test(layout) || /class="commentary"/.test(section) ? 'commentary' : /callout/.test(layout) || /class="callout/.test(section) ? 'callout' : 'slide';
      const h = Object.assign({}, base, { id: nextId(g), type: 'slide', name: nameFor(option ? `${shapeName}-${tail}` : `${layout || 'text'}-slide`), from: 'presentation' });
      const html = require('./item.js').markSpots(neutralHtml(section).replace(/^<section\b([^>]*)>/, (all, a) =>
        `<section id="${h.name}" data-component="${h.id}"${a.replace(/\s*\bid="[^"]*"/, '')}>`));
      const kept = (html.match(/<script type="application\/json">([\s\S]*?)<\/script>/) || [])[1];
      return write(h, slideItem(h, theme, html), words, describeSlide(html, g, kept ? JSON.parse(kept) : null, layout));
    }
    if (!option) stop(`slide ${sid} has no chart`);
    const h = Object.assign({}, base, { id: nextId('CT'), type: 'chart', name: nameFor(shapeName), from: 'presentation' });
    const neutral = neutralChart(option);
    const auto = autoSlots(neutral);
    Object.assign(h, auto.data ? { data: auto.data } : {}, auto.recipe ? { recipe: auto.recipe } : {});
    return write(h, chartItem(h, theme, prettyJson(neutral)), words, [
      `chart alone under a placeholder heading: ${describeChart(neutral)}`,
      `data note (slots guessed from the chart's shape): ${auto.data}`,
      'not copied: the slide\'s wording, labels (neutral months or Group A, B ...), series names (Series 1, 2 ...) and values (made-up round values, at most 6 points)']);
  }

  /* A liked section is saved as what it shows: a table, a hero card (tiles, KPI) or a chart. */
  const asType = k => (k === 'table' ? 'table' : /^(kpi|tile|tiles|card)$/.test(k) ? 'hero card' : 'chart');
  const nameOf = (type, shape) => type === 'table' ? `table-by-${shape.time ? 'month' : 'group'}-meters`
    : type === 'hero card' ? 'tile-latest-note'
    : `${shape.kind === 'line' ? 'line' : 'bars'}-by-${shape.time ? 'month' : 'group'}`;

  if (kind === 'report-section') {
    const rep = opt('--report'), sec = opt('--section');
    if (!rep || !sec) stop('report-section needs --report <report folder> --section <file, path or name> (forward slashes)');
    const file = findIn(path.join(rep, 'sections'), sec, '.py');
    const src = fs.readFileSync(file, 'utf8');
    const chart = (src.match(/^CHART\s*=\s*(\{[\s\S]*?\})\s*$/m) || [])[1] || '';
    const val = k => (chart.match(new RegExp(`"${k}"\\s*:\\s*"([^"]*)"`)) || [])[1];
    const bl = src.match(/^BULLETS\s*=\s*\[([\s\S]*?)^\]/m);
    const shape = { kind: ['bar', 'line', 'table'].includes(val('type')) ? val('type') : 'bar', time: isTime(val('x')),
      n: Math.min(4, Math.max(1, bl ? (bl[1].match(/^\s*["f]/gm) || []).length : 2)), wide: /^LAYOUT\s*=\s*"wide"/m.test(src), format: val('format') || '$short' };
    const type = asType(shape.kind);
    const h = Object.assign({}, base, { id: nextId(PREFIX[type]), type, name: nameFor(nameOf(type, shape)), from: 'analysis' });
    const custom = src.split('\n').filter(l => /pd\.Period|==\s*["']|\.iloc\[0\]|>\s*\d{3,}/.test(l)).length;
    if (custom) console.log(`The section had its own calculation (${custom} lines); it was not copied, and the item says so.`);
    // the category values live in the data, not the code: ask the report for its table (read only)
    const values = [];
    const fn = (src.match(/^def (\w+)\(/m) || [])[1];
    if (fn && fs.existsSync(path.join(rep, 'run.py'))) {
      const { spawnSync } = require('child_process');
      let r = spawnSync('python', ['run.py', 'data', fn, '--json'], { cwd: rep, encoding: 'utf8' });
      if (r.error) r = spawnSync('python3', ['run.py', 'data', fn, '--json'], { cwd: rep, encoding: 'utf8' });
      try {
        const rows = JSON.parse(r.stdout.slice(r.stdout.search(/[[{]/)));
        (Array.isArray(rows) ? rows : []).forEach(row => Object.entries(row).forEach(([k, v]) => { values.push(k); if (typeof v === 'string') values.push(v); }));
      } catch (e) { console.log('Could not read the section\'s table; only names in the code were recorded.'); }
    }
    console.log(`Saved as a ${type}: the report section showed a ${shape.kind}.`);
    return write(h, sectionItem(h, theme, shape), projectWords(src, generic).concat([path.basename(file, '.py')],
      values.filter(v => /[A-Za-z]/.test(v) && !PERIOD.test(v) && !generic.has(v.toLowerCase()))), describeSection(type, shape, 'report'));
  }

  if (kind === 'dashboard-section') {
    const dash = opt('--dashboard'), sec = opt('--section');
    if (!dash || !sec) stop('dashboard-section needs --dashboard <dashboard folder> --section <id, file or path> (forward slashes)');
    const file = findIn(path.join(dash, 'Src', 'Sections'), sec, '.jsx');
    const src = fs.readFileSync(file, 'utf8');
    const meta = (src.match(/export const meta\s*=\s*\{([\s\S]*?)\};/) || [])[1] || '';
    const mv = k => (meta.match(new RegExp(`\\b${k}\\s*:\\s*["']([^"']*)["']`)) || [])[1];
    const note = (src.match(/export const note\s*=\s*`([\s\S]*?)`/) || [])[1] || '';
    const ck = mv('chart') || 'bar';
    const shape = { kind: ['bar', 'line', 'table'].includes(ck) ? ck : /kpi|tile/.test(ck) ? 'kpi' : 'bar', time: isTime(mv('x')),
      n: Math.min(4, Math.max(1, (note.match(/^\s*-\s/gm) || []).length || 2)), format: '$short' };
    const type = asType(shape.kind);
    const h = Object.assign({}, base, { id: nextId(PREFIX[type]), type, name: nameFor(nameOf(type, shape)), from: 'dashboard' });
    console.log(`Saved as a ${type}: the dashboard section showed a ${shape.kind}.`);
    return write(h, sectionItem(h, theme, shape), projectWords(src, generic).concat([path.basename(file, '.jsx')]), describeSection(type, shape, 'dashboard'));
  }

  /* An item started by hand: a valid shell with the next free id, to fill. Hand-made items are listed in
     original-samples.txt: exempt from the saved-item rules, held to the hand-made rule instead. */
  if (kind === 'new') {
    const t = String(args[1] || '').replace(/-/g, ' ');
    const type = { chart: 'chart', table: 'table', 'hero card': 'hero card', hero: 'hero card', animation: 'animation', layout: 'layout', slide: 'slide' }[t];
    if (!type) stop('new <chart|table|hero-card|animation|layout|slide> --name <name> [--group XX for a slide]');
    if (!opt('--name')) stop('new needs --name <short-descriptive-name>, such as bars-by-group-highlight');
    let id;
    if (type === 'slide') { const g = (opt('--group') || '').toUpperCase(); if (!GROUPS.includes(g)) stop(`a slide needs --group ${GROUPS.join('|')}`); id = nextId(g); }
    else id = nextId(PREFIX[type]);
    const h = { id, type, name: nameFor(), purpose: 'WRITE one sentence: what it shows and when to use it', from: 'design-library' };
    const ex = sample(false);
    let html;
    // charts, tables and hero cards start with their data note and slots; a slide with its spots marked
    if (type === 'chart') { h.data = PLAIN_NOTES.chart; html = chartItem(h, theme, prettyJson(plainBar(ex.labels, ex.vals))); }
    else if (type === 'slide') html = slideItem(h, theme, require('./item.js').markSpots(`<section id="${h.name}" data-component="${id}">\n  <p class="kicker">Section</p>\n  <h2>Headline: the point as a sentence, with its number</h2>\n  <div class="content">\n    <div class="chart" data-echart>\n<script type="application/json">\n${JSON.stringify(plainBar(ex.labels, ex.vals))}\n</script>\n</div>\n  </div>\n  <div class="footnote">What is measured, the period, the source.</div>\n</section>`));
    else if (type === 'table') { h.data = PLAIN_NOTES.table; html = kitItem(h, theme, { body: PLAIN_TABLE(ex.labels, ex.vals), js: CSV_JS }); }
    else if (type === 'hero card') { h.data = PLAIN_NOTES.tiles; html = kitItem(h, theme, { body: PLAIN_TILES(ex.labels.slice(0, 3), ex.vals.slice(0, 3)) }); }
    else if (type === 'animation') html = kitItem(h, theme, { animate: true,
      css: `/* motion runs only under html.play (the engine adds it on load and on Replay); without it the final state shows */\n.play .grow { animation: grow .9s cubic-bezier(.2,.7,.2,1); }\n@keyframes grow { from { width: 0; } }`,
      body: `<div class="lib-card good" style="max-width: 420px;">\n<div class="lib-lab">Label: the measure</div>\n<div class="lib-big"><span data-tick-up="80">80</span></div>\n<div class="lib-tick"><div class="a grow" style="width: 80%;"></div><div class="p" style="left: 70%;"></div></div>\n</div>` });
    else html = kitItem(h, theme, { body: `<div class="lib-panel">\n<h2>Layout piece: what it holds</h2>\n<p class="cap">Neutral sample content only</p>\n</div>` });
    // recordable as hand-made: exempt from dates, the 6-point cap and the denylist
    const f = path.join(LIB, 'original-samples.txt');
    fs.writeFileSync(f, (fs.existsSync(f) ? fs.readFileSync(f, 'utf8').trimEnd() : '# Hand-made items') + ` ${id}\n`);
    return write(h, html, null, [`${type} shell with neutral sample content, to fill by hand as AUTHORING.md says`]);
  }

  if (kind === 'theme') {
    const t = themeOf(opt('--from') || DEFAULT_THEME);
    const h = Object.assign({}, base, { id: nextId('TH'), type: 'theme', name: nameFor('new-theme'), from: 'design-library' });
    const fonts = fontsOf(opt('--from') || DEFAULT_THEME);
    return write(h, themeItem(h, t, fonts), [], [`theme: a copy of ${opt('--from') || DEFAULT_THEME}'s tokens and series order${fonts ? ', with its embedded font' : ''}, to edit`]);
  }

  /* The purpose line of a saved item, set without opening the file. Only the header line changes. Hand-made items are refused. */
  if (kind === 'purpose') {
    const id = args[1], text = String(args[2] || '').trim();
    const it = items().find(i => i.h.id === id);
    if (!it) stop(`no item ${id}`);
    const orig = fs.existsSync(path.join(LIB, 'original-samples.txt')) ? fs.readFileSync(path.join(LIB, 'original-samples.txt'), 'utf8') : '';
    if (new RegExp(`(^|\\s)${id}(\\s|$)`).test(orig.split('\n').filter(l => !l.startsWith('#')).join(' '))) stop(`${id} is hand-made; its purpose is edited by hand`);
    if (!text || /[\r\n]|-->/.test(text) || /^WRITE/.test(text) || !/[.!?]$/.test(text)) stop('give one sentence in quotes, ending with a full stop');
    const raw = fs.readFileSync(it.file, 'utf8');
    const next = raw.replace(/(<!-- ITEM\r?\n(?:[^\n]*\n)*?)purpose:[^\r\n]*/, (m, a) => `${a}purpose: ${text}`);
    if (next === raw) stop(`no purpose line in ${it.rel}`);
    fs.writeFileSync(it.file, next);
    return console.log(`${id} purpose set. Next: node build-index.js.`);
  }
  /* The recipe line of a saved chart, table or hero card: how to shape the data before it fills the slots. */
  if (kind === 'recipe') {
    const id = args[1], text = String(args[2] || '').trim();
    const it = items().find(i => i.h.id === id);
    if (!it) stop(`no item ${id}`);
    if (!it.h.data) stop(`${id} has no data note, so no recipe`);
    if (!text || /[\r\n]|-->/.test(text)) stop('give the recipe as one line in quotes');
    const raw = fs.readFileSync(it.file, 'utf8').split('\r\n').join('\n');
    const next = /\nrecipe:[^\n]*/.test(raw.split('-->')[0]) ? raw.replace(/\nrecipe:[^\n]*/, `\nrecipe: ${text}`) : raw.replace(/(\ndata:[^\n]*)/, `$1\nrecipe: ${text}`);
    fs.writeFileSync(it.file, next);
    return console.log(`${id} recipe set. Next: node build-index.js.`);
  }
  stop('first argument: slide | chart | report-section | dashboard-section | theme | new | purpose | recipe (see the top of this file)');
}

module.exports = { LIB, TYPES, PREFIX, GROUPS, DEFAULT_THEME, ECHARTS, ENGINE, KIT_CSS, CHART_CSS, HOST_CSS, PERIOD, readHeader, header, items, nextId, themeOf, fontsOf, tokensBlock, deckCss,
  slideItem, chartItem, kitItem, sectionItem, themeItem, neutralChart, neutralHtml, sampleOption, hash, prettyJson, autoSlots, tag, plainBar, PLAIN_TABLE, PLAIN_TILES, PLAIN_NOTES, CSV_JS };
if (require.main === module) cli();
