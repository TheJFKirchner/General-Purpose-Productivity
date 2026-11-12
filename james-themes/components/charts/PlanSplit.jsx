import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, STATUS, tip } from './chartKit.js';

// rows = [{ name, value }]; value < 0 = under plan = favorable (green, extends left)
export function planSplitOption(t, { rows, min, max, fmt = (v) => '$' + v, motion = true }) {
  const r = rows.slice().reverse();
  return {
    animation:motion, animationDuration:900, textStyle:{ fontFamily:FONT },
    grid:{ left:4, right:56, top:8, bottom:4, containLabel:true },
    tooltip:{ trigger:'item', formatter:(p) => `<b>${p.name}</b><br>${fmt(Math.abs(p.value))} ${p.value < 0 ? 'under' : 'over'} plan`, ...tip(t) },
    xAxis:{ type:'value', min, max, axisLabel:{ show:false }, splitLine:{ show:false } },
    yAxis:{ type:'category', data:r.map((x) => x.name), axisLine:{ show:true, lineStyle:{ color:t.ink, width:2 } }, axisTick:{ show:false },
      axisLabel:{ color:t.ink, fontSize:14, fontFamily:FONT, width:150, overflow:'break' } },
    series:[{ type:'bar', barWidth:24,
      data:r.map((x) => ({ name:x.name, value:x.value,
        itemStyle:{ color:x.value < 0 ? STATUS.goodMark : STATUS.badMark, borderRadius:x.value < 0 ? [7,0,0,7] : [0,7,7,0] },
        label:{ position:x.value < 0 ? 'left' : 'right' } })),
      label:{ show:true, color:t.ink, fontWeight:700, fontSize:14, fontFamily:FONT, formatter:(p) => (p.value < 0 ? '\u2212' : '+') + fmt(Math.abs(p.value)) },
      emphasis:{ itemStyle:{ borderColor:t.ink, borderWidth:3 } } }],
  };
}

// Over/under plan bars around a zero line. active + onActive link it to a LedgerTable (see behaviors/useLinkGlow.js)
export function PlanSplit({ t, rows, min, max, fmt, motion, height, label, active, onActive }) {
  const option = useMemo(() => planSplitOption(t, { rows, min, max, fmt, motion }), [t, rows, min, max, fmt, motion]);
  const onEvents = useMemo(() => (onActive ? { mouseover:(p) => onActive(p.name), globalout:() => onActive(null) } : undefined), [onActive]);
  return <ChartMount option={option} height={height} label={label} onEvents={onEvents} highlight={onActive ? active : undefined} />;
}
