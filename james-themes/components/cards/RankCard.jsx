import './cards.css';

// rank = position (1 = first) among `of` peers
export function RankCard({ label, value, caption, rank, of, note }) {
  return (
    <div className="jt-card">
      <div className="jt-lab" style={{ color:'var(--muted)' }}>{label}</div>
      <div className="big">{value}</div>
      {caption && <div className="sub">{caption}</div>}
      <div className="jt-dots" role="img" aria-label={`Ranked ${rank} of ${of}`}>{Array.from({ length:of }, (_, i) => <span key={i} className={i === rank - 1 ? 'on' : undefined} />)}</div>
      {note && <div className="sub">{note}</div>}
    </div>
  );
}
