import './controls.css';

// options = [{ key, label }]; one pressed at a time
export function PeriodSwitch({ options, value, onChange, label = 'Period' }) {
  return (
    <div className="jt-seg" role="group" aria-label={label}>
      {options.map((o) => <button key={o.key} type="button" aria-pressed={o.key === value} onClick={() => onChange(o.key)}>{o.label}</button>)}
    </div>
  );
}
