import './controls.css';

// chips = [{ key, label }]; onRemove(key). Inherits text color, so it works on the band or on white
export function FilterChips({ chips, onRemove }) {
  return (
    <div className="jt-chips">
      {chips.map((c) => <span key={c.key} className="jt-chip">{c.label}{onRemove && <button type="button" aria-label={`Remove filter ${c.label}`} onClick={() => onRemove(c.key)}>{'\u00D7'}</button>}</span>)}
    </div>
  );
}
