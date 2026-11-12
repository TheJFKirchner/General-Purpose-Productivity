import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, tip, axisLabel } from './chartKit.js';

export function twinTrendOption(t, { labels, cur, prior, fmt = String, motion = true }) {
  const last = cur.length - 1;
  return {
    animation:motion, animationDuration:900, textStyle:{ fontFamily:FONT },
    grid:{ left:4, right:150, top:12, bottom:2, containLabel:true },
    tooltip:{ trigger:'axis', axisPointer:{ type:'line', lineStyle:{ color:t.ink, width:1.5, type:'solid' } }, valueFormatter:fmt, ...tip(t) },
    xAxis:{ type:'category', data:labels, boundaryGap:false, axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:{ interval:2, ...axisLabel(t) } },
    yAxis:{ type:'value', scale:true, splitNumber:4, axisLabel:{ ...axisLabel(t), formatter:fmt }, splitLine:{ lineStyle:{ color:t.grid } } },
    series:[
      { name:'Last year', type:'line', data:prior, symbol:'none', lineStyle:{ color:t.prior, width:2, type:[6,5] }, itemStyle:{ color:t.prior },
        endLabel:{ show:true, formatter:'Last year ' + fmt(prior[prior.length - 1]), color:t.muted, fontSize:13, fontFamily:FONT, offset:[6,8] }, emphasis:{ disabled:true } },
      { name:'This year', type:'line', data:cur, symbol:'rect', showAllSymbol:true, symbolSize:(v, p) => (p.dataIndex === last ? 12 : 0),
        lineStyle:{ color:t.primary, width:4 }, itemStyle:{ color:t.primary },
        endLabel:{ show:true, formatter:'This year ' + fmt(cur[last]), color:t.ink, fontWeight:700, fontSize:13, fontFamily:FONT, offset:[8,0] }, emphasis:{ disabled:true } },
    ],
  };
}

// This year (solid, primary) against last year (grey dashed), labels at line ends
export function TwinTrend({ t, labels, cur, prior, fmt, motion, height, label }) {
  const option = useMemo(() => twinTrendOption(t, { labels, cur, prior, fmt, motion }), [t, labels, cur, prior, fmt, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
