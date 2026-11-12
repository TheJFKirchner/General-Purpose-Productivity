import { useMemo, useState } from 'react';
import './tables.css';
import '../controls/controls.css';
import { CsvButton } from '../controls/CsvButton.jsx';

// records = flat rows; dimensions = [{ key, label }] (what can go on rows or columns); measures = [{ key, label, fmt }] (summed)
// initial = { row, col, measure } keys. csv = filename for the small download button
export function PivotLedger({ records, dimensions, measures, initial = {}, csv = 'pivot.csv' }) {
  const [row, setRow] = useState(initial.row ?? dimensions[0].key), [col, setCol] = useState(initial.col ?? dimensions[1].key), [mk, setMk] = useState(initial.measure ?? measures[0].key);
  const m = measures.find((x) => x.key === mk), fmt = m.fmt ?? ((v) => v);
  const { rowKeys, colKeys, cell, rowTot, colTot, grand } = useMemo(() => {
    const uniq = (k) => [...new Set(records.map((r) => r[k]))], rk = uniq(row), ck = uniq(col), c = {}, rt = {}, ct = {}; let g = 0;
    records.forEach((r) => { const v = +r[mk] || 0, a = r[row], b = r[col]; c[a] ??= {}; c[a][b] = (c[a][b] || 0) + v; rt[a] = (rt[a] || 0) + v; ct[b] = (ct[b] || 0) + v; g += v; });
    return { rowKeys:rk, colKeys:ck, cell:c, rowTot:rt, colTot:ct, grand:g };
  }, [records, row, col, mk]);
  const rowLabel = dimensions.find((d) => d.key === row).label, round = (v) => Math.round(v * 100) / 100;
  const csvCols = [{ key:'_r', label:rowLabel }, ...colKeys.map((k) => ({ key:k, label:k })), { key:'_t', label:'Total' }];
  const csvRows = [...rowKeys.map((a) => ({ _r:a, ...Object.fromEntries(colKeys.map((b) => [b, round(cell[a]?.[b] || 0)])), _t:round(rowTot[a]) })), { _r:'Total', ...Object.fromEntries(colKeys.map((b) => [b, round(colTot[b])])), _t:round(grand) }];
  const pick = (label, value, set, opts, block) => <label className="jt-pick">{label}<select value={value} onChange={(e) => set(e.target.value)}>{opts.filter((o) => o.key !== block).map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}</select></label>;
  return (
    <div>
      <div className="jt-tablebar">
        <div style={{ display:'flex', flexWrap:'wrap', gap:'4px 18px' }}>{pick('Rows', row, setRow, dimensions, col)}{pick('Columns', col, setCol, dimensions, row)}{pick('Value', mk, setMk, measures)}</div>
        <CsvButton filename={csv} columns={csvCols} rows={csvRows} />
      </div>
      <div className="jt-ledger-wrap">
        <table className="jt-ledger jt-pivot">
          <thead><tr><th scope="col" className="left">{rowLabel}</th>{colKeys.map((b) => <th key={b} scope="col">{b}</th>)}<th scope="col">Total</th></tr></thead>
          <tbody>{rowKeys.map((a) => <tr key={a}><td className="left">{a}</td>{colKeys.map((b) => <td key={b}>{fmt(cell[a]?.[b] || 0)}</td>)}<td className="tot">{fmt(rowTot[a])}</td></tr>)}</tbody>
          <tfoot><tr><td className="left">Total</td>{colKeys.map((b) => <td key={b}>{fmt(colTot[b])}</td>)}<td>{fmt(grand)}</td></tr></tfoot>
        </table>
      </div>
    </div>
  );
}
