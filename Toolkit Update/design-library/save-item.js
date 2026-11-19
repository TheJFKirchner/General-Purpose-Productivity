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
 *
 * Each save prints a "Preview:" description (layout, what the chart or table shows, the highlight, bullets
 * or note lines, what was not copied): the purpose sentence is written from it, without opening the item.
 *
 * A slide or chart is copied with a small made-up sample and neutral wording. A report or dashboard
 * section becomes a clean generic definition of its shape (never the project's own calculation),
 * with the command that recreates it first. Project names (columns, tables, values) are recorded
 * as hashes in denylist.json so the index check can catch any that survive. The next free id;
 * one line left to write: "purpose: WRITE ...". Never writes to the source project. Use forward slashes.
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
const header = h => `<!-- ITEM\nid: ${h.id}\ntype: ${h.type}\nname: ${h.name}\npurpose: ${h.purpose}\nfrom: ${h.from}\n-->`;

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
const ENGINE = `(function () {
  var root = document.documentElement, body = document.body;
  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function series() { return css('--series').split(/\\s+/).filter(Boolean).map(css); }
  /* Motion only for items marked data-animate (body or one element). Reduced motion means no AUTOPLAY:
     load, scroll into view and theme changes show the finished state. An explicit action (Replay, an item's
     own Play or step control, opening the item in the index popup) always plays: it sets forced. */
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches, forced = false;
  function marked(box) { return body.hasAttribute('data-animate') || !!(box && box.hasAttribute('data-animate')); }
  function moves(box) { return (forced || !still) && marked(box); }
  function force() { forced = true; root.classList.add('forced'); if (!root.classList.contains('play')) root.classList.add('play'); }
  function resolve(o) {
    Object.keys(o).forEach(function (k) {
      var v = o[k];
      if (typeof v === 'string' && v.indexOf('var(--') === 0) o[k] = css(v.slice(4, -1)) || v;
      else if (v && typeof v === 'object') resolve(v);
    });
  }
  function theme() {
    var axis = { axisLine: { lineStyle: { color: css('--rule') } }, axisTick: { show: false }, axisLabel: { color: css('--muted'), fontSize: 15 } };
    return {
      color: series(), textStyle: { fontFamily: css('--body-font'), color: css('--ink') },
      categoryAxis: Object.assign({}, axis, { splitLine: { show: false } }),
      valueAxis: Object.assign({}, axis, { axisLine: { show: false }, splitLine: { lineStyle: { color: css('--chart-grid') } } }),
      legend: { bottom: 0, icon: 'rect', itemWidth: 14, itemHeight: 14, textStyle: { color: css('--ink'), fontSize: 15 } },
      bar: { itemStyle: { borderRadius: 0 }, barMaxWidth: 110, label: { color: css('--ink'), fontSize: 16, fontWeight: 600 } },
      line: { lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 8, label: { color: css('--ink'), fontSize: 15 }, endLabel: { fontSize: 15 } },
      scatter: { symbolSize: 16, itemStyle: { opacity: 1 }, label: { color: css('--ink'), fontSize: 15 } },
      markLine: { label: { fontSize: 14, color: css('--muted') } },
      pie: { label: { color: css('--ink'), fontSize: 15 }, itemStyle: { borderColor: css('--paper'), borderWidth: 2 } }
    };
  }
  /* Hover: a one-line tooltip and a light emphasis on the hovered mark. Nothing moves, fades or redraws on hover.
     Off for one chart with data-hover="off" (or the item's body), or "tooltip": {"show": false} in its JSON;
     an item may supply its own tooltip.formatter. Off when exported (html.is-export) and never during a play. */
  function hoverOff(box) { return root.classList.contains('is-export') || body.getAttribute('data-hover') === 'off' || box.getAttribute('data-hover') === 'off'; }
  function fmt(t, p, v) {
    return String(t).split('{c}').join(v).split('{value}').join(v).split('{b}').join(p.name || '').split('{a}').join(p.seriesName || '')
      .replace(/\{@\[(\d+)\]\}/g, function (m, i) { return Array.isArray(p.value) ? p.value[+i] : v; });
  }
  function hover(o) {
    var list = [].concat(o.series || []);
    var cat = [].concat(o.xAxis || [], o.yAxis || []).some(function (a) { return a && a.type === 'category'; });
    var valAxis = [].concat(o.yAxis || [], o.xAxis || []).filter(function (a) { return a && a.type === 'value'; });
    var axisFmt = function (i) { var a = valAxis[i || 0] || valAxis[0]; return a && a.axisLabel && typeof a.axisLabel.formatter === 'string' ? a.axisLabel.formatter : null; };
    var lines = list.some(function (x) { return x.type === 'line'; });
    var axis = cat && list.every(function (x) { return x.type === 'line' || x.type === 'bar' || x.type === 'scatter'; });
    function hidden(x) { return !x || (x.itemStyle && x.itemStyle.opacity === 0) || x.silent === true || /^_/.test(x.name || ''); }
    function value(p) {
      var x = list[p.seriesIndex] || {}, v = p.value;
      if (Array.isArray(v)) v = x.type === 'scatter' || x.type === 'effectScatter' ? v[v.length > 2 ? 2 : 1] : v[v.length - 1];
      if (v == null || v === '-') return null;
      var own = p.data && p.data.label && typeof p.data.label.formatter === 'string' ? p.data.label.formatter : null;
      var shared = x.label && typeof x.label.formatter === 'string' ? x.label.formatter : null;
      var t = own || shared || axisFmt(x.yAxisIndex || x.xAxisIndex);
      return t ? fmt(t, p, v) : (typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : String(v));
    }
    /* the series name goes in front once, never when the value text (its own label formatter) already carries it */
    function named(p) { return list.length > 1 && p.seriesName && p.seriesName.indexOf('series') !== 0 && String(value(p)).indexOf(p.seriesName) === -1; }
    var tip = {
      show: true, trigger: axis ? 'axis' : 'item', confine: true, transitionDuration: 0, showDelay: 0, hideDelay: 60, enterable: false,
      backgroundColor: css('--paper'), borderColor: css('--rule'), borderWidth: 1, padding: [6, 10],
      textStyle: { color: css('--ink'), fontFamily: css('--body-font'), fontSize: 13 },
      extraCssText: 'box-shadow:none;border-radius:' + (css('--radius') || '2px') + ';pointer-events:none;',
      axisPointer: lines
        ? { type: 'line', animation: false, lineStyle: { color: css('--muted'), width: 1, type: 'solid' }, label: { show: false } }
        : { type: 'shadow', animation: false, shadowStyle: { color: css('--chart-grid'), opacity: 0.7 }, label: { show: false } },
      formatter: function (p) {
        if (Array.isArray(p)) {
          var rows = p.filter(function (q) { return !hidden(list[q.seriesIndex]) && value(q) != null; })
            .map(function (q) { return (named(q) ? q.seriesName + ': ' : '') + '<b>' + value(q) + '</b>'; });
          return rows.length ? (p[0].name ? p[0].name + (rows.length > 1 ? '<br>' : ' ') : '') + rows.join(rows.length > 1 ? '<br>' : '') : '';
        }
        if (p.componentType !== 'series' || hidden(list[p.seriesIndex]) || value(p) == null) return '';
        return (named(p) ? p.seriesName + ' \u00b7 ' : '') + (p.name ? p.name + ': ' : '') + '<b>' + value(p) + '</b>';
      }
    };
    o.tooltip = Object.assign(tip, o.tooltip && typeof o.tooltip === 'object' ? o.tooltip : {});
    list.forEach(function (x) {
      if (x.emphasis && !x.emphasis.disabled) return;   /* the item's own emphasis stands */
      var w = x.lineStyle && x.lineStyle.width || 3;
      x.emphasis = x.type === 'line' ? { focus: 'none', scale: false, lineStyle: { width: w }, label: { show: x.label && x.label.show } }
        : { focus: 'none', scale: false, itemStyle: { borderColor: css('--navy'), borderWidth: 1.5 } };
      if (hidden(x)) x.emphasis = { disabled: true };
    });
  }
  /* Tables: a native tooltip on each cell (row, column: value) and a subtle highlight (kit CSS). */
  function tableTips() {
    Array.prototype.forEach.call(document.querySelectorAll('.lib-table tbody tr'), function (tr) {
      var table = tr.closest('table'), heads = table ? Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) { return th.innerText.trim(); }) : [];
      var row = tr.cells[0] ? tr.cells[0].innerText.trim() : '';
      Array.prototype.forEach.call(tr.cells, function (td, i) { if (i && !td.title && td.innerText.trim()) td.title = row + (heads[i] ? ' \u00b7 ' + heads[i] : '') + ': ' + td.innerText.trim(); });
    });
  }
  var drawn = 0;
  function draw(play) {
    if (!window.echarts) return;
    var name = 'item' + (++drawn);
    echarts.registerTheme(name, theme());
    Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (box) {
      var src = box.querySelector('script[type="application/json"]');
      if (!src) return;
      var o = JSON.parse(src.textContent);
      resolve(o);
      var y = o.yAxis && !Array.isArray(o.yAxis) && o.yAxis.name && o.yAxis.show !== false;
      if (!o.grid) o.grid = { left: y ? 46 : 8, right: 28, top: 30, bottom: o.legend ? 44 : 8, containLabel: true };
      var anim = play && moves(box);
      var off = hoverOff(box) || (o.tooltip && o.tooltip.show === false);
      if (off) { o.tooltip = { show: false }; [].concat(o.series || []).forEach(function (s) { s.emphasis = { disabled: true }; }); }
      else hover(o);
      o.animation = !!anim;
      if (anim) { o.animationDuration = o.animationDuration || 900; o.animationEasing = o.animationEasing || 'cubicOut'; }
      if (box._chart) box._chart.dispose();
      if (!box._holder) { box._holder = document.createElement('div'); box._holder.style.cssText = 'position:absolute;inset:0;'; box.appendChild(box._holder); }
      box._chart = echarts.init(box._holder, name, { renderer: 'svg' });
      box._chart.setOption(o);
      /* no hover while it plays: the pointer is ignored until the draw-in is over */
      if (anim) { box._holder.style.pointerEvents = 'none'; clearTimeout(box._still); box._still = setTimeout(function () { box._holder.style.pointerEvents = ''; }, (o.animationDuration || 900) + 300); }
    });
    window.dispatchEvent(new Event('item:draw'));
  }
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
    chart: function (el) { var box = el && el.closest ? (el.closest('.chart[data-echart]') || (el.querySelector && el.querySelector('.chart[data-echart]'))) : document.querySelector('.chart[data-echart]'); return (box && box._chart) || null; },
    redraw: function () { draw(false); }
  };
  window.itemRedraw = window.ItemEngine.redraw;
  window.addEventListener('beforeprint', function () { Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (b) { if (b._chart) b._chart.dispatchAction({ type: 'hideTip' }); }); });
  window.addEventListener('resize', function () { fit(); draw(false); });
  tableTips(); fit(); replay();
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

function chartItem(h, theme, optionJson, title) {
  return page(h, theme, `${FRAME_BLOCK}\n<style id="item-css">\n</style>`,
    `<div class="fit">\n<h2>${title || 'Heading: what is measured, the period'}</h2>\n<!-- ITEM:START -->\n<div class="chart" data-echart>\n<script type="application/json">\n${optionJson.trim()}\n</script>\n</div>\n<!-- ITEM:END -->\n</div>`);
}

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

/* The SOURCE block: both recreate commands first (where they apply), then each generic definition. */
function sourceBlock(shape) {
  const inReport = ['bar', 'line', 'table'].includes(shape.kind);
  const cmds = [
    inReport ? `Recreate in a report:    python run.py add-section NAME --source DATA --chart ${shape.kind} --x GROUP --y VALUE --bullets ${shape.n}` : null,
    `Recreate in a dashboard: npm run new-section -- NAME --page TAB --tables DATA --chart ${shape.kind} --x GROUP --y VALUE --note "a | b"`,
    'CHANGE THESE: NAME, DATA, GROUP, VALUE (and TAB in a dashboard). The source\'s own calculation was not copied: these are generic definitions of the shape.',
  ].filter(Boolean);
  const block = (file, text) => `<script type="text/plain" class="source" data-file="${file}">\n${text.replace(/<\/script/gi, '<\\/script').trim()}\n</script>`;
  return `<!-- SOURCE: the thing to copy. Commands first, cheapest way to reuse it -->\n<script type="text/plain" class="source" id="source" data-file="commands.txt">\n${cmds.join('\n')}\n</script>\n` +
    (inReport ? block('sN_NAME.py', reportSource(shape)) + '\n' : '') + block('NAME.jsx', dashboardSource(shape)) + '\n<!-- SOURCE END -->';
}

const FRAME_REPORT = `<style id="frame">
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--paper); color: var(--ink); font-family: var(--body-font); }
.fit { width: 960px; height: 540px; transform-origin: 0 0; box-sizing: border-box; padding: 30px 40px; display: flex; flex-direction: column; gap: 14px; }
.fit h2 { margin: 0; font: var(--heading-weight) 24px var(--heading-font); color: var(--navy); }
.body { flex: 1; min-height: 0; display: grid; gap: 28px; }
.body.side { grid-template-columns: 3fr 2fr; align-items: center; }
.body.wide { grid-template-rows: 1fr auto; }
.chart { position: relative; min-height: 0; height: 100%; }
.fit ul { margin: 0; padding-left: 18px; }
.wide ul { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 24px; }
.fit li { font-size: 15px; line-height: 1.45; margin-bottom: 8px; color: var(--ink); }
.fit li b { color: var(--navy); }
.source { display: none; }
</style>`;

const FRAME_DASH = `<style id="frame">
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--wash); color: var(--ink); font-family: var(--body-font); }
.fit { width: 960px; height: 540px; transform-origin: 0 0; box-sizing: border-box; padding: 26px; }
.card { height: 100%; box-sizing: border-box; background: var(--paper); border: 1px solid var(--rule); border-radius: var(--radius); display: flex; flex-direction: column; }
.head { padding: 14px 18px; border-bottom: 1px solid var(--rule); }
.head h3 { margin: 0; font: var(--heading-weight) 18px var(--heading-font); color: var(--navy); }
.head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.chart { position: relative; flex: 1; min-height: 0; margin: 8px 12px 0; }
.note { margin: 0; padding: 10px 18px 14px 34px; border-top: 1px solid var(--rule); }
.note li { font-size: 13.5px; color: var(--ink); margin-bottom: 4px; }
.source { display: none; }
</style>`;

const chartDiv = o => `<div class="chart" data-echart>\n<script type="application/json">\n${JSON.stringify(o)}\n</script>\n</div>`;

/* The words for a saved section's preview (same shapes as sectionItem below). */
function describeSection(type, shape, style, from) {
  const s = sample(shape.time), by = shape.time ? 'month' : 'group', top = s.labels[s.hi];
  const notes = `${shape.n} note line${shape.n === 1 ? '' : 's'} (${BULLET_SETS[shape.time ? 'time' : 'group'].slice(0, shape.n).map(b => b[0].toLowerCase()).join(', ')})`;
  const out = [];
  if (type === 'table') out.push(`table in a panel: amount by ${by}, ${s.labels.length} rows, columns ${shape.time ? 'Month' : 'Group'} / Value / a meter of the share of the largest; highlighted row: ${top}; ${notes} under it`);
  else if (type === 'hero card') out.push(`hero card: one tile with the latest amount as a big number, a good-coloured up delta on the period before, and ${notes}`);
  else if (style === 'report') out.push(`chart, report layout: a sentence heading naming the ${shape.time ? 'highest month' : 'largest group'}, ${shape.kind === 'line' ? 'a line with an end label' : 'columns with value labels'} by ${by} (${s.labels.length} points, ${shape.kind === 'line' ? 'no mark highlighted' : `${top} highlighted, the rest muted`}) ${shape.wide ? 'with the bullets in a row under it' : 'with the bullets beside it'}; ${shape.n} bullet${shape.n === 1 ? '' : 's'}`);
  else out.push(`chart, dashboard card layout: a card with a title and subtitle, ${shape.kind === 'line' ? 'a line with an end label' : 'columns with value labels'} by ${by} (${s.labels.length} points, ${shape.kind === 'line' ? 'no mark highlighted' : `${top} highlighted, the rest muted`}), and ${notes} under it`);
  out.push(`source block: the recreate command${['bar', 'line', 'table'].includes(shape.kind) ? 's for a report and a dashboard' : ' for a dashboard'}, then generic definitions`);
  out.push(`not copied: the ${from} section's own calculation, names, wording and numbers (made-up round values instead)`);
  return out;
}

/* A liked section, as what it shows: a chart (report-style or card-style layout), a table or a hero card. */
function sectionItem(h, theme, shape, style) {
  const s = sample(shape.time), money = /\$/.test(shape.format || '$');
  const lines = BULLET_SETS[shape.time ? 'time' : 'group'].slice(0, shape.n);
  if (h.type === 'table') {
    const rows = s.labels.map((l, i) => `<tr${i === s.hi ? ' class="on"' : ''}><td class="left">${l}</td><td>${money ? `$${s.vals[i]}K` : s.vals[i]}</td>` +
      `<td class="left"><span class="lib-meter"><b style="width:${Math.round(100 * s.vals[i] / s.m.largest)}%"></b></span></td></tr>`).join('\n');
    return kitItem(h, theme, { body: `<div class="lib-panel">\n<div class="lib-panelhead"><div><h2>${shape.time ? 'Amount by month' : 'Amount by group'}</h2><p class="cap">Total, ${shape.time ? 'highest month' : 'largest group'} highlighted</p></div></div>\n` +
      `<table class="lib-table">\n<thead><tr><th class="left">${shape.time ? 'Month' : 'Group'}</th><th>Value</th><th class="left">Share of largest</th></tr></thead>\n<tbody>\n${rows}\n</tbody>\n</table>\n` +
      `<ul class="lib-note">\n${lines.map(([k, l, v]) => `<li>${k}: ${fill(l, s.m, money)} at ${fill(v, s.m, money && k !== 'Groups')}.</li>`).join('\n')}\n</ul>\n</div>`, after: sourceBlock(shape) + '\n' });
  }
  if (h.type === 'hero card') {
    return kitItem(h, theme, { body: `<div class="lib-cards">\n<div class="lib-card good">\n<div class="lib-lab">Amount, latest period</div>\n<div class="lib-big">$${s.m.latest}K</div>\n` +
      `<div class="lib-sub"><span class="lib-delta good">&#9650; 9%</span> on the period before</div>\n` +
      `<ul class="lib-note">\n${lines.map(([k, l, v]) => `<li>${k}: ${fill(l, s.m, true)} at ${fill(v, s.m, k !== 'Groups')}.</li>`).join('\n')}\n</ul>\n</div>\n</div>`, after: sourceBlock(shape) + '\n' });
  }
  if (style === 'report') {
    const title = fill(`{largest_label} had the ${shape.time ? 'highest' : 'largest'} value, {largest:$short}`, s.m, money);
    const lis = lines.map(([k, l, v]) => `<li><b>${k}.</b> ${fill(l, s.m, money)}, at ${fill(v, s.m, money)}.</li>`).join('\n');
    return page(h, theme, FRAME_REPORT,
      `<div class="fit">\n<h2>${title}</h2>\n<!-- ITEM:START -->\n<div class="body ${shape.wide ? 'wide' : 'side'}">\n${chartDiv(sampleOption(shape.kind, shape.time, money))}\n<ul>\n${lis}\n</ul>\n</div>\n<!-- ITEM:END -->\n</div>\n` + sourceBlock(shape));
  }
  // card-style layout, a finished-looking sample; the placeholders to change live only in the SOURCE block
  const lis = lines.map(([k, l, v]) => `<li>${k}: ${fill(l, s.m, true)} at ${fill(v, s.m, k !== 'Groups')}.</li>`).join('\n');
  const head = shape.time ? ['Amount by month', 'Monthly total, highest month highlighted'] : ['Amount by group', 'Total by group, largest highlighted'];
  return page(h, theme, FRAME_DASH,
    `<div class="fit">\n<!-- ITEM:START -->\n<div class="card">\n<div class="head"><h3>${head[0]}</h3><p>${head[1]}</p></div>\n` +
    `${chartDiv(sampleOption(shape.kind, shape.time, true))}\n<ul class="note">\n${lis}\n</ul>\n</div>\n<!-- ITEM:END -->\n</div>\n` + sourceBlock(shape));
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
      const html = neutralHtml(section).replace(/^<section\b([^>]*)>/, (all, a) =>
        `<section id="${h.name}" data-component="${h.id}"${a.replace(/\s*\bid="[^"]*"/, '')}>`);
      const kept = (html.match(/<script type="application\/json">([\s\S]*?)<\/script>/) || [])[1];
      return write(h, slideItem(h, theme, html), words, describeSlide(html, g, kept ? JSON.parse(kept) : null, layout));
    }
    if (!option) stop(`slide ${sid} has no chart`);
    const h = Object.assign({}, base, { id: nextId('CT'), type: 'chart', name: nameFor(shapeName), from: 'presentation' });
    const neutral = neutralChart(option);
    return write(h, chartItem(h, theme, JSON.stringify(neutral, null, 1)), words, [
      `chart alone under a placeholder heading: ${describeChart(neutral)}`,
      'not copied: the slide\'s wording, labels (neutral months or Group A, B ...), series names (Series 1, 2 ...) and values (made-up round values, at most 6 points)']);
  }

  /* A liked section is saved as what it shows: a table, a hero card (tiles, KPI) or a chart. */
  const asType = k => (k === 'table' ? 'table' : /^(kpi|tile|tiles|card)$/.test(k) ? 'hero card' : 'chart');
  const nameOf = (type, shape, style) => type === 'table' ? `table-by-${shape.time ? 'month' : 'group'}-meters`
    : type === 'hero card' ? `hero-latest-delta${shape.time ? '' : '-group'}`
    : `${style === 'report' ? 'report' : 'card'}-${shape.kind === 'line' ? 'line' : 'bars'}-by-${shape.time ? 'month' : 'group'}${style === 'report' ? '-highlight' : ''}`;

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
    const h = Object.assign({}, base, { id: nextId(PREFIX[type]), type, name: nameFor(nameOf(type, shape, 'report')), from: 'analysis' });
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
    return write(h, sectionItem(h, theme, shape, 'report'), projectWords(src, generic).concat([path.basename(file, '.py')],
      values.filter(v => /[A-Za-z]/.test(v) && !PERIOD.test(v) && !generic.has(v.toLowerCase()))), describeSection(type, shape, 'report', 'report'));
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
    const h = Object.assign({}, base, { id: nextId(PREFIX[type]), type, name: nameFor(nameOf(type, shape, 'card')), from: 'dashboard' });
    console.log(`Saved as a ${type}: the dashboard section showed a ${shape.kind}.`);
    return write(h, sectionItem(h, theme, shape, 'card'), projectWords(src, generic).concat([path.basename(file, '.jsx')]), describeSection(type, shape, 'card', 'dashboard'));
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
    if (type === 'chart') html = chartItem(h, theme, JSON.stringify(sampleOption('bar', false, false), null, 1));
    else if (type === 'slide') html = slideItem(h, theme, `<section id="${h.name}" data-component="${id}">\n  <p class="kicker">Section</p>\n  <h2>Headline: the point as a sentence, with its number</h2>\n  <div class="content">\n    ${chartDiv(sampleOption('bar', false, false))}\n  </div>\n  <div class="footnote">What is measured, the period, the source.</div>\n</section>`);
    else if (type === 'table') html = kitItem(h, theme, { body: `<div class="lib-panel">\n<div class="lib-panelhead"><div><h2>Heading: what the table shows</h2><p class="cap">Caption: the measure</p></div></div>\n<table class="lib-table">\n<thead><tr><th class="left">Group</th><th>Value</th></tr></thead>\n<tbody>\n${ex.labels.map((l, i) => `<tr${i === ex.hi ? ' class="on"' : ''}><td class="left">${l}</td><td>${ex.vals[i]}</td></tr>`).join('\n')}\n</tbody>\n</table>\n</div>` });
    else if (type === 'hero card') html = kitItem(h, theme, { body: `<div class="lib-cards">\n<div class="lib-card good">\n<div class="lib-lab">Label: the measure</div>\n<div class="lib-big">80</div>\n<div class="lib-sub"><span class="lib-delta good">&#9650; 5</span> on the period before</div>\n</div>\n</div>` });
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
  stop('first argument: slide | chart | report-section | dashboard-section | theme | new | purpose (see the top of this file)');
}

module.exports = { LIB, TYPES, PREFIX, GROUPS, DEFAULT_THEME, ECHARTS, ENGINE, KIT_CSS, PERIOD, readHeader, header, items, nextId, themeOf, fontsOf, tokensBlock, deckCss,
  slideItem, chartItem, kitItem, sectionItem, themeItem, neutralChart, neutralHtml, sampleOption, hash };
if (require.main === module) cli();
