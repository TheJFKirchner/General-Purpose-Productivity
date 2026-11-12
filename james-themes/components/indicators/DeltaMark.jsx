import './indicators.css';

// Arrow + change text, green if good else orange
export function DeltaMark({ up, good, size = 13, children }) {
  return <span className="jt-delta" style={{ fontSize:size, color:`var(--${good ? 'good' : 'bad'})` }}><span aria-hidden="true">{up ? '\u25B2' : '\u25BC'}</span> {children}</span>;
}
