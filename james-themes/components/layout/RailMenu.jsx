import './layout.css';

// items = [{ label, href, current? }]
export function RailMenu({ brand, sub, items = [] }) {
  return (
    <nav className="jt-rail" aria-label="Sections">
      <div className="brand">{brand}</div>
      {sub && <div className="sub">{sub}</div>}
      {items.map((x) => <a key={x.label} href={x.href} aria-current={x.current ? 'page' : undefined}>{x.label}</a>)}
    </nav>
  );
}
