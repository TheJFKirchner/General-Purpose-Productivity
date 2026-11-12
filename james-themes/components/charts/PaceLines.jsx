import { useMemo } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, base, tip, axisLabel, catAxis, valAxis, assumptionBand, eventMarks } from './chartKit.js';

// series = [{ key, name, data }]; lead = key drawn bold; band = { from, to }; events = [{ at, label }]
export function paceLinesOption(t, { labels, series, lead, band, events, fmt = (v) => v + '%', min = 0, max, motion = true }) {
  const leadKey = lead ?? series[0].key;
  return {
    ...base(motion), grid:{ left:4, right:160, top:14, bottom:2, containLabel:true },
    tooltip:tip(t, { trigger:'axis', valueFormatter:fmt }),
    xAxis:catAxis(t, labels, { boundaryGap:false, axisLabel:axisLabel(t, { interval:1 }) }),
    yAxis:valAxis(t, { min, max, axisLabel:axisLabel(t, { formatter:fmt }) }),
    series:series.map((s) => { const on = s.key === leadKey; return {
      name:s.name, type:'line', data:s.data, symbol:'none', z:on ? 5 : 2,
      lineStyle:{ color:on ? t.primary : t.dim, width:on ? 4 : 2 }, itemStyle:{ color:on ? t.primary : t.dim },
      endLabel:{ show:true, formatter:s.name + (on ? ' ' + fmt(s.data[s.data.length - 1]) : ''), color:on ? t.ink : t.muted, fontWeight:on ? 700 : 500, fontSize:12, fontFamily:FONT, offset:[6,0] },
      labelLayout:{ moveOverlap:'shiftY' }, emphasis:{ disabled:true },
      ...(on ? { ...assumptionBand(band), ...eventMarks(t, events, min + (max ?? 8) * 0.06) } : {}),
    }; }),
  };
}

// Rate of change over time, several smoothings, one leading; optional assumption band + event marks
export function PaceLines({ t, labels, series, lead, band, events, fmt, min, max, motion, height = 270, label }) {
  const option = useMemo(() => paceLinesOption(t, { labels, series, lead, band, events, fmt, min, max, motion }), [t, labels, series, lead, band, events, fmt, min, max, motion]);
  return <ChartMount option={option} height={height} label={label} />;
}
