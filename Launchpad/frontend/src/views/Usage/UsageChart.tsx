/* The stacked bar chart (ECharts, SVG renderer, only the parts used). It is created once the box has a width (the view
   stays mounted while hidden, and a hidden box has none) and resized by a ResizeObserver on its box, so it follows the
   window and the sidebar opening or collapsing. The data and measure arrive as props; switching the measure only redraws. */
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import type { UsageBucket, UsageDataEvent, UsageMeasure, UsageSplit } from '../../contract';
import { buildOption, MEASURE_LABEL, type ChartTheme } from '../../lib/usageChart';
import { REDUCED } from '../../lib/format';

echarts.use([BarChart, GridComponent, TooltipComponent, SVGRenderer]);

function theme(): ChartTheme {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, d: string) => cs.getPropertyValue(n).trim() || d;
  return { ink: v('--ink', '#22243A'), muted: v('--muted', '#5E6278'), line: v('--line', '#E4E3F3'), card: v('--card', '#FFFFFF') };
}

export default function UsageChart({ data, measure, bucket, split, label }: {
  data: Pick<UsageDataEvent, 'buckets' | 'series'>; measure: UsageMeasure; bucket: UsageBucket; split: UsageSplit; label: string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const opt = useRef<ReturnType<typeof buildOption> | null>(null);

  useEffect(() => {
    opt.current = buildOption(data, measure, bucket, split, theme(), !REDUCED);
    const el = box.current;
    if (!el) return;
    if (!chart.current && el.clientWidth > 0) chart.current = echarts.init(el, undefined, { renderer: 'svg' });
    chart.current?.setOption(opt.current, true);
  }, [data, measure, bucket, split]);

  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth <= 0) return;
      if (!chart.current) { chart.current = echarts.init(el, undefined, { renderer: 'svg' }); if (opt.current) chart.current.setOption(opt.current, true); }
      else chart.current.resize();
    });
    ro.observe(el);
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);

  return <div ref={box} className="us-chart" role="img" aria-label={`${label}. ${MEASURE_LABEL[measure]} per ${bucket}, stacked by ${split}.`} />;
}
