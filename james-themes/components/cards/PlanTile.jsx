import './cards.css';
import { TickBar } from '../indicators/TickBar.jsx';
import { useTickUp } from '../behaviors/useTickUp.js';

// Supporting measure. bars: 'status' (green/orange top bar) | 'one' (primary). Click -> onLead
export function PlanTile({ m, bars = 'status', motion = true, onLead }) {
  const shown = useTickUp(m.actual, motion);
  const bar = bars === 'one' ? 'var(--primary)' : `var(--${m.good ? 'goodMark' : 'badMark'})`;
  return (
    <button type="button" className="jt-tile" style={{ '--bar':bar }} onClick={onLead}>
      <div className="jt-lab" style={{ color:'var(--muted)' }}>{m.label}</div>
      <div className="v">{m.fmt(shown)}</div>
      <TickBar m={m} />
      <div className="jt-foot"><b style={{ color:`var(--${m.good ? 'good' : 'bad'})` }}>{m.note}</b><span style={{ color:'var(--muted)' }}>Plan {m.fmt(m.plan)}</span></div>
    </button>
  );
}
