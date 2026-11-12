import { useState } from 'react';
import './pictorial.css';
import '../controls/controls.css';
import { shade, isDeep } from './shade.js';
import { TILE_ROWS, STATE_NAMES } from './usTiles.js';
import { PeriodSwitch } from '../controls/PeriodSwitch.jsx';

// values = { TX: 8.6, ... } by state abbreviation; scale = [lo, hi] for shading; regions = { 'Southeast': ['VA', ...] } (optional, adds a fade-to-region switch)
// overall = { name, value } shown when nothing is selected; onSelect(abbr|null) optional
export function TileAtlas({ t, values, scale, regions, overall, fmt = (v) => '+' + v.toFixed(1) + '%', onSelect }) {
  const [sel, setSel] = useState(null), [reg, setReg] = useState('All');
  const regionOf = {}; if (regions) Object.entries(regions).forEach(([r, list]) => list.forEach((s) => { regionOf[s] = r; }));
  const inView = Object.keys(values).filter((s) => reg === 'All' || regionOf[s] === reg), ranked = Object.keys(values).sort((a, b) => values[b] - values[a]);
  const mean = (list) => list.reduce((a, s) => a + values[s], 0) / list.length;
  const pick = (s) => { const next = sel === s ? null : s; setSel(next); if (onSelect) onSelect(next); };
  const top = inView.slice().sort((a, b) => values[b] - values[a]);
  return (
    <div className="jt-atlas">
      <div className="jt-tilegrid" role="group" aria-label="States">
        {TILE_ROWS.flatMap((row, r) => row.map((s, c) => (s === '.' ? <span key={`${r}-${c}`} aria-hidden="true" /> : (
          <button key={s} type="button" className={`jt-st${sel === s ? ' on' : ''}${reg !== 'All' && regionOf[s] !== reg ? ' dim' : ''}`} aria-pressed={sel === s} aria-label={`${STATE_NAMES[s]}, ${fmt(values[s])}`}
            style={{ background:shade(t, values[s], scale[0], scale[1]), color:isDeep(values[s], scale[0], scale[1]) ? '#fff' : 'var(--ink)' }} onClick={() => pick(s)}>
            <b>{s}</b><span>{fmt(values[s])}</span>
          </button>))))}
      </div>
      <div className="jt-readout" aria-live="polite">
        <div className="jt-lab" style={{ color:'var(--primary)' }}>Leading</div>
        <h3>{sel ? STATE_NAMES[sel] : reg !== 'All' ? reg : overall?.name ?? 'All states'}</h3>
        <div className="big">{fmt(sel ? values[sel] : reg !== 'All' ? mean(inView) : overall?.value ?? mean(inView))}</div>
        {sel ? <><p>{regionOf[sel] ? `${regionOf[sel]} region. ` : ''}Ranked {ranked.indexOf(sel) + 1} of {ranked.length}.</p></>
          : <><p>Highest: {STATE_NAMES[top[0]]} {fmt(values[top[0]])}</p><p>Lowest: {STATE_NAMES[top[top.length - 1]]} {fmt(values[top[top.length - 1]])}</p></>}
        {regions && <><div className="jt-lab" style={{ color:'var(--muted)', margin:'12px 0 6px' }}>Fade to a region</div>
          <div style={{ display:'flex', flexWrap:'wrap' }}><PeriodSwitch label="Region" options={['All', ...Object.keys(regions)].map((r) => ({ key:r, label:r }))} value={reg} onChange={(r) => { setReg(r); if (sel && r !== 'All' && regionOf[sel] !== r) pick(sel); }} /></div></>}
        <div className="jt-ramp"><span>Lower</span><i aria-hidden="true" style={{ background:`linear-gradient(90deg, ${t.ramp.map((c) => `rgb(${c.join(',')})`).join(',')})` }} /><span>Higher</span></div>
      </div>
    </div>
  );
}
