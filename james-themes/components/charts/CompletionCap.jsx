import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip, axisLabel, catAxis, valAxis, valueLabel, shadowPointer, estimateStyle } from './chartKit.js';

// paid = known so far; estimate = still-to-come portion (0 where complete); prior = comparison line (optional)
export function completionCapOption(t, { labels, paid, estimate, prior, names = ['Paid', 'Estimate not yet reported', 'Last year'], fmt = (v) => '$' + v, min, max, motion = true }) {
  return {
    ...base(motion), grid:{ left:4, right:8, top:40, bottom:2, containLabel:true },
    legend:{ top:0, left:0, itemWidth:12, itemHeight:12, icon:'rect', textStyle:{ color:t.muted, fontSize:13, fontFamily:FONT }, selectedMode:false },
    tooltip:tip(t, { trigger:'axis', axisPointer:shadowPointer, valueFormatter:(v) => (v == null || v === '-' ? '' : fmt(v)) }),
    xAxis:catAxis(t, labels, { axisLabel:axisLabel(t, { interval:0 }) }), yAxis:valAxis(t, { min, max, axisLabel:axisLabel(t, { formatter:fmt }) }),
    series:[
      { name:names[0], type:'bar', stack:'c', barWidth:'58%', data:paid, itemStyle:{ color:t.primary } },
      { name:names[1], type:'bar', stack:'c', data:estimate.map((v) => v || '-'), itemStyle:estimateStyle(t), label:valueLabel(t, { position:'top', fontSize:12, formatter:(p) => fmt(paid[p.dataIndex] + estimate[p.dataIndex]) }) },
      ...(prior ? [{ name:names[2], type:'line', data:prior, symbol:'none', lineStyle:{ color:t.ink, width:2, type:[6,5] }, itemStyle:{ color:t.ink }, emphasis:{ disabled:true } }] : []),
    ],
  };
}

// A metric over time where the most recent periods are only partly known
export function CompletionCap({ t, labels, paid, estimate, prior, names, fmt, min, max, motion, height = 280, label }) {
  const option = useMemo(() => completionCapOption(t, { labels, paid, estimate, prior, names, fmt, min, max, motion }), [t, labels, paid, estimate, prior, names, fmt, min, max, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
