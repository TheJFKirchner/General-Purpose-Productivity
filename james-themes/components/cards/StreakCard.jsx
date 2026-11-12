import './cards.css';

// periods = [{ label, over }]; over=true drawn orange (unfavorable), false green
export function StreakCard({ label, headline, caption, periods, overLabel = 'Over plan', underLabel = 'Under plan' }) {
  const n = periods.filter((p) => p.over).length;
  return (
    <div className="jt-card">
      <div className="jt-lab" style={{ color:'var(--muted)' }}>{label}</div>
      <div className="big">{headline}</div>
      {caption && <div className="sub">{caption}</div>}
      <div className="jt-months" role="img" aria-label={`${overLabel} in ${n} of ${periods.length} periods`}>
        {periods.map((p, i) => <div key={i} style={{ background:`var(--${p.over ? 'badMark' : 'goodMark'})` }}>{p.label}</div>)}
      </div>
      <div className="jt-key"><span><i style={{ background:'var(--badMark)' }} />{overLabel}</span><span><i style={{ background:'var(--goodMark)' }} />{underLabel}</span></div>
    </div>
  );
}
