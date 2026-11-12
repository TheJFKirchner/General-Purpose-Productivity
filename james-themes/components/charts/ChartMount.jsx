import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

// Only file that imports echarts. onEvents = { mouseover: fn, ... }. highlight = data name to emphasize (or null)
export function ChartMount({ option, height = 230, label, onEvents, highlight }) {
  const el = useRef(null), chart = useRef(null);
  useEffect(() => {
    chart.current = echarts.init(el.current, null, { renderer:'svg' });
    const ro = new ResizeObserver(() => chart.current && chart.current.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); chart.current.dispose(); chart.current = null; };
  }, []);
  useEffect(() => { chart.current.setOption(option, true); }, [option]);
  useEffect(() => {
    if (!onEvents) return undefined;
    const c = chart.current, entries = Object.entries(onEvents);
    entries.forEach(([k, fn]) => c.on(k, fn));
    return () => entries.forEach(([k, fn]) => c.off(k, fn));
  }, [onEvents]);
  useEffect(() => {
    if (highlight === undefined) return;
    chart.current.dispatchAction({ type:'downplay', seriesIndex:0 });
    if (highlight) chart.current.dispatchAction({ type:'highlight', seriesIndex:0, name:highlight });
  }, [highlight, option]);
  return <div ref={el} style={{ height }} role="img" aria-label={label} />;
}
