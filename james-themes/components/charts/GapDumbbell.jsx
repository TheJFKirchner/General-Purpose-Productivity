import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, STATUS, base, tip, axisLabel, valAxis, valueLabel, shadowPointer } from './chartKit.js';

// rows = [{ name, actual, plan, lastYear }]. Each row is drawn as a percent of its own plan, so groups of different size compare fairly.
export function gapDumbbellOption(t, { rows, fmt = (v) => '$' + v, min = 90, max = 108, overIsBad = true, motion = true }) {
  const r = rows.slice().reverse(), ai = r.map((x) => +((x.actual / x.plan) * 100).toFixed(1)), li = r.map((x) => +((x.lastYear / x.plan) * 100).toFixed(1));
  const tone = (a) => ((a > 100) === overIsBad ? STATUS.badMark : STATUS.goodMark);
  return {
    ...base(motion), grid:{ left:4, right:70, top:34, bottom:2, containLabel:true },
    legend:{ top:0, left:0, itemWidth:12, itemHeight:12, textStyle:{ color:t.muted, fontSize:13, fontFamily:FONT }, selectedMode:false, data:['Last year', 'Actual'] },
    tooltip:tip(t, { trigger:'axis', axisPointer:shadowPointer, formatter:(ps) => { const x = r[ps[0].dataIndex]; return `<b>${x.name}</b><br>Actual ${fmt(x.actual)}<br>Plan ${fmt(x.plan)}<br>Last year ${fmt(x.lastYear)}`; } }),
    xAxis:valAxis(t, { min, max, interval:2, axisLabel:axisLabel(t, { formatter:(v) => (v === 100 ? 'Plan' : v) }) }),
    yAxis:{ type:'category', data:r.map((x) => x.name), axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:axisLabel(t, { color:t.ink, fontSize:13, width:150, overflow:'break' }) },
    series:[
      { type:'bar', stack:'g', silent:true, itemStyle:{ color:'transparent' }, data:ai.map((a) => Math.min(a, 100)) },
      { type:'bar', stack:'g', silent:true, barWidth:10, data:ai.map((a) => ({ value:Math.abs(a - 100), itemStyle:{ color:tone(a) } })),
        markLine:{ silent:true, symbol:'none', lineStyle:{ color:t.ink, width:2.5, type:'solid' }, label:{ show:false }, data:[{ xAxis:100 }] } },
      { name:'Last year', type:'scatter', data:li, symbol:'rect', symbolSize:[5, 20], itemStyle:{ color:t.prior }, z:4 },
      { name:'Actual', type:'scatter', data:ai, symbol:'circle', symbolSize:20, itemStyle:{ color:t.primary, borderColor:'#fff', borderWidth:2 }, z:6,
        label:valueLabel(t, { position:'right', distance:8, formatter:(p) => { const d = r[p.dataIndex].actual - r[p.dataIndex].plan; return (d > 0 ? '+' : '\u2212') + fmt(Math.abs(d)); } }) },
    ],
  };
}

// Actual against a target and a prior value, for groups of different size
export function GapDumbbell({ t, rows, fmt, min, max, overIsBad, motion, height = 260, label }) {
  const option = useMemo(() => gapDumbbellOption(t, { rows, fmt, min, max, overIsBad, motion }), [t, rows, fmt, min, max, overIsBad, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
