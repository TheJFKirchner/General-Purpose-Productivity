import { useMemo, useState } from 'react';
import { ChartMount } from './ChartMount.jsx';
import { FONT, tip } from './chartKit.js';

// sources/targets = names; matrix[i][j] = amount from sources[i] to targets[j]; focus = hovered node name or null
export function flowRibbonOption(t, { sources, targets, matrix, fmt = (v) => '$' + v + 'M', focus = null }) {
  const si = sources.indexOf(focus), ti = targets.indexOf(focus);
  const sTot = matrix.map((r) => r.reduce((a, b) => a + b, 0)), tTot = targets.map((_, j) => matrix.reduce((a, r) => a + r[j], 0));
  const amount = (name) => { const i = sources.indexOf(name), j = targets.indexOf(name);
    if (si >= 0) return i >= 0 ? (i === si ? sTot[i] : null) : matrix[si][j];
    if (ti >= 0) return j >= 0 ? (j === ti ? tTot[j] : null) : matrix[i][ti];
    return i >= 0 ? sTot[i] : tTot[j]; };
  const lit = (i, j) => (si >= 0 ? i === si : ti >= 0 ? j === ti : false);
  return {
    animation:false, textStyle:{ fontFamily:FONT },
    tooltip:tip(t, { formatter:(p) => (p.dataType === 'edge' ? `<b>${p.data.source} \u2192 ${p.data.target}</b><br>${fmt(p.data.value)}` : `<b>${p.name}</b><br>${fmt(p.value)} in total`) }),
    series:[{ type:'sankey', left:200, right:170, top:8, bottom:8, nodeWidth:14, nodeGap:16, draggable:false, emphasis:{ disabled:true }, levels:[{ depth:0, label:{ position:'left' } }],
      data:[...sources.map((n) => ({ name:n, itemStyle:{ color:t.ink, opacity:focus && amount(n) == null ? 0.3 : 1 } })), ...targets.map((n, j) => ({ name:n, itemStyle:{ color:t.cat[(j % 4) + 1], opacity:focus && amount(n) == null ? 0.3 : 1 } }))],
      links:matrix.flatMap((row, i) => row.map((v, j) => ({ source:sources[i], target:targets[j], value:v, lineStyle:{ color:lit(i, j) ? t.primary : t.prior, opacity:lit(i, j) ? 0.7 : focus ? 0.08 : 0.28 } }))),
      label:{ fontFamily:FONT, fontSize:13, fontWeight:600, formatter:(p) => { const a = amount(p.name); return a == null ? p.name : `${p.name}  ${fmt(a)}`; }, color:t.ink },
    }],
  };
}

// A total split two ways at once. Hover a name on either side: the other side re-reads as that name's amounts only.
export function FlowRibbon({ t, sources, targets, matrix, fmt, height = 340, label }) {
  const [focus, setFocus] = useState(null);
  const option = useMemo(() => flowRibbonOption(t, { sources, targets, matrix, fmt, focus }), [t, sources, targets, matrix, fmt, focus]);
  const onEvents = useMemo(() => ({
    mouseover:(p) => { if (p.dataType === 'node') setFocus(p.name); },
    mouseout:(p) => { if (p.dataType === 'node') setFocus(null); },
    globalout:() => setFocus(null),
  }), []);
  return (
    <div>
      <ChartMount option={option} height={height} label={label} onEvents={onEvents} />
      <p style={{ margin:'6px 0 0', minHeight:18, fontSize:13, fontWeight:600, color:'var(--primary)' }} aria-live="polite">{focus ? `Showing amounts for ${focus} only` : 'Hover a name on either side to isolate it'}</p>
    </div>
  );
}
