/* Top bar: brand, connection, whole-app usage, avatar. The section navigation is the left sidebar (Sidebar.tsx).
   A coral bar under it says when the connection to the back end is lost. */
import { useComputed, useLaunchpad } from '../store';
import { actions, sel } from '../store';
import { tokShort, usd } from '../lib/format';
import { Wallet, WifiOff } from './icons';

export function Header() {
  const conn = useLaunchpad(st => st.ui.conn);
  const { cost, toks } = useComputed(st => {
    const t = sel.appTotals(st);
    return { cost: usd(t.cost, { approx: true }), toks: tokShort(t.parts) };
  });

  return (
    <>
      <header>
        <div className="brand">
          <svg viewBox="0 0 40 40" aria-hidden="true"><circle className="lg-ring" cx="20" cy="20" r="18" /><circle className="lg-ring2" cx="20" cy="20" r="11" /><circle className="lg-sun" cx="20" cy="20" r="5" /><circle className="lg-moon" cx="34" cy="11" r="3.5" /></svg>
          <b>Launchpad</b><span>by COSMO</span>
        </div>
        <div className="hdr-right">
          <span className="conn" role="status" title={conn.text}><span className="dot" style={{ background: conn.color }} /><span className="conn-txt">{conn.text}</span></span>
          <button type="button" className="usage" data-tip="allagents" aria-label={`Whole app usage ${cost}, ${toks}. Open the Usage screen`} onClick={() => actions.setView('usage')}><Wallet /><span className="u-txt"><span className="u-lbl">Whole app · </span>{cost} · {toks}</span></button>
          <span className="avatar" role="img" aria-label="You">J</span>
        </div>
      </header>
      {conn.text === 'Disconnected' ? (
        <div className="connbar" role="alert"><WifiOff />Disconnected from Launchpad. <span>Actions cannot be sent until it is back; close and reopen Launchpad if this lasts.</span></div>
      ) : null}
    </>
  );
}
