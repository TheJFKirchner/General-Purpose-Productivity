import './controls.css';

// Two sliders picking a low and a high bound. value = [lo, hi]
export function RangeGate({ label, min, max, step = 1, value, onChange, fmt = (v) => v, note }) {
  const [lo, hi] = value;
  return (
    <div className="jt-gate">
      <span>{label}</span>
      <label>From <input type="range" min={min} max={max} step={step} value={lo} onChange={(e) => onChange([Math.min(+e.target.value, hi), hi])} /><output>{fmt(lo)}</output></label>
      <label>to <input type="range" min={min} max={max} step={step} value={hi} onChange={(e) => onChange([lo, Math.max(+e.target.value, lo)])} /><output>{fmt(hi)}</output></label>
      {note && <span aria-live="polite">{note}</span>}
    </div>
  );
}
