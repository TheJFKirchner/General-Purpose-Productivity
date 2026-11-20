// EXAMPLE section (ECharts line with area fill; colors from fx(), never hex). Replace with real sections.
import { useMemo } from 'react';
import ChartECharts from '../Components/ChartECharts.jsx';
import { FORMATS } from '../Lib/format.js';
import { fx } from '../Lib/theme.js';

// Numbers come from its analytic in Analysis/example.py (revenue_trend): data = { months, revenue }, metrics for the note.
// commentary: the id of its commentary.json item (optional; nothing shows when the file or the id is missing).
export const meta = {
  id: 's2_revenue_trend',
  title: 'Monthly revenue',
  description: 'Revenue by month over two years, as a line',
  tab: 'overview',
  library: 'echarts',
  commentary: 'C1',
};

// Text above the section. Numbers only as live references {metric|format}.
export const note = `
Revenue in {latest_month|name} was {latest_revenue|compact}, which {yoy_change|direction} {yoy_change|pct:1} versus the same month a year earlier.
`;

export default function Section({ data }) {
  const option = useMemo(() => {
    const f = fx();
    const c0 = f.color(0);
    return {
      tooltip: { trigger: 'axis', valueFormatter: (v) => FORMATS.compact(v) },
      grid: { left: 64, right: 24, top: 16, bottom: 32 },
      xAxis: { type: 'category', data: data.months, boundaryGap: false },
      yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v) => FORMATS.compact(v) } },
      series: [{ name: 'Revenue', type: 'line', data: data.revenue, color: c0, lineStyle: { width: 2 }, areaStyle: { color: f.area(c0) } }],
    };
  }, [data]);

  return <ChartECharts option={option} height={320} />;
}
