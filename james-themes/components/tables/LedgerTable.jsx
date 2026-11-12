import './tables.css';
import { RowMeter } from '../indicators/RowMeter.jsx';
import { CsvButton } from '../controls/CsvButton.jsx';

// columns = [{ key, label, align?:'left', fmt?, meter?:{ min, max, flag?:(v)=>bool } }]; first column is the row name
// active = row name to highlight; onActive(name|null) fires on hover (pair with PlanSplit via useLinkGlow)
// csv = filename -> small CSV button at the top right of the table
export function LedgerTable({ columns, rows, rowKey = columns[0].key, active = null, onActive, csv }) {
  return (
    <div>
    {csv && <div className="jt-tablebar"><span /><CsvButton filename={csv} columns={columns} rows={rows} /></div>}
    <div className="jt-ledger-wrap">
      <table className="jt-ledger">
        <thead><tr>{columns.map((c, i) => <th key={c.key} scope="col" className={i === 0 || c.align === 'left' || c.meter ? 'left' : undefined}>{c.label}</th>)}</tr></thead>
        <tbody onMouseLeave={onActive ? () => onActive(null) : undefined}>
          {rows.map((r) => (
            <tr key={r[rowKey]} className={active === r[rowKey] ? 'on' : undefined} onMouseEnter={onActive ? () => onActive(r[rowKey]) : undefined}>
              {columns.map((c, i) => {
                const v = r[c.key], text = c.fmt ? c.fmt(v) : v;
                if (c.meter) { const flagged = c.meter.flag ? c.meter.flag(v) : false;
                  return <td key={c.key} className="left"><RowMeter value={v} min={c.meter.min} max={c.meter.max} flagged={flagged} /><span style={{ fontWeight:flagged ? 700 : 500 }}>{text}</span></td>; }
                return <td key={c.key} className={i === 0 || c.align === 'left' ? 'left' : undefined}>{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    </div>
  );
}
