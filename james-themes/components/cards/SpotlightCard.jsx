import './cards.css';
import { TickBar } from '../indicators/TickBar.jsx';
import { DeltaMark } from '../indicators/DeltaMark.jsx';
import { useTickUp } from '../behaviors/useTickUp.js';

// The one lead measure, on a light card inside CommandBand
export function SpotlightCard({ m, motion = true }) {
  const shown = useTickUp(m.actual, motion);
  const tone = `var(--${m.good ? 'good' : 'bad'})`;
  return (
    <div className="jt-spot">
      <div className="jt-lab" style={{ color:'var(--muted)', fontSize:12 }}>{m.label}</div>
      <div className="row"><div className="huge">{m.fmt(shown)}</div><DeltaMark up={m.up} good={m.good} size={17}>{m.delta}</DeltaMark></div>
      <p className="said">{m.sentence}</p>
      <TickBar m={m} track="var(--leadTrack)" />
      <div className="jt-foot" style={{ color:'var(--muted)' }}><b style={{ color:tone }}>{m.note}</b><span>Tall tick is plan</span></div>
    </div>
  );
}
