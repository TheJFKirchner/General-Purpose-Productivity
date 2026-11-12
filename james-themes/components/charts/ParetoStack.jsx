import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip, axisLabel, catAxis, valAxis, valueLabel, shadowPointer } from './chartKit.js';

// rows = [{ name, value }] in display order (ranked, with any "all other" row last); top = how many leading bars to draw in primary
export function paretoStackOption(t, { rows, top = 3, restName, fmt = (v) => '$' + v.toFixed(1), max, motion = true }) {
  const total = rows.reduce((a, r) => a + r.value, 0), run = []; rows.reduce((s, r) => { run.push(Math.round(((s + r.value) / total) * 100)); return s + r.value; }, 0);
  return {
    ...base(motion), grid:{ left:4, right:8, top:36, bottom:2, containLabel:true },
    tooltip:tip(t, { trigger:'axis', axisPointer:shadowPointer }),
    xAxis:catAxis(t, rows.map((r) => r.name), { axisLabel:axisLabel(t, { color:t.ink, fontSize:13, interval:0 }) }),
    yAxis:[valAxis(t, { max, axisLabel:axisLabel(t, { formatter:(v) => fmt(v).replace(/\.0$/, '') }) }), { type:'value', min:0, max:100, show:false }],
    series:[
      { name:'Amount', type:'bar', barWidth:'56%', tooltip:{ valueFormatter:fmt },
        data:rows.map((r, i) => ({ value:r.value, itemStyle:{ color:i < top ? t.primary : r.name === restName ? t.dim : t.prior, borderRadius:[5,5,0,0] }, label:{ color:i < top ? '#fff' : t.ink } })),
        label:valueLabel(t, { position:'insideBottom', distance:8, formatter:(p) => fmt(p.value) }) },
      { name:'Running share', type:'line', yAxisIndex:1, data:run, symbol:'rect', symbolSize:8, lineStyle:{ color:t.ink, width:2.5 }, itemStyle:{ color:t.ink }, tooltip:{ valueFormatter:(v) => v + '%' }, emphasis:{ disabled:true },
        label:{ show:true, position:'top', distance:8, fontFamily:FONT, fontSize:13, fontWeight:700, color:t.ink, backgroundColor:'#fff', padding:[2,4], formatter:(p) => p.value + '%' } },
    ],
  };
}

// Ranked drivers with a running share: how few explain most of the total
export function ParetoStack({ t, rows, top, restName, fmt, max, motion, height = 300, label }) {
  const option = useMemo(() => paretoStackOption(t, { rows, top, restName, fmt, max, motion }), [t, rows, top, restName, fmt, max, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
