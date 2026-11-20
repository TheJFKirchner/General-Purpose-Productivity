import { formatDate } from '../Lib/dates.js';

export default function ReportHeader({ title, audience, asOf, source, staleDays }) {
  return (
    <header className="report-header">
      <h1>{title}</h1>
      {audience && <div className="audience">Prepared for {audience}</div>}
      <div className="meta-line">
        {asOf && <>Data as of {formatDate(asOf)}</>}
        {source && <>{asOf ? ' · Source: ' : 'Source: '}{source}</>}
      </div>
      {staleDays !== null && (
        <div className="stale-banner" role="status">
          Data was pulled {staleDays} days ago. Refresh with <code>npm run pipeline</code>.
        </div>
      )}
    </header>
  );
}
