// A design-library item copied into a section: a chart (ECharts option) or a block of HTML (table, hero cards).
// At every draw (data or filter change) the section's rows go into the copy's slots (Src/Lib/fill.js); the rest
// of the copy is drawn as written. The page's host-runtime.js (loaded once by App.jsx) resolves the theme
// tokens, adds the hover tooltip and the number formats, so the item looks as it does in the library.
// After drawing, text that runs past the chart's edge or sits on other text is noted on the section
// (data-faults); npm run shot prints it.
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import {
  BarChart, BoxplotChart, CustomChart, EffectScatterChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart,
  RadarChart, SankeyChart, ScatterChart, TreemapChart,
} from 'echarts/charts';
import {
  AxisPointerComponent, DataZoomComponent, DatasetComponent, GraphicComponent, GridComponent, LegendComponent,
  MarkAreaComponent, MarkLineComponent, MarkPointComponent, PolarComponent, TitleComponent, TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import { SVGRenderer } from 'echarts/renderers';
import { codeFormats, fillChart, fillHtml } from '../Lib/fill.js';
import { renderTemplate } from '../Lib/format.js';
import { currentTheme } from '../Lib/theme.js';

echarts.use([
  BarChart, BoxplotChart, CustomChart, EffectScatterChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart,
  RadarChart, SankeyChart, ScatterChart, TreemapChart,
  AxisPointerComponent, DataZoomComponent, DatasetComponent, GraphicComponent, GridComponent, LegendComponent,
  MarkAreaComponent, MarkLineComponent, MarkPointComponent, PolarComponent, TitleComponent, TooltipComponent,
  VisualMapComponent, LabelLayout, SVGRenderer,
]);

const text = (t, metrics) => renderTemplate(String(t ?? ''), metrics ?? {}).segments.map((s) => s.text).join('');

/** Every category label shows: all of them, wrapped to the room each has, turned when they still do not fit.
 *  Only on axes whose labels the section has not set itself (axisLabel.interval, width or rotate). */
function fitCategories(o, width) {
  const axes = (k) => [].concat(o[k] ?? []).filter((a) => a && typeof a === 'object' && a.type === 'category' && Array.isArray(a.data));
  for (const a of axes('xAxis')) {
    const l = a.axisLabel ?? {};
    if (l.interval !== undefined || l.width !== undefined || l.rotate !== undefined || !a.data.length) continue;
    const room = Math.max(30, (width - 90) / a.data.length - 8);
    const longest = Math.max(...a.data.map((d) => String(d && typeof d === 'object' ? d.value : d).length)) * 8;
    a.axisLabel = { ...l, interval: 0, hideOverlap: false };
    if (longest > room * 3) Object.assign(a.axisLabel, { rotate: 35 });
    else if (longest > room) Object.assign(a.axisLabel, { width: room, overflow: 'break', lineHeight: 18 });
  }
  for (const a of axes('yAxis')) if (a.axisLabel?.interval === undefined) a.axisLabel = { ...(a.axisLabel ?? {}), interval: 0 };
}

const categoriesOf = (o) => ['xAxis', 'yAxis'].flatMap((k) => [].concat(o[k] ?? []))
  .filter((a) => a && a.type === 'category' && a.show !== false && a.axisLabel?.show !== false && Array.isArray(a.data))
  .flatMap((a) => a.data.map((d) => String(d && typeof d === 'object' ? d.value : d)));

/** Texts in the drawn chart that leave the chart's box or overlap each other, and category labels not drawn. */
function drawingFaults(box, categories = []) {
  const edge = box.getBoundingClientRect();
  const texts = [...box.querySelectorAll('svg text')]
    .map((el) => ({ t: el.textContent.trim(), r: el.getBoundingClientRect(), turned: /matrix\((?!1[ ,]+0[ ,]+0[ ,]+1[ ,])/.test(el.getAttribute('transform') ?? '') }))
    .filter((x) => x.t && x.r.width > 0);
  const out = [];
  for (const { t, r } of texts) {
    if (r.left < edge.left - 2 || r.right > edge.right + 2 || r.top < edge.top - 2 || r.bottom > edge.bottom + 2) out.push(`"${t.slice(0, 40)}" is cut off at the chart's edge`);
  }
  for (let i = 0; i < texts.length; i++) {
    for (let j = i + 1; j < texts.length; j++) {
      if (texts[i].turned || texts[j].turned) continue;   // turned labels: their boxes overlap, the words do not
      const a = texts[i].r;
      const b = texts[j].r;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > 3 && h > 0.5 * Math.min(a.height, b.height)) out.push(`"${texts[i].t.slice(0, 30)}" overlaps "${texts[j].t.slice(0, 30)}"`);
    }
  }
  const bigPct = texts.find((x) => /(\d{1,3}(,\d{3})+|\d{4,})(\.\d+)?%/.test(x.t));
  if (bigPct) out.unshift(`"${bigPct.t.slice(0, 30)}": a percent label on a large number; the label's format does not suit the values`);
  const all = texts.map((x) => x.t).join('').replace(/\s+/g, '');
  const hidden = categories.filter((c) => c && !all.includes(c.replace(/\s+/g, '')));
  if (hidden.length) out.unshift(`${hidden.length} of ${categories.length} category labels are not shown (e.g. "${hidden[0].slice(0, 30)}")`);
  return [...new Set(out)].slice(0, 8);
}

function note(el, problems) {
  const section = el?.closest('section.section');
  if (!section) return;
  if (problems.length) section.dataset.faults = problems.join(' | ');
  else delete section.dataset.faults;
}

/**
 * use: the library id it was copied from (CT-34 ...), or own-chart / own-html.
 * chart: ECharts option with "slot" marks; html: the item's HTML block; css, script: its own styles and script.
 * rows: the section's data rows; slots, names, format: the wiring (Src/Lib/fill.js); metrics: for {metric|format} in basis and html.
 * keyHtml: a hand-written legend under the chart; basis: the line under it; height: the chart's height in px.
 */
export default function Item({ use, chart, html, css, script, rows, slots, names, format, metrics, keyHtml, basis, height }) {
  const wiring = useMemo(() => ({ slots, names, format }), [slots, names, format]);
  const todo = Object.entries(slots ?? {}).filter(([, v]) => v === null).map(([k]) => k);   // MANUAL: not filled yet
  const box = useRef(null);
  const wrap = useRef(null);
  const instance = useRef(null);
  const missing = !Array.isArray(rows);

  useLayoutEffect(() => {
    if (!chart || missing) return undefined;
    const el = box.current;
    const theme = `item-${currentTheme()?.name ?? 'page'}`;
    echarts.registerTheme(theme, window.ItemHost.theme());
    const c = echarts.init(el, theme, { renderer: 'svg' });
    el._chart = c;   // ItemEngine.chart(el), for item scripts
    instance.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      c.dispose();
      instance.current = null;
    };
  }, [chart, missing, currentTheme()?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    const c = instance.current;
    if (!c || !chart || missing) return;
    const option = typeof chart === 'function' ? chart(rows, metrics) : JSON.parse(JSON.stringify(chart));
    const problems = fillChart(option, rows, wiring);
    fitCategories(option, box.current.clientWidth);
    const categories = categoriesOf(option);
    codeFormats(window.ItemHost.prepare(option, box.current));
    c.setOption(option, { notMerge: true });
    const check = () => note(box.current, [...problems, ...drawingFaults(box.current, categories)]);
    c.off('finished');
    c.on('finished', check);
    check();
  }, [chart, rows, wiring, metrics, missing]);

  const filled = useMemo(() => (html && !missing ? fillHtml(html, rows, wiring, (t) => text(t, metrics)) : null), [html, rows, wiring, metrics, missing]);

  useEffect(() => {
    if (!filled) return;
    note(wrap.current, filled.problems);
    window.ItemHost?.tableTips();
    if (script) {
      try {
        new Function(script)();   // eslint-disable-line no-new-func -- the item's own script, copied with it
      } catch (e) {
        console.warn(`${use}: its script failed: ${e.message}`);
      }
    }
  }, [filled, script, use]);

  if (missing) return <div className="section-error">This section's data has no rows (its analytic must return data: {'{'} rows: [...] {'}'}).</div>;
  const style = height ? { '--chart-height': `${height}px` } : undefined;
  return (
    <div data-item={use} style={style} ref={wrap}>
      {css && <style>{css}</style>}
      {chart && <div className="chart" data-echart="" ref={box} />}
      {chart && keyHtml && <div className="key" dangerouslySetInnerHTML={{ __html: keyHtml }} />}
      {filled && <div className="item-html" dangerouslySetInnerHTML={{ __html: filled.html }} />}
      {basis && <p className="basis">{text(basis, metrics)}</p>}
      {todo.length > 0 && <p className="item-todo">Not filled yet: {todo.join(', ')}. This part shows the library's sample data until it is set in the section file.</p>}
    </div>
  );
}
