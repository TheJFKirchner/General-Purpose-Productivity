import { renderNote } from '../Lib/format.js';

const Segments = ({ segments }) =>
  segments.map((s, i) => (s.missing ? <mark key={i} className="missing">{s.text}</mark> : <span key={i}>{s.text}</span>));

/** A section's note with live numbers: metrics = its analytic's "metrics" for the current filters. */
export default function Note({ markdown, metrics }) {
  const { blocks } = renderNote(markdown, metrics ?? {});
  return (
    <div className="note">
      {blocks.map((b, i) =>
        b.type === 'list' ? (
          <ul key={i}>{b.items.map((segs, j) => <li key={j}><Segments segments={segs} /></li>)}</ul>
        ) : (
          <p key={i}><Segments segments={b.segments} /></p>
        ),
      )}
    </div>
  );
}
