import './indicators.css';

// Small in-row bar for tables. flagged -> orange, else primary
export function RowMeter({ value, min, max, flagged = false }) {
  const w = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  return <span className="jt-meter" aria-hidden="true"><b style={{ width:`${w.toFixed(0)}%`, background:flagged ? 'var(--badMark)' : 'var(--primary)' }} /></span>;
}
