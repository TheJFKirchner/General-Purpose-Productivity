import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, axisLabel } from './chartKit.js';

// rows = [{ name, from, to }]; highlight = name drawn in primary (default: largest percent change)
export function slopeShiftOption(t, { rows, ends = ['Last year', 'This year'], fmt = (v) => '$' + v, highlight, max, motion = true }) {
  const pct = (r) => (r.to / r.from - 1) * 100;
  const hotName = highlight ?? rows.reduce((a, b) => (pct(b) > pct(a) ? b : a)).name;
  return {
    ...base(motion), grid:{ left:170, right:150, top:16, bottom:28 },
    xAxis:{ type:'category', data:ends, boundaryGap:false, axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:axisLabel(t, { fontSize:13, fontWeight:600, color:t.ink }) },
    yAxis:{ type:'value', show:false, min:0, max:max ?? Math.max(...rows.map((r) => Math.max(r.from, r.to))) * 1.08 },
    series:rows.map((r) => { const hot = r.name === hotName, p = pct(r), L = { show:true, fontFamily:FONT, fontSize:13, color:t.ink, fontWeight:hot ? 700 : 500, distance:10 };
      return { type:'line', symbol:'rect', symbolSize:9, lineStyle:{ color:hot ? t.primary : t.prior, width:hot ? 4 : 2.5 }, itemStyle:{ color:hot ? t.primary : t.prior }, emphasis:{ disabled:true },
        data:[ { value:r.from, label:{ ...L, position:'left', formatter:`${r.name}  ${fmt(r.from)}` } },
               { value:r.to, label:{ ...L, position:'right', formatter:`${fmt(r.to)}   ${p >= 0 ? '+' : '\u2212'}${Math.abs(p).toFixed(1)}%` } } ] }; }),
  };
}

// Before and after for several groups; steepness is the change
export function SlopeShift({ t, rows, ends, fmt, highlight, max, motion, height = 290, label }) {
  const option = useMemo(() => slopeShiftOption(t, { rows, ends, fmt, highlight, max, motion }), [t, rows, ends, fmt, highlight, max, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
