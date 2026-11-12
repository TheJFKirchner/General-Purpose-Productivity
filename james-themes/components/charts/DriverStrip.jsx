import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip } from './chartKit.js';

// parts = [{ name, value }] (max 5, colored by t.cat); shows each part's share of the total
export function driverStripOption(t, { parts, fmt = (v) => '$' + v, motion = true }) {
  const total = parts.reduce((a, p) => a + p.value, 0), share = (v) => Math.round((v / total) * 100) + '%';
  return {
    ...base(motion), grid:{ left:4, right:44, top:54, bottom:30 },
    legend:{ top:0, left:0, itemWidth:12, itemHeight:12, icon:'rect', textStyle:{ color:t.muted, fontSize:13, fontFamily:FONT }, selectedMode:false },
    tooltip:tip(t, { formatter:(p) => `<b>${p.seriesName}</b><br>${fmt(p.value)} of ${fmt(total)} (${share(p.value)})` }),
    xAxis:{ type:'value', max:total, show:false }, yAxis:{ type:'category', data:['x'], show:false },
    series:parts.map((p, i) => { const slim = p.value / total < 0.07; return {
      name:p.name, type:'bar', stack:'s', barWidth:64, data:[p.value], itemStyle:{ color:t.cat[i], borderColor:'#fff', borderWidth:2 }, emphasis:{ focus:'series' },
      label:{ show:true, position:slim ? 'right' : 'inside', fontFamily:FONT, fontSize:16, fontWeight:700, color:i >= 2 ? t.ink : '#fff', formatter:(x) => share(x.value) } }; }),
  };
}

// One bar adding to 100 percent: what a total or a change is made of
export function DriverStrip({ t, parts, fmt, motion, height = 200, label }) {
  const option = useMemo(() => driverStripOption(t, { parts, fmt, motion }), [t, parts, fmt, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
