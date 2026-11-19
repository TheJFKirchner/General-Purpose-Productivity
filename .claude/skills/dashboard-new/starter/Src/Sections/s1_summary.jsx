// EXAMPLE section (KPI tile with sparkline, no chart of its own). Replace with real sections.
// Numbers come from its analytic in Analysis/example.py (summary): data = sparkline, metrics = tile value + note.
import KpiTile from '../Components/KpiTile.jsx';
import { FORMATS } from '../Lib/format.js';

export const meta = {
  id: 's1_summary',
  title: 'Summary',
  description: 'Trailing twelve months revenue with change and sparkline',
  tab: 'overview',
  library: 'none',
};

// Text above the section. Numbers only as live references {metric|format}.
export const note = `
Revenue over the trailing year through {latest_month|name} was {revenue_t12|compact}, which {revenue_change|direction} {revenue_change|pct:1} versus the year before.
`;

export default function Section({ data, metrics }) {
  return (
    <div className="kpis">
      <KpiTile label="Revenue · trailing 12" value={metrics.revenue_t12} format={FORMATS.compact} change={metrics.revenue_change} goodWhen="up" spark={data.revenue_spark} />
    </div>
  );
}
