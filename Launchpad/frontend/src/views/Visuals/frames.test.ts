// @vitest-environment happy-dom
/* The visual frames keep the vanilla security model: frame CSP, sandbox, no meta refresh, script-safe library,
   replies matched to the sending frame, and the stand-in renderer works on its own. */
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { clampVisHeight, VIS_BASE_CSS, VIS_GUARD, VIS_MAX_H, VIS_MIN_H } from './frames';
import { createVisFrame, ECHARTS_STAND_IN, getVisProbe, LIB_PART, libName, libUrl, onVisMessage, scriptSafe, VIS_CSP, visLib, visSrcdoc } from './frames';
import { libLabel } from './Visuals';

describe('visual frames', () => {
  beforeAll(async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new Error('no server in tests')));
    const l = await visLib();
    expect(l.stub).toBe(true);                    // no /vendor/echarts.min.js -> the stand-in
    vi.unstubAllGlobals();
  });

  it('builds a srcdoc with the frame CSP, the guard, and no meta refresh', () => {
    const doc = visSrcdoc('<meta http-equiv="refresh" content="0;url=https://example.com"><p>hi</p>', { code: 'var x=1;', stub: true });
    expect(doc).toContain(`<meta http-equiv="Content-Security-Policy" content="${VIS_CSP}">`);
    expect(doc.indexOf('Content-Security-Policy')).toBeLessThan(doc.indexOf('<script>'));
    expect(doc).toContain('<base target="_top">');
    expect(doc).not.toMatch(/http-equiv="refresh"/i);
    expect(doc).toContain('<p>hi</p>');
    expect(doc).toContain('lpVisual:1');
    expect(doc).toContain('stand-in renderer');
    expect(VIS_CSP).toContain("default-src 'none'");
    expect(VIS_CSP).toContain("connect-src 'none'");
    expect(VIS_CSP).toContain("form-action 'none'");
  });

  it('escapes closing script tags in the inlined library', () => {
    expect(scriptSafe('a</script>b</SCRIPT>c')).toBe('a<\\/script>b<\\/script>c');
    expect(scriptSafe('x="<!--"')).toBe('x="<\\!--"');
  });

  it('fetches each library from /vendor/lib; installed ones carry the code and the folder', () => {
    expect(libUrl('chartjs', 'd1', '?port=1&code=abc')).toBe('/vendor/lib/chartjs.js');
    expect(libUrl('echarts', null, '?code=abc')).toBe('/vendor/lib/echarts.js');
    expect(libUrl('plotly', 'd1', '?port=1&code=abc')).toBe('/vendor/lib/plotly.js?code=abc&dir=d1');
    expect(libUrl('bokeh', null, '')).toBe('/vendor/lib/bokeh.js');
    expect(libName('chartjs')).toBe('Chart.js');
    expect(libName(null)).toBe('ECharts');
    expect(libName('matplotlib')).toBe('matplotlib');
  });

  it('inlines only the option\'s library; several files get one script tag each; missing ones show a note', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', (u: string) => {
      urls.push(u);
      if (u.includes('bokeh')) return Promise.resolve(new Response('/*BOKEH-CORE*/var Bokeh={};' + ' '.repeat(3000) + LIB_PART + "'use strict';/*BOKEH-API*/" + ' '.repeat(10), { headers: { 'content-type': 'application/javascript' } }));
      if (u.includes('d3')) return Promise.resolve(new Response('/*D3-LIB*/var d3={};' + ' '.repeat(3000), { headers: { 'content-type': 'application/javascript' } }));
      if (u.includes('chartjs')) return Promise.resolve(new Response('<!doctype html><html></html>', { headers: { 'content-type': 'text/html' } }));
      return Promise.reject(new Error('offline'));
    });
    const d3 = await visLib('d3');
    expect(d3.stub).toBe(false);
    const doc = visSrcdoc('<div id="d"></div>', d3);
    expect(doc).toContain('/*D3-LIB*/');
    expect(doc).not.toContain('echartsStandIn');
    expect(doc.match(/<script>/g)).toHaveLength(2);                  // the library + the guard
    const bk = await visLib('bokeh', 'd2');
    const bdoc = visSrcdoc('<div id="b"></div>', bk);
    expect(bdoc.match(/<script>/g)).toHaveLength(3);                 // core, plotting API, guard
    expect(bdoc.indexOf('BOKEH-CORE')).toBeLessThan(bdoc.indexOf('BOKEH-API'));
    expect(bdoc).toContain("<script>'use strict';/*BOKEH-API*/");    // the API keeps its own strict mode
    const cj = await visLib('chartjs');                              // a dev server's index page is never inlined
    expect(cj.stub).toBe(true);
    const cdoc = visSrcdoc('<canvas></canvas>', cj);
    expect(cdoc).toContain('Chart.js is not loaded here');
    expect(cdoc).not.toContain('<!doctype html><html></html>');
    expect(cdoc.match(/<script>/g)).toHaveLength(1);                 // only the guard
    expect(urls.some(u => u.startsWith('/vendor/lib/bokeh.js') && u.includes('dir=d2'))).toBe(true);
    const f = createVisFrame('<div id="d"></div>', { onBlocked: () => {} }, 'd3');
    document.body.append(f.iframe);
    expect(f.iframe.srcdoc).toContain('/*D3-LIB*/');               // cached library: set at once
    expect(f.iframe.getAttribute('sandbox')).toBe('allow-scripts');
    expect(f.iframe.srcdoc).toContain(VIS_CSP);
    f.dispose();
    vi.unstubAllGlobals();
  });

  it('makes sandboxed frames with allow-scripts only and routes messages by source window', () => {
    const errs: string[] = [];
    const a = createVisFrame('<p>a</p>', { onBlocked: () => {}, onError: m => errs.push('a:' + m) });
    const b = createVisFrame('<p>b</p>', { onBlocked: () => {}, onError: m => errs.push('b:' + m) });
    document.body.append(a.iframe, b.iframe);
    expect(a.iframe.getAttribute('sandbox')).toBe('allow-scripts');
    expect(a.iframe.getAttribute('referrerpolicy')).toBe('no-referrer');
    const winB = b.iframe.contentWindow;
    if (winB) {
      onVisMessage({ data: { lpVisual: 1, kind: 'error', msg: 'boom' }, source: winB });
      expect(errs).toEqual(['b:boom']);
    }
    onVisMessage({ data: { lpVisual: 1, kind: 'error', msg: 'stranger' }, source: null });
    onVisMessage({ data: { kind: 'error', msg: 'not ours' }, source: winB });
    expect(errs.filter(e => e.includes('stranger') || e.includes('not ours'))).toHaveLength(0);
    onVisMessage({ data: { lpVisual: 1, kind: 'probe', results: ['read parent page: blocked'] }, source: null });
    expect(getVisProbe()).toEqual(['read parent page: blocked']);
    a.dispose(); b.dispose();
    expect(a.iframe.isConnected).toBe(false);
  });

  it('labels every drawn option with its library (ECharts too); design html is "HTML and CSS"; a fallback says "styled like"', () => {
    const base = { libraries: ['echarts', 'chartjs', 'd3'] };
    const ec = { ...base, library: null, drawn_with: 'echarts', library_note: null };
    expect(libLabel(ec)).toBeNull();                                  // still rendering, nothing asked
    expect(libLabel(ec, '<div id="c"></div><script>echarts.init(c)</script>')?.text).toBe('Drawn with ECharts');
    expect(libLabel(ec, '<div style="display:grid">swatches</div>')?.text).toBe('HTML and CSS');
    expect(libLabel({ ...base, library: 'chartjs', drawn_with: 'chartjs', library_note: null }))
      .toEqual({ text: 'Drawn with Chart.js', tip: 'Available for this folder: ECharts, Chart.js, D3', fallback: false });
    expect(libLabel({ ...base, library: 'matplotlib', drawn_with: 'echarts', library_note: 'drawn in ECharts, styled like matplotlib' }))
      .toMatchObject({ text: 'Drawn in ECharts, styled like matplotlib', fallback: true });
  });

  it('frames report their content height and readiness through the matched postMessage channel, clamped', () => {
    expect(VIS_GUARD).toContain("post('size'");
    expect(VIS_GUARD).toContain("post('ready')");
    expect(VIS_BASE_CSS).toContain('overflow-wrap:break-word');
    expect(clampVisHeight(340)).toBe(340);
    expect(clampVisHeight(99999)).toBe(VIS_MAX_H);
    expect(clampVisHeight(3)).toBe(VIS_MIN_H);
    expect(clampVisHeight('nope')).toBeNull();
    expect(clampVisHeight(-5)).toBeNull();
    const sizes: number[] = [], ready: string[] = [];
    const a = createVisFrame('<p>a</p>', { onBlocked: () => {}, onSize: h => sizes.push(h), onReady: () => ready.push('a') });
    document.body.append(a.iframe);
    const win = a.iframe.contentWindow;
    if (win) {
      onVisMessage({ data: { lpVisual: 1, kind: 'size', h: 412 }, source: win });
      onVisMessage({ data: { lpVisual: 1, kind: 'size', h: 1e9 }, source: win });
      onVisMessage({ data: { lpVisual: 1, kind: 'ready' }, source: win });
      expect(sizes).toEqual([412, VIS_MAX_H]);
      expect(ready).toContain('a');
    }
    onVisMessage({ data: { lpVisual: 1, kind: 'size', h: 500 }, source: null });   // a stranger: ignored
    expect(sizes).not.toContain(500);
    a.dispose();
  });

  it('stand-in draws bars and a line as SVG', () => {
    const w = window as unknown as { echarts?: { init: (d: Element) => { setOption: (o: unknown) => void } } };
    new Function('(' + ECHARTS_STAND_IN + ')();')();
    const dom = document.createElement('div'); document.body.appendChild(dom);
    w.echarts!.init(dom).setOption({ title: { text: 'T' }, xAxis: { type: 'category', data: ['a', 'b'] }, yAxis: { type: 'value' },
      series: [{ type: 'bar', data: [1, 2] }, { type: 'line', name: 'L', data: [2, { value: 1 }] }] });
    expect(dom.querySelectorAll('svg rect').length).toBeGreaterThanOrEqual(2);
    expect(dom.querySelector('svg polyline')).toBeTruthy();
    expect(dom.textContent).toContain('T');
  });
});
