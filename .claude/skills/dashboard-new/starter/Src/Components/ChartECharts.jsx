// Thin ECharts wrapper. Modular imports keep bundles small:
// add a chart type or component to the lists below only when a section needs it.
import { useEffect, useLayoutEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from 'echarts/charts';
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent,
} from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';
import { currentTheme } from '../Lib/theme.js';

// Minimal common set. Other types (sankey, radar, gauge, sunburst, boxplot, markPoint/markArea ...) are added
// here when a section needs them.
echarts.use([
  BarChart, HeatmapChart, LineChart, PieChart, ScatterChart,
  DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent,
  SVGRenderer,
]);

/** option: ECharts option (memoize it). onEvents: optional { click: (params) => ... } (memoize it too). */
export default function ChartECharts({ option, height = 320, onEvents }) {
  const box = useRef(null);
  const chart = useRef(null);

  useLayoutEffect(() => {
    const host = box.current;
    chart.current = echarts.init(host, currentTheme()?.name, { renderer: 'svg' });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(host);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useLayoutEffect(() => {
    chart.current?.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    const c = chart.current;
    if (!c || !onEvents) return undefined;
    const entries = Object.entries(onEvents);
    for (const [name, fn] of entries) c.on(name, fn);
    return () => entries.forEach(([name, fn]) => c.off(name, fn));
  }, [onEvents]);

  return <div ref={box} className="chart" style={{ height, width: '100%' }} />;
}
