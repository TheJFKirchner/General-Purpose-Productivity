export default function TabBar({ tabs, active, onSelect }) {
  return (
    <nav className="tab-bar" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={t.id === active} className={t.id === active ? 'on' : ''} onClick={() => onSelect(t.id)}>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
