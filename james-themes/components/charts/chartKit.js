// Shared by every chart. Colors come from the theme object `t` only.
export const FONT = "'Barlow', system-ui, sans-serif";
export const STATUS = { goodMark:'#00B85C', badMark:'#FF8A00', goodSoft:'#B5EBCD', badSoft:'#FFD9A8', goodText:'#00703C' }; // marks = --goodMark / --badMark in foundation/groundwork.css
export const tip = (t, extra = {}) => ({
  backgroundColor:'#FFFFFF', borderColor:t.ink, borderWidth:1.5, padding:[8,12],
  textStyle:{ color:t.ink, fontSize:13, fontFamily:FONT },
  extraCssText:`box-shadow:4px 4px 0 ${t.ink};border-radius:3px;`, ...extra,
});
export const axisLabel = (t, extra = {}) => ({ color:t.muted, fontSize:12, fontFamily:FONT, ...extra });
export const catAxis = (t, data, extra = {}) => ({ type:'category', data, axisLine:{ show:false }, axisTick:{ show:false }, axisLabel:axisLabel(t), ...extra });
export const valAxis = (t, extra = {}) => ({ type:'value', axisLabel:axisLabel(t), splitLine:{ lineStyle:{ color:t.grid } }, ...extra });
export const valueLabel = (t, extra = {}) => ({ show:true, color:t.ink, fontSize:13, fontWeight:700, fontFamily:FONT, ...extra });
export const shadowPointer = { type:'shadow', shadowStyle:{ color:'rgba(10,31,92,0.06)' } };
export const soft = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
export const base = (motion = true) => ({ animation:motion, animationDuration:800, textStyle:{ fontFamily:FONT } });

// FEATURE helpers (spread into a series)
// AssumptionBand: shaded target range on a value axis. band = { from, to }
export const assumptionBand = (band) => (band ? { markArea:{ silent:true, itemStyle:{ color:soft(STATUS.goodMark, 0.14) }, label:{ show:false }, data:[[{ yAxis:band.from }, { yAxis:band.to }]] } } : {});
// EventMarks: labeled vertical lines at category positions. events = [{ at:'Jul', label:'Fee schedule change' }]; yAt = value where the label sits
export const eventMarks = (t, events = [], yAt = 0) => (events.length ? {
  markLine:{ silent:true, symbol:'none', lineStyle:{ color:t.ink, width:1.5, type:'solid' }, label:{ show:false }, data:events.map((e) => ({ xAxis:e.at })) },
  markPoint:{ silent:true, symbol:'rect', symbolSize:1, itemStyle:{ color:'transparent' },
    label:{ show:true, position:'right', distance:6, color:t.ink, fontSize:12, fontWeight:700, fontFamily:FONT, backgroundColor:'#fff', padding:[2,4], formatter:(p) => p.name },
    data:events.map((e) => ({ name:e.label, coord:[e.at, yAt] })) },
} : {});
// EstimateStyle: dashed, lighter fill for values that are not final yet
export const estimateStyle = (t) => ({ color:soft(t.primary, 0.14), borderColor:t.primary, borderWidth:1.5, borderType:'dashed', borderRadius:[5,5,0,0] });
