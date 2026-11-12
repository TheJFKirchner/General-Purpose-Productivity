import './cards.css';

// White card that holds one chart inside CommandBand
export function ChartSlate({ label, children }) {
  return (
    <div className="jt-slate">
      {label && <div className="jt-lab" style={{ color:'var(--muted)' }}>{label}</div>}
      {children}
    </div>
  );
}
