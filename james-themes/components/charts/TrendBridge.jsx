import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { STATUS, base, axisLabel, catAxis, valAxis, valueLabel } from './chartKit.js';

// start/end = { name, value }; steps = [{ name, value }] (signed). upIsBad colors increases orange.
export function trendBridgeOption(t, { start, steps, end, fmt = (v) => '$' + v, min, max, upIsBad = true, motion = true }) {
  let run = start.value; const floor = [0], bars = [{ value:start.value, itemStyle:{ color:t.ink, borderRadius:[5,5,0,0] }, label:{ formatter:fmt(start.value) } }];
  steps.forEach((s) => { const up = s.value >= 0; floor.push(up ? run : run + s.value);
    bars.push({ value:Math.abs(s.value), itemStyle:{ color:up === upIsBad ? STATUS.badMark : STATUS.goodMark, borderRadius:[5,5,0,0] }, label:{ formatter:(up ? '+' : '\u2212') + fmt(Math.abs(s.value)) } }); run += s.value; });
  floor.push(0); bars.push({ value:end.value, itemStyle:{ color:t.ink, borderRadius:[5,5,0,0] }, label:{ formatter:fmt(end.value) } });
  return {
    ...base(motion), grid:{ left:4, right:8, top:24, bottom:2, containLabel:true },
    xAxis:catAxis(t, [start.name, ...steps.map((s) => s.name), end.name], { axisLabel:axisLabel(t, { color:t.ink, fontSize:13, interval:0 }) }),
    yAxis:valAxis(t, { min, max, axisLabel:axisLabel(t, { formatter:fmt }) }),
    series:[ { type:'bar', stack:'w', silent:true, itemStyle:{ color:'transparent' }, data:floor }, { type:'bar', stack:'w', barWidth:'52%', data:bars, label:valueLabel(t, { position:'top' }) } ],
  };
}

// Walk from a starting total to an ending total, one driver at a time
export function TrendBridge({ t, start, steps, end, fmt, min, max, upIsBad, motion, height = 280, label }) {
  const option = useMemo(() => trendBridgeOption(t, { start, steps, end, fmt, min, max, upIsBad, motion }), [t, start, steps, end, fmt, min, max, upIsBad, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
