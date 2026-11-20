/* host-runtime.js: draws copied design-library items (AUTHORING.md, "What the host page provides"). Copy verbatim, after
   ECharts, the theme tokens and host.css. ItemHost.draw() redraws; ItemHost.prepare(option, box) readies an option. */
(function () {
  var root = document.documentElement;
  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function series() { return css('--series').split(/\s+/).filter(Boolean).map(css); }
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
      line: { lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 8, label: { color: css('--ink'), fontSize: 15 }, endLabel: { fontSize: 15, color: css('--ink'), textBorderWidth: 0 } },
      scatter: { symbolSize: 16, itemStyle: { opacity: 1 }, label: { color: css('--ink'), fontSize: 15 } },
      markLine: { label: { fontSize: 14, color: css('--muted') } },
      pie: { label: { color: css('--ink'), fontSize: 15 }, itemStyle: { borderColor: css('--paper'), borderWidth: 2 } }
    };
  }
  /* Number formats in formatter strings: {value:short} or {c:short} gives 7M, 1.2K; {value:comma} or {c:comma} gives 7,000,000. */
  function short(v) {
    if (typeof v !== 'number') return v;
    var a = Math.abs(v), u = a >= 1e9 ? ['B', 1e9] : a >= 1e6 ? ['M', 1e6] : a >= 1e3 ? ['K', 1e3] : ['', 1], n = v / u[1];
    return n.toLocaleString('en-US', { maximumFractionDigits: u[1] === 1 ? 2 : Math.abs(n) < 10 ? 1 : 0 }) + u[0];
  }
  function comma(v) { return typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : v; }
  var CODED = /\{(?:c|value):(?:short|comma)\}/;
  function fmt(t, p, v) {
    return String(t).replace(/\{(?:c|value):short\}/g, function () { return short(v); }).replace(/\{(?:c|value):comma\}/g, function () { return comma(v); })
      .split('{c}').join(v).split('{value}').join(v).split('{b}').join(p.name || '').split('{a}').join(p.seriesName || '')
      .replace(/\{@\[(\d+)\]\}/g, function (m, i) { return Array.isArray(p.value) ? p.value[+i] : v; });
  }
  function tplOf(x) { return x ? (x._tpl || (typeof x.formatter === 'string' ? x.formatter : null)) : null; }
  /* formatter strings with a number format become functions; the string stays in _tpl for the tooltip */
  function formats(o) {
    Object.keys(o).forEach(function (k) {
      var v = o[k];
      if (k === 'animationDelay' && typeof v === 'string' && /^index\*\d+$/.test(v)) { var ms = +v.split('*')[1]; o[k] = function (i) { return i * ms; }; }   /* bars land one by one */
      else if (k === 'formatter' && typeof v === 'string' && CODED.test(v)) {
        o._tpl = v;
        o[k] = function (x) { var p = x && typeof x === 'object' ? x : { value: x }, n = Array.isArray(p.value) ? p.value[p.value.length - 1] : p.value; return fmt(v, p, n); };
      } else if (v && typeof v === 'object') formats(v);
    });
  }
  /* Hover: a one-line tooltip and a light emphasis; nothing moves. Off with data-hover="off" (chart or body),
     "tooltip": {"show": false}, or when exported (html.is-export). An item may give its own tooltip.formatter. */
  function hoverOff(box) { return root.classList.contains('is-export') || document.body.getAttribute('data-hover') === 'off' || !!(box && box.getAttribute('data-hover') === 'off'); }
  function hover(o) {
    var list = [].concat(o.series || []);
    var cat = [].concat(o.xAxis || [], o.yAxis || []).some(function (a) { return a && a.type === 'category'; });
    var valAxis = [].concat(o.yAxis || [], o.xAxis || []).filter(function (a) { return a && a.type === 'value'; });
    var axisFmt = function (i) { var a = valAxis[i || 0] || valAxis[0]; return a ? tplOf(a.axisLabel) : null; };
    var lines = list.some(function (x) { return x.type === 'line'; });
    var axis = cat && list.every(function (x) { return x.type === 'line' || x.type === 'bar' || x.type === 'scatter'; });
    function hidden(x) { return !x || (x.itemStyle && x.itemStyle.opacity === 0) || x.silent === true || /^_/.test(x.name || ''); }
    function value(p) {
      var x = list[p.seriesIndex] || {}, v = p.value;
      if (Array.isArray(v)) v = x.type === 'scatter' || x.type === 'effectScatter' ? v[v.length > 2 ? 2 : 1] : v[v.length - 1];
      if (v == null || v === '-') return null;
      var t = tplOf(p.data && p.data.label) || tplOf(x.label) || axisFmt(x.yAxisIndex || x.xAxisIndex);
      return t ? fmt(t, p, v) : comma(v);
    }
    /* the series name goes in front once, never when the value text already carries it */
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
        return (named(p) ? p.seriesName + ' · ' : '') + (p.name ? p.name + ': ' : '') + '<b>' + value(p) + '</b>';
      }
    };
    o.tooltip = Object.assign(tip, o.tooltip && typeof o.tooltip === 'object' ? o.tooltip : {});
    list.forEach(function (x) {
      if (x.emphasis && !x.emphasis.disabled) return;
      var w = x.lineStyle && x.lineStyle.width || 3;
      x.emphasis = x.type === 'line' ? { focus: 'none', scale: false, lineStyle: { width: w }, label: { show: x.label && x.label.show } }
        : { focus: 'none', scale: false, itemStyle: { borderColor: css('--navy'), borderWidth: 1.5 } };
      if (hidden(x)) x.emphasis = { disabled: true };
    });
  }
  /* Line end labels: no halo, wrapped to the room grid.right leaves (spaceEnds pushes close ones apart after drawing). */
  function endLabels(o) {
    var right = o.grid && !Array.isArray(o.grid) && typeof o.grid.right === 'number' ? o.grid.right : 0;
    [].concat(o.series || []).forEach(function (s) {
      if (!s || s.type !== 'line') return;
      var e = s.endLabel;
      if (e && e.show) {
        if (e.textBorderWidth == null) e.textBorderWidth = 0;
        if (right > 40 && e.width == null) { e.width = right - 12; if (e.overflow == null) e.overflow = 'break'; }
      }
    });
  }
  /* Series labels show a number: the numeric part of a point (a [value, "name"] point prints its value, not its name),
     formatted (7,000 with no format given). */
  function seriesLabels(o) {
    var xs = [].concat(o.xAxis || [])[0] || {}, ys = [].concat(o.yAxis || [])[0] || {}, at = xs.type === 'value' && ys.type === 'category' ? 0 : 1;
    [].concat(o.series || []).forEach(function (s) {
      if (!s || s.type === 'pie' || s.type === 'heatmap') return;
      ['label', 'endLabel'].forEach(function (k) {
        var l = s[k];
        if (!l || typeof l.formatter === 'function') return;
        var t = typeof l.formatter === 'string' ? l.formatter : (l.show && k === 'label' ? '{c:comma}' : null);
        if (!t || !/\{c[:}]/.test(t)) return;
        t = t.replace(/\{c\}/g, '{c:comma}');   /* a bare {c} prints 1,844.84, never 1844.8360103943749 */
        l._tpl = t;
        l.formatter = function (p) { var v = p.value; if (Array.isArray(v)) v = typeof v[at] === 'number' ? v[at] : v.filter(function (x) { return typeof x === 'number'; }).pop(); return fmt(t, p, v); };
      });
    });
  }
  function prepare(o, box) {
    resolve(o);
    var y = o.yAxis && !Array.isArray(o.yAxis) && o.yAxis.name && o.yAxis.show !== false;
    if (!o.grid) o.grid = { left: y ? 46 : 8, right: 28, top: 30, bottom: o.legend ? 44 : 8, containLabel: true };
    endLabels(o);
    if (hoverOff(box) || (o.tooltip && o.tooltip.show === false)) { o.tooltip = { show: false }; [].concat(o.series || []).forEach(function (s) { s.emphasis = { disabled: true }; }); }
    else hover(o);
    seriesLabels(o);
    formats(o);
    o.animation = false;
    return o;
  }
  function tableTips() {
    Array.prototype.forEach.call(document.querySelectorAll('.lib-table tbody tr'), function (tr) {
      var table = tr.closest('table'), heads = table ? Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) { return th.innerText.trim(); }) : [];
      var row = tr.cells[0] ? tr.cells[0].innerText.trim() : '';
      Array.prototype.forEach.call(tr.cells, function (td, i) { if (i && !td.title && td.innerText.trim()) td.title = row + (heads[i] ? ' · ' + heads[i] : '') + ': ' + td.innerText.trim(); });
    });
  }
  /* Labels of several lines at the same end (a slope chart's two ends, end labels) are pushed apart vertically. */
  function spaceEnds(c, o) {
    var lines = [].concat(o.series || []).map(function (s, i) { return { s: s, i: i }; }).filter(function (x) { return x.s.type === 'line' && Array.isArray(x.s.data) && x.s.data.length; });
    var val = function (d) { return d && typeof d === 'object' && !Array.isArray(d) ? d.value : d; };
    function spread(ls, apply) {
      if (ls.length < 2) return false;
      ls.sort(function (a, b) { return a.y - b.y; });
      ls.forEach(function (x, k) { x.to = k ? Math.max(x.y, ls[k - 1].to + 18) : x.y; });
      var moved = false;
      ls.forEach(function (x) { if (x.to !== x.y) { moved = true; apply(x, x.to - x.y); } });
      return moved;
    }
    var starts = lines.filter(function (x) { var d = x.s.data[0]; return d != null && ((d.label && d.label.show) || (x.s.label && x.s.label.show)); })
      .map(function (x) { x = { s: x.s, i: x.i }; x.y = (c.convertToPixel({ seriesIndex: x.i }, [0, val(x.s.data[0])]) || [0, 0])[1]; return x; });
    var ends = lines.filter(function (x) { return x.s.endLabel && x.s.endLabel.show; }).map(function (x) {
      var k = x.s.data.length - 1; while (k > 0 && val(x.s.data[k]) == null) k--;
      x = { s: x.s, i: x.i }; x.y = (c.convertToPixel({ seriesIndex: x.i }, [k, val(x.s.data[k])]) || [0, 0])[1]; return x;
    });
    var a = spread(starts, function (x, dy) { var d = x.s.data[0], p = d && typeof d === 'object' && !Array.isArray(d) ? d : { value: d }; p.label = Object.assign({}, x.s.label || {}, p.label || {}, { offset: [0, dy] }); x.s.data[0] = p; });
    var b = spread(ends, function (x, dy) { x.s.endLabel = Object.assign({}, x.s.endLabel, { offset: [0, dy] }); });
    if (a || b) c.setOption({ series: o.series });
  }
  /* animate(box), when given, says which charts draw in (the library's own engine uses it) */
  var drawn = 0;
  function draw(animate) {
    if (!window.echarts) return;
    var name = 'item' + (++drawn);
    echarts.registerTheme(name, theme());
    Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (box) {
      var src = box.querySelector('script[type="application/json"]');
      if (!src) return;
      var o = prepare(JSON.parse(src.textContent), box);
      var anim = !!(animate && animate(box));
      o.animation = anim;
      if (anim) { o.animationDuration = o.animationDuration || 900; o.animationEasing = o.animationEasing || 'cubicOut'; }
      if (box._chart) box._chart.dispose();
      if (!box._holder) { box._holder = document.createElement('div'); box._holder.style.cssText = 'position:absolute;inset:0;'; box.appendChild(box._holder); }
      box._chart = echarts.init(box._holder, name, { renderer: 'svg' });
      box._chart.setOption(o);
      spaceEnds(box._chart, o);
      if (anim) { box._holder.style.pointerEvents = 'none'; clearTimeout(box._still); box._still = setTimeout(function () { box._holder.style.pointerEvents = ''; }, (o.animationDuration || 900) + 300); }
    });
    window.dispatchEvent(new Event('item:draw'));
  }
  function chart(el) { var box = el && el.closest ? (el.closest('.chart[data-echart]') || (el.querySelector && el.querySelector('.chart[data-echart]'))) : document.querySelector('.chart[data-echart]'); return (box && box._chart) || null; }
  window.ItemHost = { css: css, theme: theme, prepare: prepare, draw: draw, chart: chart, tableTips: tableTips };
  if (window.ItemEngineInside) return;   /* inside a library item its engine drives drawing and motion */
  window.ItemEngine = { motion: function () { return false; }, play: function () {}, force: function () {}, chart: chart, redraw: function () { draw(); } };
  window.itemRedraw = window.ItemEngine.redraw;
  function start() { tableTips(); draw(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  var t = null;
  window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(function () { Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (b) { if (b._chart) b._chart.resize(); }); }, 100); });
  window.addEventListener('beforeprint', function () { Array.prototype.forEach.call(document.querySelectorAll('.chart[data-echart]'), function (b) { if (b._chart) b._chart.dispatchAction({ type: 'hideTip' }); }); });
})();
