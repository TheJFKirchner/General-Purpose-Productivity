// RESTRICTED: do NOT use unless the user explicitly asks for BodyLens or a body figure. Never choose it on your own.
import { useState } from 'react';
import './pictorial.css';
import { shade, isDeep } from './shade.js';

const SPOTS = { head:[130, 46], 'chest-left':[108, 158], 'chest-right':[146, 150], abdomen:[130, 212], pelvis:[130, 262], knee:[104, 392], whole:[222, 60] };

// items = [{ name, value, tone, spot }]; spot = head | chest-left | chest-right | abdomen | pelvis | knee | whole (beside the figure)
// circle size = value; shade = tone on toneScale [lo, hi]
export function BodyLens({ t, items, fmt = (v) => '+$' + v.toFixed(1), toneScale, note }) {
  const [on, setOn] = useState(-1), max = Math.max(...items.map((x) => x.value));
  const fill = (x) => shade(t, x.tone, toneScale[0], toneScale[1]), ink = (x) => (isDeep(x.tone, toneScale[0], toneScale[1]) ? '#fff' : t.ink);
  return (
    <div className="jt-bodylens">
      <svg viewBox="0 0 260 520" role="img" aria-label="Body figure with a numbered circle for each item in the list" onMouseLeave={() => setOn(-1)}>
        <g fill={`rgb(${t.ramp[0].join(',')})`} stroke={t.ink} strokeWidth="1.5">
          <circle cx="130" cy="48" r="34" /><rect x="116" y="78" width="28" height="24" rx="6" /><rect x="42" y="104" width="28" height="178" rx="14" /><rect x="190" y="104" width="28" height="178" rx="14" />
          <rect x="76" y="96" width="108" height="196" rx="30" /><rect x="82" y="276" width="44" height="226" rx="20" /><rect x="134" y="276" width="44" height="226" rx="20" />
        </g>
        {items.some((x) => x.spot === 'whole') && <text x="222" y="22" textAnchor="middle" fontSize="10" fontWeight="600" fill={t.muted}>Whole body</text>}
        {items.map((x, i) => { const [cx, cy] = SPOTS[x.spot] ?? SPOTS.whole; return (
          <g key={x.name} onMouseEnter={() => setOn(i)}>
            <circle className={`jt-spot${on === i ? ' on' : ''}`} cx={cx} cy={cy} r={7 + Math.sqrt(x.value / max) * 15.5} fill={fill(x)} stroke="#fff" strokeWidth="2.5" />
            <text x={cx} y={cy + 4.5} textAnchor="middle" fontSize="13" fontWeight="700" fill={ink(x)} pointerEvents="none">{i + 1}</text>
          </g>); })}
      </svg>
      <div className="jt-syslist" onMouseLeave={() => setOn(-1)}>
        {items.map((x, i) => (
          <button key={x.name} type="button" className={`jt-sys${on === i ? ' on' : ''}`} onMouseEnter={() => setOn(i)} onFocus={() => setOn(i)} onBlur={() => setOn(-1)} aria-label={`${x.name}, ${fmt(x.value)}`}>
            <span className="n" style={{ background:fill(x), color:ink(x) }}>{i + 1}</span><span className="nm">{x.name}</span>
            <span className="bar"><i style={{ width:`${(x.value / max) * 100}%`, background:fill(x) }} /></span><span className="v">{fmt(x.value)}</span>
          </button>))}
        {note && <p style={{ margin:'6px 8px 0', fontSize:12, color:'var(--muted)' }}>{note}</p>}
      </div>
    </div>
  );
}
