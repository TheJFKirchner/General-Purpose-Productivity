/* DEMO: the extra visual options of the in-page demo (what the Visualizer would return for each library and for
   design briefs), made-up hospital data. Each is one self-contained fragment that calls only its set's library:
   Chart.js (`Chart`), D3 (`d3`), ECharts styled like matplotlib (`echarts`), or no script at all (palette, hero). */
import { esc } from '../lib/markdown';

/** JSON for inline scripts (no "<" so nothing can close the script element). */
export const visJs = (v: unknown): string => JSON.stringify(v).replace(/</g, '\\u003c');

const PAL = ['#3B3FB6', '#E8664A', '#4BAE7F', '#7C80E0', '#F2B33D', '#22243A'];
const MPL = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'];       // matplotlib's default colour cycle
const FAC = [['North', 182], ['Riverside', 141], ['St Anne', 126], ['Hillcrest', 97], ['Bayview', 74], ['Elm Park', 52]] as const;

const note = (tweak: string): string => tweak ? `<div style="position:absolute;left:8px;bottom:4px;font-size:10px;color:#5E6278">Tweak: ${esc(tweak)}</div>` : '';

function chartjs(cfg: unknown, tweak: string): string {
  return `<div style="position:relative;height:100%;padding:6px 8px;box-sizing:border-box"><canvas id="c"></canvas>${note(tweak)}</div>` +
    `<script>new Chart(document.getElementById("c"),${visJs(cfg)});<\/script>`;
}

function d3frame(body: string, tweak: string): string {
  return `<div id="d" style="position:relative;height:100%"></div>${note(tweak)}<script>var data=${visJs(FAC.map(([k, v]) => ({ k, v })))},pal=${visJs(PAL)},W=520,H=240;` +
    'var svg=d3.select("#d").append("svg").attr("viewBox","0 0 "+W+" "+H).attr("width","100%").attr("height","100%").style("font","11px system-ui");' +
    body + '<\/script>';
}

/** The fragment for one demo option id, or null when Demo.visHtml draws it itself (the ECharts set and probes). */
export function visExtra(id: string, tweak: string, months: string[], rate: number[]): string | null {
  const horiz = /horizontal|sideways/i.test(tweak);
  switch (id) {
    case 'cj-doughnut':
      return chartjs({ type: 'doughnut', data: { labels: ['Home', 'Home with care', 'Rehab', 'Nursing home', 'Other'],
        datasets: [{ data: [38, 24, 17, 14, 7], backgroundColor: PAL.slice(0, 5), borderColor: '#fff', borderWidth: 2 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '58%', plugins: { legend: { position: 'right', labels: { boxWidth: 12 } },
          title: { display: true, text: 'Readmissions by discharge destination, %', align: 'start', color: '#22243A' } } } }, tweak);
    case 'cj-bars':
      return chartjs({ type: 'bar', data: { labels: ['Q1', 'Q2', 'Q3'], datasets: [
        { label: 'Home', data: [212, 205, 198], backgroundColor: PAL[0], borderRadius: 4 },
        { label: 'Rehab', data: [96, 101, 93], backgroundColor: PAL[1], borderRadius: 4 },
        { label: 'Nursing home', data: [81, 77, 84], backgroundColor: PAL[2], borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: horiz ? 'y' : 'x', plugins: { legend: { position: 'top', align: 'end', labels: { boxWidth: 12 } } } } }, tweak);
    case 'd3-bubble':
      return d3frame('var root=d3.pack().size([W,H]).padding(4)(d3.hierarchy({children:data}).sum(function(d){return d.v;}));' +
        'var g=svg.selectAll("g").data(root.leaves()).join("g").attr("transform",function(d){return "translate("+d.x+","+d.y+")";});' +
        'g.append("circle").attr("r",function(d){return d.r;}).attr("fill",function(d,i){return pal[i%pal.length];}).attr("fill-opacity",0.88);' +
        'g.append("text").attr("text-anchor","middle").attr("dy","-0.2em").attr("fill","#fff").attr("font-weight",600).text(function(d){return d.data.k;});' +
        'g.append("text").attr("text-anchor","middle").attr("dy","1.1em").attr("fill","#fff").text(function(d){return d.data.v;});', tweak);
    case 'd3-bars':
      return d3frame('var x=d3.scaleBand().domain(data.map(function(d){return d.k;})).range([40,W-10]).padding(0.25);' +
        'var y=d3.scaleLinear().domain([0,d3.max(data,function(d){return d.v;})]).nice().range([H-22,16]);' +
        'svg.append("g").attr("transform","translate(0,"+(H-22)+")").call(d3.axisBottom(x));' +
        'svg.append("g").attr("transform","translate(40,0)").call(d3.axisLeft(y).ticks(5));' +
        'svg.selectAll("rect.b").data(data).join("rect").attr("class","b").attr("x",function(d){return x(d.k);}).attr("y",function(d){return y(d.v);})' +
        '.attr("width",x.bandwidth()).attr("height",function(d){return H-22-y(d.v);}).attr("rx",3).attr("fill","#3B3FB6");' +
        'svg.selectAll("text.l").data(data).join("text").attr("class","l").attr("x",function(d){return x(d.k)+x.bandwidth()/2;})' +
        '.attr("y",function(d){return y(d.v)-4;}).attr("text-anchor","middle").attr("fill","#22243A").text(function(d){return d.v;});', tweak);
    case 'mpl-line':
    case 'mpl-bar': {
      const line = id === 'mpl-line', box = { show: true, lineStyle: { color: '#000' } };
      const ax = (o: Record<string, unknown>) => ({ ...o, axisLine: box, axisTick: { inside: false }, splitLine: { show: false }, axisLabel: { color: '#000' } });
      const opt = { backgroundColor: '#fff', color: MPL, textStyle: { fontFamily: 'DejaVu Sans, Verdana, sans-serif' },
        title: { text: '30-day readmission rate (%)', left: 'center', top: 4, textStyle: { fontSize: 12, fontWeight: 'normal', color: '#000' }, subtext: tweak ? 'Tweak: ' + tweak : '' },
        legend: { right: 16, top: 26, orient: 'vertical', borderColor: '#ccc', borderWidth: 1, data: ['2025', '2026'] },
        grid: { left: 44, right: 16, top: 34, bottom: 26 }, xAxis: ax({ type: 'category', data: months, boundaryGap: !line }), yAxis: ax({ type: 'value', min: line ? 10 : 0 }),
        series: [{ name: '2025', type: line ? 'line' : 'bar', data: rate.map(v => +(v + 0.6).toFixed(1)), symbol: 'circle', symbolSize: 6 },
          { name: '2026', type: line ? 'line' : 'bar', data: rate, symbol: 'circle', symbolSize: 6 }] };
      return '<div id="c" style="width:100%;height:100%"></div><script>var ch=echarts.init(document.getElementById("c"));ch.setOption(' + visJs(opt) + ');<\/script>';
    }
    case 'palette': {
      const sw = [['Indigo', '#3B3FB6'], ['Lilac', '#B9B7E6'], ['Coral', '#E8664A'], ['Green', '#4BAE7F'], ['Ground', '#F4F3FA'], ['Ink', '#22243A']]
        .map(([n, c]) => `<div style="min-width:0"><div style="height:48px;border-radius:10px;background:${c};border:1px solid #E4E3F0"></div>` +
          `<div style="font-size:12px;margin-top:4px;color:#22243A">${n}</div><div style="font:11px ui-monospace,monospace;color:#5E6278">${c}</div></div>`).join('');
      /* a wrapping grid: swatches drop to a new row instead of squeezing their hex codes together */
      return `<div style="padding:12px;font-family:system-ui,sans-serif"><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:10px 8px">${sw}</div>` +
        '<div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;background:#F4F3FA;padding:10px;border-radius:12px">' +
        '<span style="background:#3B3FB6;color:#fff;border-radius:999px;padding:7px 14px;font-weight:600;font-size:13px">Approve plan</span>' +
        '<span style="background:#fff;color:#3B3FB6;border:1px solid #B9B7E6;border-radius:999px;padding:7px 14px;font-size:13px">Send back</span>' +
        '<span style="color:#9C3520;font-size:12px;font-weight:600">2 cards need you</span><span style="color:#1F6B47;font-size:12px">Step 3 done</span></div>' +
        `${tweak ? `<div style="font-size:11px;color:#5E6278;margin-top:6px">Tweak: ${esc(tweak)}</div>` : ''}</div>`;
    }
    case 'hero':
      return '<div style="padding:10px;font-family:system-ui,sans-serif"><div style="border-radius:18px;padding:20px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;color:#fff;background:linear-gradient(135deg,#3B3FB6,#5A5ED0 60%,#7C80E0)">' +
        '<div style="flex:1 1 200px;min-width:0"><div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;opacity:.8">Q3 quality report</div>' +
        '<div style="font:700 22px/1.2 system-ui;margin:6px 0">Readmissions down to 12.6%</div>' +
        '<div style="font-size:13px;opacity:.9">Lowest in two years. Riverside and North drove most of the drop.</div>' +
        '<div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap"><span style="background:#E8664A;padding:7px 14px;border-radius:999px;font-weight:600;font-size:13px">Read the report</span>' +
        '<span style="border:1px solid rgba(255,255,255,.6);padding:7px 14px;border-radius:999px;font-size:13px">Download data</span></div>' +
        `${tweak ? `<div style="font-size:11px;opacity:.85;margin-top:8px">Tweak: ${esc(tweak)}</div>` : ''}</div>` +
        '<svg viewBox="0 0 100 100" style="width:96px;height:96px;flex:none"><circle cx="50" cy="50" r="38" fill="#B9B7E6"/><path d="M28 60 L42 46 L54 54 L72 34" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="72" cy="34" r="6" fill="#E8664A"/></svg></div></div>';
    default:
      return null;
  }
}
