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
const TYPES = { slide: 'slides', chart: 'charts', 'report section': 'report-sections', 'dashboard section': 'dashboard-sections', theme: 'themes' };
const PREFIX = { chart: 'CT', 'report section': 'RS', 'dashboard section': 'DS', theme: 'TH' };
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
      const text = fs.readFileSync(file, 'utf8');
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
const tokensBlock = theme => `<style id="tokens">:root {\n${Object.entries(theme.css).map(([k, v]) => `  ${k}: ${v};`).join('\n')}\n  --series: ${theme.series.join(' ')};\n}</style>`;

/* The deck stylesheet without its colour and font tokens (those come from the theme). */
function deckCss(theme) {
  const skillCss = path.join(LIB, '..', '.claude', 'skills', 'presentation', 'references', 'base-styles.css');
  if (!fs.existsSync(skillCss)) {
    // a copy of the library without the skill beside it: reuse the stylesheet a slide item already carries
    const one = items().find(i => i.h.type === 'slide');
    if (!one) throw new Error('no presentation skill beside the library and no slide item to take the stylesheet from');
    return one.text.match(/<style id="deck-css">\n([\s\S]*?)\n<\/style>/)[1];
  }
  const base = fs.readFileSync(skillCss, 'utf8');
  return base.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^:root \{[\s\S]*?^\}/m, block =>
    block.split('\n').filter(l => !Object.keys(theme.css).some(k => l.trim().startsWith(k + ':'))).join('\n'))
    .replace(/\n\s*\n+/g, '\n').trim();
}

/* ---------- the shared lines every item carries: fit, theme, charts ---------- */
const ENGINE = `(function () {
  var root = document.documentElement;
  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function series() { return css('--series').split(/\\s+/).filter(Boolean).map(css); }
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
  var drawn = 0;
  function draw() {
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
      [].concat(o.series || []).forEach(function (s) { s.emphasis = { disabled: true }; });
      o.animation = false;
      if (box._chart) box._chart.dispose();
      if (!box._holder) { box._holder = document.createElement('div'); box._holder.style.cssText = 'position:absolute;inset:0;'; box.appendChild(box._holder); }
      box._chart = echarts.init(box._holder, name, { renderer: 'svg' });
      box._chart.setOption(o);
    });
  }
  function fit() {
    var f = document.querySelector('.fit');
    if (!f) return;
    var s = Math.min(window.innerWidth / f.offsetWidth, window.innerHeight / f.offsetHeight);
    f.style.transform = 'scale(' + s + ')';
  }
  /* A theme from the index: {theme: {css: {...}, series: [...]}}. Items keep their own look when opened alone. */
  window.addEventListener('message', function (e) {
    var t = e.data && e.data.theme;
    if (!t || document.body.hasAttribute('data-own-theme')) return;
    Object.keys(t.css || {}).forEach(function (k) { root.style.setProperty(k, t.css[k]); });
    if (t.series) root.style.setProperty('--series', t.series.join(' '));
    draw();
  });
  window.addEventListener('resize', function () { fit(); draw(); });
  fit(); draw();
})();`;

const page = (h, theme, head, body) => `<!doctype html>
${header(h)}
<html lang="en">
<head>
<meta charset="utf-8">
<title>${h.id} ${h.name}</title>
${tokensBlock(theme)}
${head}
<script src="${ECHARTS}"></script>
</head>
<body${h.type === 'theme' ? ' data-own-theme' : ''}>
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

function slideItem(h, theme, sectionHtml) {
  return page(h, theme, `<style id="deck-css">\n${deckCss(theme)}\n</style>\n${FRAME_SLIDE}`,
    `<div class="fit reveal"><div class="slides">\n<!-- ITEM:START -->\n${sectionHtml.trim()}\n<!-- ITEM:END -->\n</div></div>`);
}

function chartItem(h, theme, optionJson, title) {
  return page(h, theme, FRAME_BLOCK,
    `<div class="fit">\n<h2>${title || 'Heading: what is measured, the period'}</h2>\n<!-- ITEM:START -->\n<div class="chart" data-echart>\n<script type="application/json">\n${optionJson.trim()}\n</script>\n</div>\n<!-- ITEM:END -->\n</div>`);
}

function themeItem(h, theme) {
  const sw = Object.keys(theme.css).filter(k => !/font|weight/.test(k))
    .map(k => `<div class="sw"><i style="background: var(${k})"></i><span>${k}</span></div>`).join('\n');
  const option = { xAxis: { type: 'category', data: ['A', 'B', 'C', 'D', 'E', 'F'] }, yAxis: { type: 'value', show: false },
    series: theme.series.map((t, i) => ({ type: 'bar', name: t, data: [3, 5, 4, 6, 5, 7].map(v => v + i) })) };
  return page(h, theme, `${FRAME_BLOCK}\n<style id="theme-page">
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

/* The generic report section: what `python run.py add-section` writes, for this shape. */
function reportSource(shape) {
  const { kind, time, n, wide, format } = shape;
  const bullets = BULLET_SETS[time ? 'time' : 'group'].slice(0, n).map(([k, l, v]) => `    "**${k}.** ${l}, at ${v}.",`).join('\n');
  return `# Recreate with the analysis skill (cheapest): python run.py add-section NAME --source DATA --chart ${kind} --x GROUP --y VALUE --bullets ${n}
# Or save as sections/sN_NAME.py and add it to SECTIONS. CHANGE THESE: NAME, DATA, GROUP, VALUE; then reword TITLE and BULLETS.
# The source report's own calculation was not copied: this is the generic analytic for the shape.
"""Section NAME: VALUE summed by GROUP, shown as a ${kind} chart."""
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

/* The generic dashboard section: what `npm run new-section` writes, for this shape. */
function dashboardSource(shape) {
  const { kind, time, n } = shape;
  const notes = BULLET_SETS[time ? 'time' : 'group'].slice(0, n)
    .map(([k, l, v]) => `- ${k}: ${l.replace(/\{(\w+)\}/, time ? '{$1|month}' : '{$1}')} at ${v.replace(/\{(\w+)(?::[^}]*)?\}/, k === 'Groups' ? '{$1|int}' : '{$1|compact}')}.`).join('\n');
  return `// Recreate with the dashboard skill (cheapest): npm run new-section -- NAME --page TAB --tables DATA --chart ${kind} --x GROUP --y VALUE --note "a | b"
// Or save as Src/Sections/NAME.jsx and add it to index.js. CHANGE THESE: NAME, TAB, DATA, GROUP, VALUE; reword title, description and note.
// The source dashboard's own calculation was not copied: this is the generic section for the shape.
import { useMemo } from 'react';
import ChartECharts from '../Components/ChartECharts.jsx';
import { FORMATS } from '../Lib/format.js';

export const meta = {
  id: 'NAME', title: "Title: what is measured", tab: 'TAB', chart: '${kind}', library: 'echarts',
  description: "What this section shows, in 8 to 10 words",
  tables: ["DATA"], x: "GROUP", y: "VALUE", agg: 'sum',
};

// Reword these lines; keep the {metric|format} parts (they fill in the real numbers).
export const note = \`
${notes}
\`;

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
.card { height: 100%; box-sizing: border-box; background: var(--paper); border: 1px solid var(--rule); border-radius: var(--box-radius, 2px); display: flex; flex-direction: column; }
.head { padding: 14px 18px; border-bottom: 1px solid var(--rule); }
.head h3 { margin: 0; font: var(--heading-weight) 18px var(--heading-font); color: var(--navy); }
.head p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.chart { position: relative; flex: 1; min-height: 0; margin: 8px 12px 0; }
.note { margin: 0; padding: 10px 18px 14px 34px; border-top: 1px solid var(--rule); }
.note li { font-size: 13.5px; color: var(--ink); margin-bottom: 4px; }
.source { display: none; }
</style>`;

const sourceBlock = (file, text) => `<!-- SOURCE: ${file} (the thing to copy; its first line is the command that recreates it) -->\n` +
  `<script type="text/plain" class="source" id="source" data-file="${file}">\n${text.replace(/<\/script/gi, '<\\/script').trim()}\n</script>\n<!-- SOURCE END -->`;
const chartDiv = o => `<div class="chart" data-echart>\n<script type="application/json">\n${JSON.stringify(o)}\n</script>\n</div>`;

function reportItem(h, theme, shape) {
  const s = sample(shape.time), money = /\$/.test(shape.format);
  const title = fill(`{largest_label} had the ${shape.time ? 'highest' : 'largest'} value, {largest:$short}`, s.m, money);
  const lis = BULLET_SETS[shape.time ? 'time' : 'group'].slice(0, shape.n).map(([k, l, v]) => `<li><b>${k}.</b> ${fill(l, s.m, money)}, at ${fill(v, s.m, money)}.</li>`).join('\n');
  return page(h, theme, FRAME_REPORT,
    `<div class="fit">\n<h2>${title}</h2>\n<!-- ITEM:START -->\n<div class="body ${shape.wide ? 'wide' : 'side'}">\n${chartDiv(sampleOption(shape.kind, shape.time, money))}\n<ul>\n${lis}\n</ul>\n</div>\n<!-- ITEM:END -->\n</div>\n` +
    sourceBlock('sN_NAME.py', reportSource(shape)));
}

function dashboardItem(h, theme, shape) {
  const s = sample(shape.time);
  // a finished-looking sample card; the placeholders to change live only in the SOURCE block
  const lis = BULLET_SETS[shape.time ? 'time' : 'group'].slice(0, shape.n).map(([k, l, v]) => `<li>${k}: ${fill(l, s.m, true)} at ${fill(v, s.m, k !== 'Groups')}.</li>`).join('\n');
  const head = shape.time ? ['Amount by month', `Monthly total, highest month highlighted`] : ['Amount by group', 'Total by group, largest highlighted'];
  return page(h, theme, FRAME_DASH,
    `<div class="fit">\n<!-- ITEM:START -->\n<div class="card">\n<div class="head"><h3>${head[0]}</h3><p>${head[1]}</p></div>\n` +
    `${chartDiv(sampleOption(shape.kind, shape.time, true))}\n<ul class="note">\n${lis}\n</ul>\n</div>\n<!-- ITEM:END -->\n</div>\n` +
    sourceBlock('NAME.jsx', dashboardSource(shape)));
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
  const write = (h, html, words) => {
    const dir = path.join(LIB, TYPES[h.type]);
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `${h.id}-${h.name}.html`);
    if (fs.existsSync(file)) stop(`${file} exists`);
    fs.writeFileSync(file, html);
    recordWords(h.id, words);
    console.log(`Saved ${h.id} (${h.type}) as ${path.relative(process.cwd(), file).split(path.sep).join('/')}.` +
      `\nNext: replace "WRITE ..." on its purpose line with one sentence true of the preview, then node build-index.js.`);
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
      return write(h, slideItem(h, theme, html), words);
    }
    if (!option) stop(`slide ${sid} has no chart`);
    const h = Object.assign({}, base, { id: nextId('CT'), type: 'chart', name: nameFor(shapeName), from: 'presentation' });
    return write(h, chartItem(h, theme, JSON.stringify(neutralChart(option), null, 1)), words);
  }

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
    if (shape.kind === 'table') shape.kind = 'bar';
    const highlight = /idxmax|largest/.test(src) ? '-highlight' : '';
    const h = Object.assign({}, base, { id: nextId('RS'), type: 'report section', name: nameFor(`report-${shape.kind === 'line' ? 'line' : 'bars'}-by-${shape.time ? 'month' : 'group'}${highlight}`), from: 'analysis' });
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
    return write(h, reportItem(h, theme, shape), projectWords(src, generic).concat([path.basename(file, '.py')],
      values.filter(v => /[A-Za-z]/.test(v) && !PERIOD.test(v) && !generic.has(v.toLowerCase()))));
  }

  if (kind === 'dashboard-section') {
    const dash = opt('--dashboard'), sec = opt('--section');
    if (!dash || !sec) stop('dashboard-section needs --dashboard <dashboard folder> --section <id, file or path> (forward slashes)');
    const file = findIn(path.join(dash, 'Src', 'Sections'), sec, '.jsx');
    const src = fs.readFileSync(file, 'utf8');
    const meta = (src.match(/export const meta\s*=\s*\{([\s\S]*?)\};/) || [])[1] || '';
    const mv = k => (meta.match(new RegExp(`\\b${k}\\s*:\\s*["']([^"']*)["']`)) || [])[1];
    const note = (src.match(/export const note\s*=\s*`([\s\S]*?)`/) || [])[1] || '';
    const shape = { kind: mv('chart') === 'line' ? 'line' : 'bar', time: isTime(mv('x')), n: Math.min(4, Math.max(1, (note.match(/^\s*-\s/gm) || []).length || 2)) };
    const h = Object.assign({}, base, { id: nextId('DS'), type: 'dashboard section', name: nameFor(`card-${shape.kind === 'line' ? 'line' : 'bars'}-by-${shape.time ? 'month' : 'group'}`), from: 'dashboard' });
    return write(h, dashboardItem(h, theme, shape), projectWords(src, generic).concat([path.basename(file, '.jsx')]));
  }

  if (kind === 'theme') {
    const t = themeOf(opt('--from') || DEFAULT_THEME);
    const h = Object.assign({}, base, { id: nextId('TH'), type: 'theme', name: nameFor('new-theme'), from: 'design-library' });
    return write(h, themeItem(h, t), []);
  }
  stop('first argument: slide | chart | report-section | dashboard-section | theme (see the top of this file)');
}

module.exports = { LIB, TYPES, PREFIX, GROUPS, DEFAULT_THEME, ECHARTS, ENGINE, PERIOD, readHeader, header, items, nextId, themeOf, tokensBlock, deckCss,
  slideItem, chartItem, reportItem, dashboardItem, themeItem, neutralChart, neutralHtml, sampleOption, hash };
if (require.main === module) cli();
