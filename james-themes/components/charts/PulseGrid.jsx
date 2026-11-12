import { useMemo, useState } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { RangeGate } from '../controls/RangeGate.jsx';
import { FONT, base } from './chartKit.js';

// items = [{ name, data, change }]; hotAbove = change above which a line is drawn in primary
export function pulseGridOption(t, { labels, items, min, max, baseline, hotAbove = Infinity, fmtChange = (v) => '+' + v + '%', motion = true }) {
  const n = items.length, step = 100 / n, last = labels.length - 1;
  return {
    ...base(motion),
    title:items.map((it, i) => ({ text:`${it.name}\n{b|${fmtChange(it.change)}}`, left:`${(i * step + 1).toFixed(2)}%`, top:0,
      textStyle:{ fontSize:13, fontWeight:600, color:t.ink, fontFamily:FONT, lineHeight:18, rich:{ b:{ fontSize:15, fontWeight:700, color:it.change > hotAbove ? t.primary : t.muted, fontFamily:FONT } } } })),
    grid:items.map((it, i) => ({ left:`${(i * step + 1).toFixed(2)}%`, width:`${(step - 3).toFixed(2)}%`, top:44, bottom:8 })),
    xAxis:items.map((it, i) => ({ gridIndex:i, type:'category', data:labels, show:false, boundaryGap:false })),
    yAxis:items.map((it, i) => ({ gridIndex:i, type:'value', min, max, show:false })),
    series:items.map((it, i) => { const hot = it.change > hotAbove; return {
      type:'line', xAxisIndex:i, yAxisIndex:i, data:it.data, symbol:'rect', showAllSymbol:true, symbolSize:(v, p) => (p.dataIndex === last ? 9 : 0),
      lineStyle:{ color:hot ? t.primary : t.prior, width:hot ? 3.5 : 2.5 }, itemStyle:{ color:hot ? t.primary : t.prior }, emphasis:{ disabled:true },
      ...(baseline != null ? { markLine:{ silent:true, symbol:'none', lineStyle:{ color:t.grid, width:1.5 }, label:{ show:false }, data:[{ yAxis:baseline }] } } : {}),
    }; }),
  };
}

// Same metric over time for many groups, one small chart each, shared scale.
// gate = { min, max, step } adds a RangeGate that hides groups whose change is outside the chosen range
export function PulseGrid({ t, labels, items, min, max, baseline, hotAbove, fmtChange = (v) => '+' + v + '%', gate, motion, height = 230, label }) {
  const [range, setRange] = useState(gate ? [gate.min, gate.max] : null);
  const shown = useMemo(() => (range ? items.filter((it) => it.change >= range[0] && it.change <= range[1]) : items), [items, range]);
  const option = useMemo(() => pulseGridOption(t, { labels, items:shown, min, max, baseline, hotAbove, fmtChange, motion }), [t, labels, shown, min, max, baseline, hotAbove, fmtChange, motion]);
  return (
    <div>
      {gate && <RangeGate label="Show groups with a change between" min={gate.min} max={gate.max} step={gate.step ?? 0.5} value={range} onChange={setRange} fmt={fmtChange} note={`${shown.length} of ${items.length} shown`} />}
      {shown.length ? <ChartMount option={option} height={height} label={label} /> : <p style={{ height, margin:0, display:'flex', alignItems:'center', color:'var(--muted)' }}>No groups fall in this range.</p>}
    </div>
  );
}
