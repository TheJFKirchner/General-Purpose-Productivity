/* The usage chart, in two forms of one design: smooth stacked areas or stacked bars (ECharts, SVG renderer, only the parts used). It is created once the box has a
   width (the view stays mounted while hidden, and a hidden box has none) and resized by a ResizeObserver on its box, so it
   follows the window, the sidebar and the right-hand panel opening or closing. Data, measure and the hidden series arrive
   as props. Motion: a one-time draw-in when the chart first appears; after that a quick morph when the buckets stay the
   same (measure, legend, a push), one quick transition when Line / Bar changes, and no animation when the buckets change
   (period, bucket, session), so controls feel instant. Hover never redraws: the tooltip and the hover band come from ECharts'
   axis pointer, and the tooltip is placed beside the hovered bucket using pixelOf (below). */
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import type { UsageBucket, UsageDataEvent, UsageMeasure, UsageSplit } from '../../contract';
import { buildOption, MEASURE_LABEL, type ChartMotion, type ChartTheme, type ChartType } from '../../lib/usageChart';
import { REDUCED } from '../../lib/format';

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, SVGRenderer]);

function theme(): ChartTheme {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, d: string) => cs.getPropertyValue(n).trim() || d;
  return {
    ink: v('--ink', '#22243A'), muted: v('--muted', '#5E6278'), line: v('--line', '#E4E3F3'), line2: v('--line2', '#D9D8EC'), card: v('--card', '#FFFFFF'),
    font: v('--body', 'Inter, system-ui, sans-serif'), shadow: v('--shadow-lg', ''), radius: v('--r-md', '12px'),
  };
}

type Props = { data: Pick<UsageDataEvent, 'buckets' | 'series'>; measure: UsageMeasure; bucket: UsageBucket; split: UsageSplit; label: string; hidden: readonly string[]; type: ChartType };

export default function UsageChart({ data, measure, bucket, split, label, hidden, type }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const props = useRef<Props | null>(null);
  const drawnKeys = useRef<string | null>(null);         // the bucket keys last drawn on this chart (null = nothing drawn yet)
  const drawnType = useRef<ChartType | null>(null);
  /* the x pixel of bucket i on the drawn chart (for the tooltip's place beside the bucket) */
  const pixelOf = (i: number): number | null => {
    const c = chart.current, k = props.current?.data.buckets[i]?.key;
    if (!c || k == null) return null;
    try { const v = c.convertToPixel({ xAxisIndex: 0 }, k); return typeof v === 'number' ? v : Array.isArray(v) ? v[0] : null; } catch { return null; }
  };

  const draw = () => {
    const p = props.current, c = chart.current;
    if (!p || !c) return;
    const keys = `${p.bucket}|${p.data.buckets.map(b => b.key).join(',')}`;
    const motion: ChartMotion = REDUCED ? 'none' : drawnKeys.current == null ? 'intro' : drawnType.current !== p.type ? 'switch' : drawnKeys.current === keys ? 'update' : 'none';
    const opt = buildOption(p.data, p.measure, p.bucket, p.split, theme(), { motion, hidden: p.hidden, type: p.type, reduced: REDUCED, pixelOf });
    if (motion === 'update') c.setOption(opt, { replaceMerge: ['series'] });
    else c.setOption(opt, true);
    drawnKeys.current = keys; drawnType.current = p.type;
  };
  const ensure = (el: HTMLDivElement) => {
    if (!chart.current && el.clientWidth > 0) { chart.current = echarts.init(el, undefined, { renderer: 'svg' }); drawnKeys.current = null; drawnType.current = null; }
    return chart.current;
  };

  useEffect(() => {
    props.current = { data, measure, bucket, split, label, hidden, type };
    const el = box.current;
    if (el && ensure(el)) draw();
  }, [data, measure, bucket, split, hidden, type]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth <= 0) return;
      if (!chart.current) { if (ensure(el)) draw(); }
      else chart.current.resize();
    });
    ro.observe(el);
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={box} className="us-chart" role="img" aria-label={`${label}. ${MEASURE_LABEL[measure]} per ${bucket}, ${type === 'bar' ? 'stacked bars' : 'stacked areas'} by ${split}.`} />;
}
