import './cards.css';

// parts = [{ name, value }] (max 5); the strip shows each part's share, the key shows its value
export function SplitDial({ label, value, caption, parts, fmt = (v) => v }) {
  const total = parts.reduce((a, p) => a + Math.abs(p.value), 0);
  return (
    <div className="jt-card">
      <div className="jt-lab" style={{ color:'var(--muted)' }}>{label}</div>
      <div className="big">{value}</div>
      {caption && <div className="sub">{caption}</div>}
      <div className="jt-strip" role="img" aria-label={parts.map((p) => `${p.name} ${Math.round((Math.abs(p.value) / total) * 100)} percent`).join(', ')}>
        {parts.map((p, i) => <div key={p.name} style={{ width:`${(Math.abs(p.value) / total) * 100}%`, background:`var(--cat${i + 1})` }} />)}
      </div>
      <div className="jt-key">{parts.map((p, i) => <span key={p.name}><i style={{ background:`var(--cat${i + 1})` }} />{p.name} {fmt(p.value)}</span>)}</div>
    </div>
  );
}
