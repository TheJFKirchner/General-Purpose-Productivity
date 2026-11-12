import './indicators.css';

// bar = actual, tall tick = plan, short tick = last year. m: label, actual, plan, lastYear?, min, max, fmt, good, note
const pos = (m, v) => `${(((v - m.min) / (m.max - m.min)) * 100).toFixed(1)}%`;

export function TickBar({ m, track }) {
  return (
    <div className="jt-tick" style={track ? { background:track } : undefined} role="img" aria-label={`${m.label} ${m.fmt(m.actual)}, ${m.note}`}>
      <div className="a" style={{ width:pos(m, m.actual), background:`var(--${m.good ? 'goodMark' : 'badMark'})` }} />
      <div className="p" style={{ left:pos(m, m.plan) }} />
      {m.lastYear != null && <div className="l" style={{ left:pos(m, m.lastYear) }} />}
    </div>
  );
}
