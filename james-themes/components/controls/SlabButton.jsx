import './controls.css';

// kind: 'solid' | 'line' (on the band) ; 'pri' | 'sec' (on white)
export function SlabButton({ kind = 'sec', onClick, children }) {
  return <button type="button" className={`jt-btn ${kind}`} onClick={onClick}>{children}</button>;
}
