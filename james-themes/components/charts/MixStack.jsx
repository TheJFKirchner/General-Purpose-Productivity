import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, tip } from './chartKit.js';

// series = { CategoryName: [value per column] }; order = bottom to top; max 5 (t.cat length)
export function mixStackOption(t, { labels, series, max, fmt = (v) => '$' + v, motion = true }) {
  const keys = Object.keys(series), top = keys.length - 1;
  return {
    animation:motion, animationDuration:900, textStyle:{ fontFamily:FONT },
    grid:{ left:8, right:16, top:44, bottom:4, containLabel:true },
    legend:{ top:0, left:0, itemWidth:12, itemHeight:12, icon:'rect', textStyle:{ color:t.muted, fontSize:13, fontFamily:FONT }, selectedMode:false },
    tooltip:{ trigger:'item', formatter:(p) => `<b>${p.seriesName} \u00B7 ${p.name}</b><br>${fmt(p.value)}`, ...tip(t) },
    xAxis:{ type:'category', data:labels, axisLine:{ lineStyle:{ color:t.ink, width:1.5 } }, axisTick:{ show:false }, axisLabel:{ color:t.muted, fontSize:13, fontFamily:FONT } },
    yAxis:{ type:'value', show:false, max },
    series:keys.map((k, i) => ({
      name:k, type:'bar', stack:'s', barWidth:'48%', data:series[k], emphasis:{ focus:'series' },
      itemStyle:{ color:t.cat[i], borderColor:'#FFFFFF', borderWidth:1.5, ...(i === top ? { borderRadius:[7,7,0,0] } : {}) },
      ...(i === top ? { label:{ show:true, position:'top', color:t.ink, fontWeight:700, fontSize:13, fontFamily:FONT,
        formatter:(p) => fmt(keys.reduce((a, kk) => a + series[kk][p.dataIndex], 0)) } } : {}),
    })),
  };
}

// Stacked columns with totals on top; hovering a category dims the rest
export function MixStack({ t, labels, series, max, fmt, motion, height, label }) {
  const option = useMemo(() => mixStackOption(t, { labels, series, max, fmt, motion }), [t, labels, series, max, fmt, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
