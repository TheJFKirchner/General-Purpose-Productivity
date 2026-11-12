import './cards.css';

// scale = [min, max] of the track; range = [lo, hi] of the recent window; current = today's value (number)
export function RangeCard({ label, value, caption, scale, range, current, rangeLabel, fmt = (v) => v }) {
  const pos = (v) => `${(((v - scale[0]) / (scale[1] - scale[0])) * 100).toFixed(1)}%`;
  return (
    <div className="jt-card">
      <div className="jt-lab" style={{ color:'var(--muted)' }}>{label}</div>
      <div className="big">{value}</div>
      {caption && <div className="sub">{caption}</div>}
      <div className="jt-rangebar" role="img" aria-label={`Current ${fmt(current)}; ${rangeLabel} ${fmt(range[0])} to ${fmt(range[1])}; scale ${fmt(scale[0])} to ${fmt(scale[1])}`}>
        <div className="t" /><div className="r" style={{ left:pos(range[0]), width:`calc(${pos(range[1])} - ${pos(range[0])})` }} /><div className="d" style={{ left:pos(current) }} />
      </div>
      <div className="jt-ends"><span>{fmt(scale[0])}</span><span>{fmt(scale[1])}</span></div>
      <div className="jt-key"><span><i style={{ background:'var(--prior)' }} />{rangeLabel} {fmt(range[0])} to {fmt(range[1])}</span></div>
    </div>
  );
}
