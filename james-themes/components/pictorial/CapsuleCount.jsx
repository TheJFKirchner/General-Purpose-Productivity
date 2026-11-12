import './pictorial.css';

const TONES = ['var(--primary)', 'var(--prior)', 'var(--hair)'];

// groups = [{ title, parts:[{ name, count }], callout:{ value, text } }]; each group's counts should total 100.
// parts[0] is the one to notice (primary color); keep the same part order in every group; max 3 parts
export function CapsuleCount({ groups }) {
  return (
    <div>
      <div className="jt-caps">
        {groups.map((g) => (
          <div key={g.title}>
            <h3>{g.title}</h3>
            <div className="jt-waffle" role="img" aria-label={g.parts.map((p) => `${p.name} ${p.count}`).join(', ')}>
              {g.parts.flatMap((p, i) => Array.from({ length:p.count }, (_, k) => <i key={`${i}-${k}`} style={{ background:TONES[i] }} />))}
            </div>
            {g.callout && <p className="jt-capnote"><b>{g.callout.value}</b> {g.callout.text}</p>}
          </div>))}
      </div>
      <div className="jt-capkey">{groups[0].parts.map((p, i) => <span key={p.name}><i style={{ background:TONES[i] }} />{p.name}</span>)}</div>
    </div>
  );
}
