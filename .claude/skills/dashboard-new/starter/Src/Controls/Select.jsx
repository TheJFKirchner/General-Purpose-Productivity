/** options: strings, or { value, label } objects. */
export default function Select({ label, value, options, onChange, disabled, title }) {
  return (
    <label className="control" title={title}>
      <span className="control-label">{label}</span>
      <select value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => {
          const { value: v, label: l } = typeof o === 'object' ? o : { value: o, label: o };
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
    </label>
  );
}
