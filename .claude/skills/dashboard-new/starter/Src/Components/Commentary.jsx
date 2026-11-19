// A section's commentary (a commentary.json item): bullets across the section, the source behind a toggle.
// When the section has commentary but none for the current filters, one muted line says what it covers.
export default function Commentary({ match }) {
  if (!match?.hasItems) return null;
  const lines = (match.item?.commentary ?? []).filter((l) => typeof l === 'string' && l.trim());
  if (!lines.length) {
    const scope = match.covered.length ? `${match.covered.join(' and ')} choices` : 'no filters set';
    return <div className="commentary-none">No commentary for this choice; it is written for {scope}.</div>;
  }
  return (
    <div className="commentary">
      <ul>{lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
      {match.item.source && (
        <details className="commentary-source">
          <summary>Source</summary>
          {match.item.source}
        </details>
      )}
    </div>
  );
}
