#!/usr/bin/env node

/**
 * Creates a reveal.js presentation scaffold: presentation.html and styles.css
 * (plan.md only with --plan-only, for full mode). --refresh rewrites the engine
 * of an existing deck or library file and keeps its slides.
 * Usage: node create-presentation.js [options]
 *
 * Adapted from github.com/ryanbbrown/revealjs-skill (MIT). Added: plan.md, the bottom
 * section bar, and ECharts charts (in place of Chart.js) that read the theme variables in styles.css.
 */

const fs = require('fs');
const path = require('path');

const REFERENCES = path.join(__dirname, '..', 'references');
const BASE_STYLES_PATH = path.join(REFERENCES, 'base-styles.css');
const PLAN_TEMPLATE_PATH = path.join(REFERENCES, 'plan-template.md');

function parseArgs(args) {
  const options = {
    slides: null,
    structure: null,
    output: 'presentation.html',
    title: 'Presentation',
    stylesFile: 'styles.css',
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--slides' || arg === '-s') {
      options.slides = parseInt(args[++i], 10);
    } else if (arg === '--structure') {
      options.structure = args[++i].split(',').map(n => n === 'd' ? 'd' : parseInt(n, 10));
    } else if (arg === '--output' || arg === '-o') {
      options.output = args[++i];
    } else if (arg === '--title') {
      options.title = args[++i];
      options.titleSet = true;
    } else if (arg === '--styles') {
      options.stylesFile = args[++i];
      options.stylesSet = true;
    } else if (arg === '--back') {
      options.back = args[++i];
    } else if (arg === '--plan-only') {
      options.planOnly = true;
    } else if (arg === '--refresh') {
      options.refresh = args[++i];
    } else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }
  }

  return options;
}

function printHelp() {
  console.log(`
create-presentation.js - Generate a reveal.js presentation scaffold

Usage: node create-presentation.js [options]

Options:
  (neither --slides nor --structure: the BRIEF and one line to replace with every slide in one Edit)
  --slides, -s <num>    Number of placeholder slides
  --structure <list>    Mixed layout: comma-separated values (e.g., "1,1,d,3,1,d,1")
                        - Number 1 = single horizontal slide
                        - Number >1 = vertical stack of that many slides
                        - 'd' = section divider slide
                        Cannot be used with --slides
  --output, -o <file>   Output HTML path (default: presentation.html). Its folder is created.
  --title <text>        Presentation title (default: Presentation)
  --styles <file>       Custom CSS filename (default: styles.css)
  --plan-only           Full mode: create only the folder and plan.md (from plan-template.md)
  --back <href>         Add a small link back to an index page (the design library uses this)
  --refresh <file>      Rewrite the engine (everything outside SLIDES:START/END) of an existing
                        deck or library file, keeping its slides, title, styles link and back link
  --help, -h            Show this help message

Also writes styles.css (from base-styles.css) next to the HTML file, unless it already exists.

Examples:
  node create-presentation.js --slides 5 --title "Churn update" -o deck/2026-11-churn/presentation.html
  node create-presentation.js --structure 1,1,d,1,1,1,d,1 --title "Q4 Review" -o deck/2026-11-q4/presentation.html
  node create-presentation.js --refresh deck/2026-11-churn/presentation.html
`);
}

function escapeHtml(text) {
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Generates slides from a structure array (e.g., [1, 1, 'd', 5, 1, 2]) */
function generateSlides(structure) {
  let slides = '';
  let hIndex = 1; // Horizontal index (1-based for display)
  let dividerCount = 1;

  for (let colIndex = 0; colIndex < structure.length; colIndex++) {
    const item = structure[colIndex];

    if (item === 'd') {
      slides += `
      <section id="divider-${dividerCount}" class="section-divider" data-state="is-section-divider">
        <h1>Section ${dividerCount} Title</h1>
      </section>
`;
      dividerCount++;
      hIndex++;
    } else if (item === 1) {
      if (hIndex === 1) {
        slides += `
      <section id="title" class="section-divider" data-state="is-section-divider">
        <h1>Presentation Title</h1>
      </section>
`;
      } else {
        slides += `
      <section id="slide-${hIndex}">
        <h2>Slide ${hIndex} Title Here</h2>
      </section>
`;
      }
      hIndex++;
    } else {
      slides += `
      <section>
`;
      for (let vIndex = 1; vIndex <= item; vIndex++) {
        slides += `        <section id="slide-${hIndex}-${vIndex}">
          <h2>Slide ${hIndex}.${vIndex} Title Here</h2>
        </section>
`;
      }
      slides += `      </section>
`;
      hIndex++;
    }
  }

  return slides;
}

function generateHTML(options) {
  const brief = `
      <!-- BRIEF
      Audience:
      Want from them:
      Minutes:
      Answer:
      Basis: (date basis, comparison period)
      Sources:
      Slides: (written by slides.js; do not edit)
      -->
`;
  const slidesContent = options.slidesHtml != null ? options.slidesHtml : brief + (options.structure ? generateSlides(options.structure) : '\n      <!-- NEW SLIDES: replace this line with every slide in one Edit -->\n') + '\n';
  const backLink = options.back
    ? `    <a class="library-back" href="${escapeHtml(options.back)}" onclick="this.href='${escapeHtml(options.back)}#'+Reveal.getCurrentSlide().id" style="position:absolute;top:14px;right:18px;z-index:30;font:600 13px 'Segoe UI',system-ui,sans-serif;color:var(--blue);background:var(--wash);border:1px solid var(--rule);padding:6px 14px;border-radius:2px;text-decoration:none;">&larr; Library index</a>\n`
    : '';

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(options.title)}</title>

  <!-- Reveal.js core -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reset.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">

  <!-- Custom styles: the whole look of the deck lives in this file -->
  <link rel="stylesheet" href="${escapeHtml(options.stylesFile)}">

  <!-- ECharts for data visualization -->
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
</head>
<body>
  <div class="reveal">
    <div class="slides">
<!-- SLIDES:START -->${slidesContent}<!-- SLIDES:END -->
    </div>
${backLink}    <div class="section-bar is-hidden" aria-label="Progress"></div>
  </div>

  <!-- ENGINE: do not edit per deck. Slides are above; the look is in the CSS file. -->
  <script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
  <script>
    (function () {
      var css = function (name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); };
      var isExport = window.location.search.includes('export');
      if (isExport) document.documentElement.classList.add('is-export');

      /* Charts: <div class="chart" data-echart> holding an ECharts option as JSON.
         Fonts and colours come from the theme; "var(--name)" in the JSON resolves to the theme value. */
      function resolveVars(node, depth) {
        if (!node || typeof node !== 'object' || depth > 8) return;
        Object.keys(node).forEach(function (key) {
          var v = node[key];
          if (typeof v === 'string') {
            if (v.indexOf('var(--') === 0 && v.charAt(v.length - 1) === ')') node[key] = css(v.slice(4, -1)) || v;
          } else if (v && typeof v === 'object') {
            resolveVars(v, depth + 1);
          }
        });
      }
      function chartTheme() {
        var axis = {
          axisLine: { lineStyle: { color: css('--rule') } },
          axisTick: { show: false },
          axisLabel: { color: css('--muted'), fontSize: 15 },
          nameTextStyle: { color: css('--muted'), fontSize: 14 },
          splitLine: { lineStyle: { color: css('--chart-grid') } }
        };
        return {
          /* Series order from the Look: blue, green, navy, teal, orange, muted */
          color: [css('--blue'), css('--green'), css('--navy'), css('--teal'), css('--orange'), css('--muted')],
          textStyle: { fontFamily: css('--body-font'), color: css('--ink') },
          categoryAxis: Object.assign({}, axis, { splitLine: { show: false } }),
          valueAxis: Object.assign({}, axis, { axisLine: { show: false } }),
          legend: { bottom: 0, icon: 'rect', itemWidth: 14, itemHeight: 14, textStyle: { color: css('--ink'), fontSize: 15 } },
          bar: { itemStyle: { borderRadius: 0 }, barMaxWidth: 110, label: { color: css('--ink'), fontSize: 16, fontWeight: 600 } },
          line: { lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 8, label: { color: css('--ink'), fontSize: 15 }, endLabel: { fontSize: 15 } },
          scatter: { symbolSize: 16, itemStyle: { opacity: 1 }, label: { color: css('--ink'), fontSize: 15 } },
          markLine: { label: { fontSize: 14, color: css('--muted') } },
          pie: { label: { color: css('--ink'), fontSize: 15 }, itemStyle: { borderColor: css('--paper'), borderWidth: 2 } }
        };
      }
      function drawChart(box) {
        var src = box.querySelector('script[type="application/json"]');
        if (!window.echarts || !src) return;
        var option;
        try { option = JSON.parse(src.textContent); }
        catch (e) { box.insertAdjacentText('beforeend', 'Chart data is not valid JSON: ' + e.message); return; }
        resolveVars(option, 0);
        var yName = option.yAxis && !Array.isArray(option.yAxis) && option.yAxis.name && option.yAxis.show !== false;
        if (!option.grid) option.grid = { left: yName ? 46 : 8, right: 28, top: 30, bottom: option.legend ? 44 : 8, containLabel: true };
        /* Light hover: one small tooltip naming the item and its value. Nothing else reacts, so nothing
           flickers: the marks keep their look (no emphasis state) and the tooltip never takes the pointer. */
        var seriesList = [].concat(option.series || []);
        var valueAxis = [option.yAxis, option.xAxis].filter(function (a) { return a && !Array.isArray(a) && a.type === 'value'; })[0];
        var axisFormat = valueAxis && valueAxis.axisLabel && typeof valueAxis.axisLabel.formatter === 'string' ? valueAxis.axisLabel.formatter : null;
        function fill(template, p, v) {
          return template.split('{c}').join(v).split('{value}').join(v).split('{b}').join(p.name).split('{a}').join(p.seriesName || '').split('{@[0]}').join(v);
        }
        seriesList.forEach(function (s) {
          s.emphasis = { disabled: true };
          if (s.itemStyle && s.itemStyle.opacity === 0) s.silent = true;   /* hidden waterfall base */
          else delete s.silent;
        });
        function valueText(p) {
          var v = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value;
          if (v == null || v === '-') return null;
          var s = seriesList[p.seriesIndex] || {};
          var own = p.data && p.data.label && typeof p.data.label.formatter === 'string' ? p.data.label.formatter : null;
          var shared = s.label && typeof s.label.formatter === 'string' ? s.label.formatter : null;
          return own ? fill(own, p, v) : shared ? fill(shared, p, v) : axisFormat ? fill(axisFormat, p, v) : String(v);
        }
        function strong(text) { return '<span style="font-weight:600">' + text + '</span>'; }
        function isNamed(p) { return p.seriesName && p.seriesName.indexOf('series') !== 0; }
        /* Lines are read along the time axis (their points are usually hidden); everything else by item. */
        var byAxis = seriesList.length > 0 && seriesList.every(function (s) { return s.type === 'line'; }) &&
          option.xAxis && !Array.isArray(option.xAxis) && option.xAxis.type === 'category';
        option.tooltip = isExport ? { show: false } : {
          trigger: byAxis ? 'axis' : 'item', confine: true, transitionDuration: 0, showDelay: 0, hideDelay: 60, enterable: false,
          axisPointer: { type: 'line', animation: false, lineStyle: { color: css('--muted'), width: 1, type: 'solid' }, label: { show: false } },
          backgroundColor: css('--navy'), borderWidth: 0, padding: [7, 12],
          textStyle: { color: css('--paper'), fontSize: 14, fontFamily: css('--body-font') },
          extraCssText: 'pointer-events:none;border-radius:2px;box-shadow:none;',
          formatter: function (p) {
            if (Array.isArray(p)) {
              var rows = p.filter(function (q) { return valueText(q) != null; }).map(function (q) {
                return (isNamed(q) ? q.seriesName + ': ' : '') + strong(valueText(q));
              });
              return rows.length ? p[0].name + '<br>' + rows.join('<br>') : '';
            }
            if (p.componentType !== 'series' || valueText(p) == null) return '';
            var named = isNamed(p) && seriesList.length > 1 ? p.seriesName + ' \u00b7 ' : '';
            return named + (p.name ? p.name + ': ' : '') + strong(valueText(p));
          }
        };
        if (isExport) { option.animation = false; seriesList.forEach(function (s) { s.silent = true; }); }
        if (!box._chart) {
          var holder = document.createElement('div');
          holder.style.cssText = 'position:absolute;inset:0;';
          box.appendChild(holder);
          /* Canvas when live (hover never rebuilds the marks under the pointer); crisp SVG for export. */
          box._chart = echarts.init(holder, 'deck', isExport
            ? { renderer: 'svg', width: box.clientWidth, height: box.clientHeight }
            : { renderer: 'canvas', devicePixelRatio: Math.max(2, (window.devicePixelRatio || 1) * 2), width: box.clientWidth, height: box.clientHeight });
        } else {
          box._chart.clear();
          box._chart.resize({ width: box.clientWidth, height: box.clientHeight });
        }
        box._chart.setOption(option);
      }
      function drawCharts(slide) {
        if (!slide) return;
        Array.prototype.forEach.call(slide.querySelectorAll('.chart[data-echart]'), drawChart);
      }
      if (window.echarts) echarts.registerTheme('deck', chartTheme());

      Reveal.initialize({
        width: 1280,
        height: 720,
        margin: 0,
        controls: false,
        progress: false,
        slideNumber: false,
        hash: true,
        transition: isExport ? 'none' : 'slide',
        transitionSpeed: 'default',
        backgroundTransition: 'fade',
        center: false
      });

      /* Bottom section bar: built from data-section on the slides. A slide with no
         data-section continues the previous one; data-section="" ends the sections. */
      var bar = document.querySelector('.section-bar');
      var slides = [], sections = [], count;
      function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

      function buildBar() {
        slides = Reveal.getSlides();
        sections = [];
        var last = '';
        slides.forEach(function (s) {
          if (s.dataset.section !== undefined) last = s.dataset.section;
          s._sec = -1;
          if (!last) return;
          var top = sections[sections.length - 1];
          if (!top || top.name !== last) { top = { name: last, first: s, count: 0 }; sections.push(top); }
          top.count++; s._sec = sections.length - 1; s._pos = top.count;
        });
        bar.innerHTML = '';
        bar.appendChild(el('div', 'bar-title', document.title));
        var list = el('div', 'bar-list');
        sections.forEach(function (sec) {
          var li = el('div', 'bar-item'); li.title = sec.name;
          li.appendChild(el('span', 'bar-name', sec.name));
          var track = el('span', 'bar-track'); sec.fill = el('i'); track.appendChild(sec.fill); li.appendChild(track);
          li.addEventListener('click', function () { var i = Reveal.getIndices(sec.first); Reveal.slide(i.h, i.v); });
          list.appendChild(li); sec.li = li;
        });
        bar.appendChild(list);
        count = el('div', 'bar-count');
        bar.appendChild(count);
      }

      function updateBar() {
        var cur = Reveal.getCurrentSlide();
        if (!cur || !count) return;
        sections.forEach(function (sec, k) {
          var pct = k < cur._sec ? 100 : k === cur._sec ? Math.round(100 * cur._pos / sec.count) : 0;
          sec.fill.style.width = pct + '%';
          sec.li.classList.toggle('is-current', k === cur._sec);
          sec.li.classList.toggle('is-done', cur._sec > k);
        });
        count.textContent = (slides.indexOf(cur) + 1) + ' / ' + slides.length;
        bar.classList.toggle('is-hidden', cur._sec === -1 || cur.dataset.bar === 'hide' || !sections.length);
      }

      /* Keep the bar on the bottom edge of the slide, whatever the window shape. */
      function placeBar() {
        var s = Reveal.getScale(), box = document.querySelector('.reveal');
        bar.style.setProperty('--deck-scale', s);
        bar.style.width = (1280 * s) + 'px';
        bar.style.left = Math.max(0, (box.offsetWidth - 1280 * s) / 2) + 'px';
        bar.style.bottom = Math.max(0, (box.offsetHeight - 720 * s) / 2) + 'px';
      }

      Reveal.on('ready', function () {
        placeBar(); buildBar(); updateBar();
        if (document.documentElement.classList.contains('print-pdf') || document.documentElement.classList.contains('reveal-print')) {
          Reveal.getSlides().forEach(drawCharts);
        } else {
          drawCharts(Reveal.getCurrentSlide());
        }
      });
      Reveal.on('slidechanged', function (e) { updateBar(); drawCharts(e.currentSlide); });
      Reveal.on('resize', placeBar);
    })();
  </script>
</body>
</html>
`;
}

function copyIfMissing(from, to, label, transform) {
  if (fs.existsSync(to)) {
    console.log(`${to} already exists, skipping`);
    return;
  }
  if (!fs.existsSync(from)) {
    console.warn(`Warning: Could not find ${from}; create ${to} by hand.`);
    return;
  }
  const text = fs.readFileSync(from, 'utf8');
  fs.writeFileSync(to, transform ? transform(text) : text);
  console.log(`Copied ${label} to ${to}`);
}

function refresh(options) {
  const file = options.refresh;
  if (!fs.existsSync(file)) { console.error(`Error: ${file} not found.`); process.exit(1); }
  const html = fs.readFileSync(file, 'utf8');
  const start = html.indexOf('<!-- SLIDES:START -->');
  const end = html.indexOf('<!-- SLIDES:END -->');
  if (start === -1 || end === -1) { console.error('Error: no SLIDES:START / SLIDES:END markers; not a deck made by this script.'); process.exit(1); }
  const unescape = t => t.replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  const title = (html.match(/<title>([\s\S]*?)<\/title>/) || [])[1];
  const styles = (html.match(/<link rel="stylesheet" href="(?!https?:)([^"]+)">/) || [])[1];
  const back = (html.match(/class="library-back" href="([^"]+)"/) || [])[1];
  const opts = Object.assign({}, options, {
    title: options.titleSet ? options.title : (title ? unescape(title) : options.title),
    stylesFile: options.stylesSet ? options.stylesFile : (styles ? unescape(styles) : options.stylesFile),
    back: options.back !== undefined ? options.back : (back ? unescape(back) : undefined),
    slidesHtml: html.slice(start + '<!-- SLIDES:START -->'.length, end),
  });
  fs.writeFileSync(file, generateHTML(opts));
  console.log(`Refreshed the engine of ${file}; slides kept.`);
}

function main() {
  const args = process.argv.slice(2);
  const options = parseArgs(args);
  if (options.refresh) { refresh(options); return; }

  if (options.slides !== null && options.structure !== null) {
    console.error('Error: Cannot use both --slides and --structure. Choose one.');
    process.exit(1);
  }

  if (options.slides === null && options.structure === null) {
    options.structure = null;
  } else if (options.slides !== null) {
    if (options.slides < 1 || isNaN(options.slides)) {
      console.error('Error: Slide count must be at least 1.');
      process.exit(1);
    }
    options.structure = Array(options.slides).fill(1);
  } else {
    if (options.structure.some(n => n !== 'd' && (n < 1 || isNaN(n)))) {
      console.error('Error: Structure values must be positive integers or "d" for dividers.');
      process.exit(1);
    }
  }

  const totalSlides = options.structure ? options.structure.reduce((a, b) => a + (b === 'd' ? 1 : b), 0) : 0;
  const outputDir = path.dirname(options.output);

  if (outputDir && outputDir !== '.') {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  if (options.planOnly) {
    copyIfMissing(PLAN_TEMPLATE_PATH, path.join(outputDir, 'plan.md'), 'plan-template.md', text =>
      text.replace('{{TITLE}}', options.title).replace('{{DATE}}', new Date().toISOString().slice(0, 10)));
    console.log('Plan only. Run again without --plan-only after the storyboard is approved.');
    return;
  }

  if (fs.existsSync(options.output)) {
    console.error(`Error: ${options.output} already exists. Edit it, or choose another output path.`);
    process.exit(1);
  }

  fs.writeFileSync(options.output, generateHTML(options));
  console.log(`Created ${options.output}`);

  copyIfMissing(BASE_STYLES_PATH, path.join(outputDir, options.stylesFile), 'base-styles.css');

  console.log(options.structure ? `\nPresentation created with ${totalSlides} slides (structure: ${options.structure.join(',')}).`
    : '\nPresentation created. Read it down to SLIDES:END, then fill the BRIEF and every slide in one Edit.');
  console.log(`The look is in ${path.join(outputDir, options.stylesFile)}.`);
}

main();
