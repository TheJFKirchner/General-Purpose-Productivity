import './cards.css';

// share = 0..1 of the total explained by the driver named in `sentence`
export function DriverCard({ label = 'Main driver', sentence, share, note }) {
  return (
    <div className="jt-card dark">
      <div className="jt-lab">{label}</div>
      <div className="said">{sentence}</div>
      <div className="jt-strip" role="img" aria-label={`${Math.round(share * 100)} percent of the total`}><div style={{ width:`${share * 100}%`, background:'#fff' }} /></div>
      {note && <div className="sub">{note}</div>}
    </div>
  );
}
