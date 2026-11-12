import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip } from './chartKit.js';

// rows = [{ name, ranks:[one per period], note? }]; rank 1 is drawn on top; highlight = name drawn in primary
export function rankClimbOption(t, { periods, rows, highlight, motion = true }) {
  const worst = Math.max(...rows.flatMap((r) => r.ranks));
  return {
    ...base(motion), grid:{ left:120, right:176, top:20, bottom:48 },
    tooltip:tip(t, { trigger:'item', formatter:(p) => `<b>${p.seriesName}</b><br>${p.name}: rank ${p.value}` }),
    xAxis:{ type:'category', data:periods, boundaryGap:false, axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:{ color:t.ink, fontSize:13, fontWeight:600, fontFamily:FONT, margin:22 } },
    yAxis:{ type:'value', inverse:true, min:1, max:worst, show:false },
    series:rows.map((r) => { const hot = r.name === highlight, moved = r.ranks[0] !== r.ranks[r.ranks.length - 1], c = hot ? t.primary : moved ? t.prior : t.dim;
      return { name:r.name, type:'line', data:r.ranks, smooth:0.35, symbol:'circle', symbolSize:30, z:hot ? 5 : 2, lineStyle:{ color:c, width:hot ? 7 : 5 }, itemStyle:{ color:c, borderColor:'#fff', borderWidth:2 }, emphasis:{ focus:'series' },
        label:{ show:true, position:'inside', color:hot ? '#fff' : t.ink, fontSize:13, fontWeight:700, fontFamily:FONT, formatter:'{c}' },
        endLabel:{ show:true, formatter:r.name + (r.note ? '  ' + r.note : ''), color:t.ink, fontSize:13, fontWeight:hot ? 700 : 500, fontFamily:FONT, offset:[14, 0] },
        markPoint:{ silent:true, symbol:'rect', symbolSize:1, itemStyle:{ color:'transparent' }, label:{ show:true, position:'left', distance:24, formatter:r.name, color:hot ? t.ink : t.muted, fontSize:13, fontWeight:hot ? 700 : 500, fontFamily:FONT }, data:[{ coord:[periods[0], r.ranks[0]] }] } }; }),
  };
}

// How the rank order of groups shifts across periods
export function RankClimb({ t, periods, rows, highlight, motion, height = 400, label }) {
  const option = useMemo(() => rankClimbOption(t, { periods, rows, highlight, motion }), [t, periods, rows, highlight, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
