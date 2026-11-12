import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { STATUS, base, tip, axisLabel, catAxis, valAxis, valueLabel } from './chartKit.js';

// monthly = each period's amount over (+) or under (-) target; the line is the running total
export function planDriftOption(t, { labels, monthly, fmt = (v) => '$' + v, endNote = 'year to date', overIsBad = true, motion = true }) {
  const run = []; monthly.reduce((s, v) => { run.push(s + v); return s + v; }, 0);
  const sign = (v) => (v < 0 ? '\u2212' : '+') + fmt(Math.abs(v)), last = monthly.length - 1;
  return {
    ...base(motion), grid:{ left:4, right:110, top:14, bottom:2, containLabel:true },
    tooltip:tip(t, { trigger:'axis', formatter:(ps) => { const i = ps[0].dataIndex; return `<b>${labels[i]}</b><br>This period ${sign(monthly[i])}<br>Running total <b>${sign(run[i])}</b>`; } }),
    xAxis:catAxis(t, labels, { axisLabel:axisLabel(t, { interval:0 }) }),
    yAxis:valAxis(t, { axisLabel:axisLabel(t, { formatter:(v) => (v < 0 ? '\u2212' : '') + fmt(Math.abs(v)) }) }),
    series:[
      { type:'bar', barWidth:'55%', data:monthly.map((v) => ({ value:v, itemStyle:{ color:(v > 0) === overIsBad ? STATUS.badSoft : STATUS.goodSoft } })) },
      { type:'line', step:'middle', data:run, symbol:'rect', showAllSymbol:true, symbolSize:(v, p) => (p.dataIndex === last ? 11 : 0), lineStyle:{ color:t.ink, width:3.5 }, itemStyle:{ color:t.ink },
        endLabel:valueLabel(t, { formatter:`${sign(run[last])}\n${endNote}`, lineHeight:16, offset:[6,0] }), emphasis:{ disabled:true },
        markLine:{ silent:true, symbol:'none', lineStyle:{ color:t.ink, width:1.5, type:'solid' }, label:{ show:false }, data:[{ yAxis:0 }] } },
    ],
  };
}

// Gap to a target accumulating over time; shows when it started to open
export function PlanDrift({ t, labels, monthly, fmt, endNote, overIsBad, motion, height = 260, label }) {
  const option = useMemo(() => planDriftOption(t, { labels, monthly, fmt, endNote, overIsBad, motion }), [t, labels, monthly, fmt, endNote, overIsBad, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
