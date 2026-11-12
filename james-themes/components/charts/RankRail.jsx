import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT } from './chartKit.js';

// rows = [{ name, value }]; highlight = name to emphasize (others dim) or null
export function rankRailOption(t, { rows, max, highlight = null, fmt = String, motion = true }) {
  const r = rows.slice().sort((a, b) => a.value - b.value);
  return {
    animation:motion, animationDuration:700, textStyle:{ fontFamily:FONT },
    grid:{ left:4, right:52, top:2, bottom:2, containLabel:true },
    xAxis:{ type:'value', show:false, min:0, max },
    yAxis:{ type:'category', data:r.map((x) => x.name), axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:{ color:t.ink, fontSize:13, fontFamily:FONT } },
    series:[{ type:'bar', barWidth:14, itemStyle:{ borderRadius:[0,7,7,0] },
      data:r.map((x) => ({ name:x.name, value:x.value, itemStyle:{ color:highlight && x.name !== highlight ? t.dim : t.primary } })),
      label:{ show:true, position:'right', color:t.ink, fontWeight:700, fontSize:13, fontFamily:FONT, formatter:(p) => fmt(p.value) },
      emphasis:{ itemStyle:{ borderColor:t.ink, borderWidth:2 } } }],
  };
}

// Ranked horizontal bars, largest on top, values at bar ends
export function RankRail({ t, rows, max, highlight, fmt, motion, height, label }) {
  const option = useMemo(() => rankRailOption(t, { rows, max, highlight, fmt, motion }), [t, rows, max, highlight, fmt, motion]);
  return <ChartMount option={option} height={height ?? rows.length * 30 + 10} label={label} />;
}
