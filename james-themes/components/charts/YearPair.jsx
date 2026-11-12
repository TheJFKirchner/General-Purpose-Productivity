import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip, axisLabel, catAxis, valAxis, valueLabel, shadowPointer } from './chartKit.js';

export function yearPairOption(t, { labels, cur, prior, names = ['Last year', 'This year'], fmt = (v) => '$' + v, min, max, motion = true }) {
  return {
    ...base(motion), grid:{ left:4, right:8, top:40, bottom:2, containLabel:true },
    legend:{ top:0, left:0, itemWidth:12, itemHeight:12, icon:'rect', textStyle:{ color:t.muted, fontSize:13, fontFamily:FONT }, selectedMode:false },
    tooltip:tip(t, { trigger:'axis', axisPointer:shadowPointer, valueFormatter:fmt }),
    xAxis:catAxis(t, labels), yAxis:valAxis(t, { min, max, axisLabel:axisLabel(t, { formatter:fmt }) }),
    series:[
      { name:names[0], type:'bar', data:prior, barWidth:'28%', itemStyle:{ color:t.dim, borderRadius:[5,5,0,0] } },
      { name:names[1], type:'bar', data:cur, barWidth:'28%', barGap:'8%', itemStyle:{ color:t.primary, borderRadius:[5,5,0,0] },
        label:valueLabel(t, { position:'top', formatter:(p) => { const c = (cur[p.dataIndex] / prior[p.dataIndex] - 1) * 100; return (c >= 0 ? '+' : '\u2212') + Math.abs(c).toFixed(1) + '%'; } }) },
    ],
  };
}

// A few periods, two years side by side, percent change printed on top
export function YearPair({ t, labels, cur, prior, names, fmt, min, max, motion, height = 260, label }) {
  const option = useMemo(() => yearPairOption(t, { labels, cur, prior, names, fmt, min, max, motion }), [t, labels, cur, prior, names, fmt, min, max, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
