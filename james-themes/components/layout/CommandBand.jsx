import './layout.css';
import { SlabButton } from '../controls/SlabButton.jsx';

// Colored band. actions = [{ label, kind:'solid'|'line', onClick }]. children = SpotlightCard + ChartSlate
export function CommandBand({ kicker, headline, actions = [], children }) {
  return (
    <div className="jt-band">
      <div className="jt-bandtop">
        <div><div className="jt-lab" style={{ color:'var(--bandSoft)' }}>{kicker}</div><h1>{headline}</h1></div>
        <div className="jt-btnrow">{actions.map((a) => <SlabButton key={a.label} kind={a.kind || 'line'} onClick={a.onClick}>{a.label}</SlabButton>)}</div>
      </div>
      <div className="jt-lead">{children}</div>
    </div>
  );
}
