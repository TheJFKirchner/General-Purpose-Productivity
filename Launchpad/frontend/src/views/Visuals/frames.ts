/* Sandboxed frames for the visual options (vanilla prototype/launchpad-orbit.html 2678-2799). Security model, kept exactly:
   - <iframe sandbox="allow-scripts"> (no allow-same-origin -> opaque origin, cannot touch this page;
     no allow-top-navigation / allow-forms / allow-popups / allow-modals)
   - a Content-Security-Policy inside the frame (VIS_CSP): default-src 'none' (no network at all: no fetch, no images or
     fonts from URLs, no frames, no form posts); inline scripts and styles only
   - the frame gets only the library its option needs (drawn_with: echarts | chartjs | d3 | plotly | bokeh), inlined:
     the page fetches GET /vendor/lib/<key>.js once per library (installed ones, Plotly / Bokeh, with the access code
     and the session's folder) and inlines it, so the frame needs no network. A library made of several files arrives
     joined by LIB_PART and gets one script tag per file. Without the server (npm run dev, or opened as a file) a
     tiny built-in stand-in draws ECharts bar/line charts; other libraries show a "not loaded" note
   - if a frame ever loads a second document (it navigated itself), onBlocked fires: the caller removes it and marks
     the option blocked
   - frames talk to the page only by postMessage {lpVisual:1, kind}; messages are matched to their frame by
     contentWindow === event.source and only ever shown as text
   Frames are created imperatively and never moved or re-attached (that would reload them). */

export const VIS_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; " +
  "connect-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; object-src 'none'; media-src 'none'; form-action 'none'; base-uri 'none'";
/* box-sizing + overflow-wrap so narrow labels (palette hex codes, captions) wrap instead of running together */
export const VIS_BASE_CSS = "html,body{margin:0;height:100%;background:#fff;color:#22243A;font:13px system-ui,-apple-system,'Segoe UI',sans-serif}" +
  "*,*::before,*::after{box-sizing:border-box}body{overflow-x:hidden;overflow-y:auto;overflow-wrap:break-word}" +
  "svg:not(:root),canvas{vertical-align:top}" +
  ".lp-stub{position:fixed;right:6px;bottom:4px;font-size:10px;color:#8A8DA3;background:rgba(255,255,255,.85);padding:1px 5px;border-radius:6px;pointer-events:none}";
/* The frame's guard: reports script errors, 'ready' on load, and its content height ('size', h) so the page can make the
   frame as tall as the drawing (re-checked for a few seconds after load and on resize, only when it overflows and
   changed, at most 40 times). A drawing sized in % of the frame that still overflows by the same amount after the frame
   grew would grow forever: the guard stops reporting then. Messages go to the parent only; the page matches them to
   this frame by contentWindow and clamps h. */
export const VIS_GUARD = "(function(){function post(k,m,h){try{parent.postMessage({lpVisual:1,kind:k,msg:String(m||'').slice(0,300),h:h||0},'*')}catch(e){}}" +
  "var last=0,n=0,lastVh=0,lastOver=-1,stop=false;function report(){if(stop)return;var d=document.documentElement,b=document.body,vh=window.innerHeight;" +
  "var h=Math.ceil(Math.max(d?d.scrollHeight:0,b?b.scrollHeight:0)),over=h-vh;if(!h||over<=2)return;" +
  "if(lastVh&&vh!==lastVh&&Math.abs(over-lastOver)<=2){stop=true;return}" +
  "if(Math.abs(h-last)>2&&n<40){last=h;lastVh=vh;lastOver=over;n++;post('size','',h)}}" +
  "window.addEventListener('error',function(e){post('error',e.message||'script error')});" +
  "window.addEventListener('unhandledrejection',function(e){post('error',(e.reason&&e.reason.message)||'promise rejected')});" +
  "window.addEventListener('resize',function(){report();if(!window.echarts)return;var els=document.querySelectorAll('[_echarts_instance_]');" +
  "for(var i=0;i<els.length;i++){var c=echarts.getInstanceByDom(els[i]);if(c&&c.resize)c.resize()}});" +
  "window.addEventListener('load',function(){post('ready');report();var t=0,iv=setInterval(function(){report();if(++t>25)clearInterval(iv)},200)})})();";
/** Frame heights the page accepts from a frame's size report (px). */
export const VIS_MIN_H = 80, VIS_MAX_H = 900;
export const clampVisHeight = (h: unknown): number | null => {
  const n = Number(h);
  return Number.isFinite(n) && n > 0 ? Math.round(Math.min(VIS_MAX_H, Math.max(VIS_MIN_H, n))) : null;
};

/* Stand-in for ECharts when /vendor/echarts.min.js is not available: bar, stacked bar, horizontal bar and line only.
   Kept as frame source text (vanilla echartsStandIn, line 2701) rather than a page function, so no bundler transform
   can change what runs inside the frame. */
export const ECHARTS_STAND_IN = `function echartsStandIn() {
  var NS = 'http://www.w3.org/2000/svg', PAL = ['#3B3FB6', '#E8664A', '#4BAE7F', '#B9B7E6', '#22243A', '#7E81D8'];
  function el(t, a, txt) { var e = document.createElementNS(NS, t); for (var k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; return e; }
  function val(d) { return typeof d === 'object' && d ? +d.value : +d; }
  function Chart(dom) { this.dom = dom; dom.setAttribute('_echarts_instance_', 'standin'); dom.__lpChart = this; }
  Chart.prototype.setOption = function (o) { this.o = o; this.draw(); };
  Chart.prototype.resize = function () { if (this.o) this.draw(); };
  Chart.prototype.dispose = function () { this.dom.innerHTML = ''; };
  Chart.prototype.on = function () {};
  Chart.prototype.draw = function () {
    var o = this.o || {}, dom = this.dom, W = dom.clientWidth || 300, H = dom.clientHeight || 200;
    var xa = [].concat(o.xAxis || {})[0] || {}, ya = [].concat(o.yAxis || {})[0] || {}, horiz = ya.type === 'category';
    var cats = (horiz ? ya.data : xa.data) || [], series = [].concat(o.series || []).filter(function (s) { return s && (s.type === 'bar' || s.type === 'line'); });
    var colors = o.color || PAL, stacked = series.some(function (s) { return s.stack; });
    var max = 0;
    cats.forEach(function (_, i) {
      var sum = 0; series.forEach(function (s) { var v = val((s.data || [])[i]) || 0; if (stacked && s.type === 'bar') sum += v; else max = Math.max(max, v); }); max = Math.max(max, sum);
    });
    max = max || 1;
    var title = o.title && o.title.text, top = title ? 30 : 14, L = horiz ? 64 : 36, R = 12, B = 26, T = top + (series.length > 1 ? 16 : 0);
    var svg = el('svg', { width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, style: 'display:block;font:11px system-ui' });
    if (title) svg.appendChild(el('text', { x: 8, y: 18, 'font-weight': 600, fill: '#22243A' }, title));
    if (series.length > 1) series.forEach(function (s, k) { var x = 8 + k * 110; svg.appendChild(el('rect', { x: x, y: top - 2, width: 10, height: 8, fill: colors[k % colors.length] })); svg.appendChild(el('text', { x: x + 14, y: top + 6, fill: '#5E6278' }, s.name || 'Series ' + (k + 1))); });
    var pw = W - L - R, ph = H - T - B, n = Math.max(cats.length, 1);
    svg.appendChild(el('line', { x1: L, y1: T + ph, x2: L + pw, y2: T + ph, stroke: '#D9D8EC' }));
    svg.appendChild(el('line', { x1: L, y1: T, x2: L, y2: T + ph, stroke: '#D9D8EC' }));
    cats.forEach(function (c, i) {
      if (horiz) svg.appendChild(el('text', { x: L - 6, y: T + (i + .5) * ph / n + 4, 'text-anchor': 'end', fill: '#5E6278' }, c));
      else if (n <= 12 || i % 2 === 0) svg.appendChild(el('text', { x: L + (i + .5) * pw / n, y: H - 8, 'text-anchor': 'middle', fill: '#5E6278' }, c));
    });
    var bars = series.filter(function (s) { return s.type === 'bar'; }), groups = stacked ? 1 : Math.max(bars.length, 1);
    var base = cats.map(function () { return 0; });
    series.forEach(function (s, k) {
      var col = (s.itemStyle && s.itemStyle.color) || colors[k % colors.length], data = s.data || [];
      if (s.type === 'line') {
        var pts = data.map(function (d, i) { return (L + (i + .5) * pw / n).toFixed(1) + ',' + (T + ph - val(d) / max * ph).toFixed(1); });
        svg.appendChild(el('polyline', { points: pts.join(' '), fill: 'none', stroke: col, 'stroke-width': 2.5, 'stroke-linejoin': 'round' }));
        data.forEach(function (d, i) { svg.appendChild(el('circle', { cx: L + (i + .5) * pw / n, cy: T + ph - val(d) / max * ph, r: 3, fill: col })); });
      } else {
        var bi = bars.indexOf(s), slot = (horiz ? ph : pw) / n, bw = slot * .7 / groups;
        data.forEach(function (d, i) {
          var v = val(d) || 0, len = v / max * (horiz ? pw : ph), off = stacked ? base[i] : 0, pos = i * slot + slot * .15 + (stacked ? 0 : bi * bw);
          svg.appendChild(horiz ? el('rect', { x: L + off, y: T + pos, width: Math.max(len, 0), height: bw, fill: col, rx: 2 })
                                : el('rect', { x: L + pos, y: T + ph - off - len, width: bw, height: Math.max(len, 0), fill: col, rx: 2 }));
          if (stacked) base[i] += len;
        });
      }
    });
    dom.innerHTML = ''; dom.appendChild(svg);
  };
  window.echarts = { init: function (d) { return d.__lpChart || new Chart(d); }, getInstanceByDom: function (d) { return d.__lpChart; }, use: function () {}, graphic: {}, number: {}, format: {} };
}`;

/** Library keys (server: app/visuals.py LIBRARIES) -> display names. */
export const LIB_NAMES: Record<string, string> = { echarts: 'ECharts', chartjs: 'Chart.js', d3: 'D3', plotly: 'Plotly', bokeh: 'Bokeh' };
/** Libraries found in an installed Python package: fetched with the access code and the folder. */
export const INSTALLED_LIBS = new Set(['plotly', 'bokeh']);
/** Between the files of one library in a /vendor/lib response (server: visuals.LIB_PART_SEPARATOR). */
export const LIB_PART = '\n/*lp:next-script*/\n';
export const DEFAULT_LIB = 'echarts';
export const libName = (key: string | null | undefined): string => LIB_NAMES[String(key || DEFAULT_LIB)] || String(key);

/** code: the library's script(s) (LIB_PART between files); stub: not the real library; note: shown in the frame's corner. */
export interface VisLib { code: string; stub: boolean; note?: string }

const libs = new Map<string, VisLib>();
const libPromises = new Map<string, Promise<VisLib>>();
const libKey = (key: string, dir?: string | null): string => INSTALLED_LIBS.has(key) ? `${key}|${dir || ''}` : key;

/** Escape what could end the library's own <script> element early (or open an HTML comment state inside it). */
export const scriptSafe = (code: string): string => code.replace(/<\/script/gi, '<\\/script').replace(/<!--/g, '<\\!--');

/** Where the page fetches a library: same origin; installed ones carry the access code and the session's folder. */
export function libUrl(key: string, dir?: string | null, search?: string): string {
  const base = `/vendor/lib/${encodeURIComponent(key)}.js`;
  if (!INSTALLED_LIBS.has(key)) return base;
  const q = new URLSearchParams(search ?? (typeof location !== 'undefined' ? location.search : ''));
  const out = new URLSearchParams();
  const code = q.get('code');
  if (code) out.set('code', code);
  if (dir) out.set('dir', dir);
  const s = out.toString();
  return s ? `${base}?${s}` : base;
}

/** A library's source, fetched once per library (and folder, for installed ones); a stand-in when it is not there
    (npm run dev, file mode, not installed): ECharts gets the tiny bar/line renderer, the others a "not loaded" note. */
export function visLib(key: string = DEFAULT_LIB, dir?: string | null): Promise<VisLib> {
  const k = libKey(key, dir);
  const known = libPromises.get(k);
  if (known) return known;
  const p = (async (): Promise<VisLib> => {
    if (typeof location !== 'undefined' && /^https?:$/.test(location.protocol)) {
      try {
        const r = await fetch(libUrl(key, dir), { cache: INSTALLED_LIBS.has(key) ? 'no-store' : 'force-cache' });
        /* a dev server answers unknown paths with its index page: never inline HTML as the library */
        const html = /text\/html/i.test(r.headers.get('content-type') || '');
        if (r.ok && !html) { const t = await r.text(); if (t.length > 2000 && !/^\s*</.test(t)) return { code: scriptSafe(t), stub: false }; }
      } catch { /* fall through to the stand-in */ }
    }
    if (key === DEFAULT_LIB) return { code: '(' + ECHARTS_STAND_IN + ')();', stub: true, note: 'stand-in renderer (file mode, no ECharts)' };
    return { code: '', stub: true, note: `${libName(key)} is not loaded here (no server, or not installed)` };
  })().then(l => { libs.set(k, l); return l; });
  libPromises.set(k, p);
  return p;
}

/* <base target="_top"> comes first, so plain links aim at the top window, which the sandbox refuses;
   meta refresh tags are removed (the browser offers no way to stop a frame navigating itself) */
export function visSrcdoc(html: string | null | undefined, l: VisLib): string {
  const body = String(html ?? '').replace(/<meta\b[^>]*http-equiv\s*=\s*["']?\s*refresh[^>]*>/gi, '');
  const scripts = l.code ? l.code.split(LIB_PART).map(c => `<script>${c}<\/script>`).join('') : '';
  const note = l.stub ? (l.note || 'stand-in renderer (file mode, no ECharts)') : '';
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${VIS_CSP}"><base target="_top"><style>${VIS_BASE_CSS}</style>` +
    `${scripts}<script>${VIS_GUARD}<\/script></head><body>${body}` +
    `${note ? `<div class="lp-stub">${note.replace(/[<>&"]/g, '')}</div>` : ''}</body></html>`;
}

/* ---------- frame registry: postMessage replies are matched to the sending frame by contentWindow ---------- */
interface FrameRec { onError?: (msg: string) => void; onSize?: (h: number) => void; onReady?: () => void }
export interface VisFrameCallbacks {
  onBlocked: () => void;
  onError?: (msg: string) => void;
  /** the frame's content height, clamped to VIS_MIN_H..VIS_MAX_H */
  onSize?: (h: number) => void;
  /** the frame finished loading its option (its guard said so, or its first load event) */
  onReady?: () => void;
}
const frames = new Map<HTMLIFrameElement, FrameRec>();
let probe: string[] | null = null;
let listening = false;

/** The latest results posted by the demo's security probe option (?vistest=1); also on window.lpVisProbe. */
export const getVisProbe = (): string[] | null => probe;
function setProbe(d: { results?: unknown }) {
  probe = Array.isArray(d.results) ? d.results.map(String) : [];
  (window as unknown as { lpVisProbe?: string[] }).lpVisProbe = probe;
}

export function onVisMessage(e: Pick<MessageEvent, 'data' | 'source'>): void {
  const d = e.data as { lpVisual?: unknown; kind?: unknown; msg?: unknown; results?: unknown; h?: unknown } | null;
  if (!d || typeof d !== 'object' || d.lpVisual !== 1) return;
  for (const [iframe, rec] of frames) {
    if (!iframe.contentWindow || iframe.contentWindow !== e.source) continue;
    if (d.kind === 'error' && rec.onError) rec.onError(String(d.msg || '').slice(0, 160));
    if (d.kind === 'size' && rec.onSize) { const h = clampVisHeight(d.h); if (h != null) rec.onSize(h); }
    if (d.kind === 'ready' && rec.onReady) rec.onReady();
    if (d.kind === 'probe') setProbe(d);
    return;
  }
  if (d.kind === 'probe') setProbe(d);           // a frame no longer registered (e.g. the enlarge view closing)
}

function listen() {
  if (listening || typeof window === 'undefined') return;
  listening = true;
  window.addEventListener('message', onVisMessage);
}

/** One sandboxed frame for an option's HTML, with only its library inlined (lib = drawn_with; dir = the session's
    folder, for installed libraries). onBlocked fires if it ever navigates away from its own document; onError gets
    script errors reported by the frame's guard. Call the returned dispose() to remove it. */
export function createVisFrame(html: string, cb: VisFrameCallbacks,
  libKeyName: string = DEFAULT_LIB, dir?: string | null): { iframe: HTMLIFrameElement; dispose: () => void } {
  const key = LIB_NAMES[libKeyName] ? libKeyName : DEFAULT_LIB;
  listen();
  const f = document.createElement('iframe');
  f.setAttribute('sandbox', 'allow-scripts');
  f.setAttribute('referrerpolicy', 'no-referrer');
  f.setAttribute('allow', '');
  f.setAttribute('title', 'Visual option');
  /* the first load after srcdoc is assigned is the option itself; any later load means it navigated away.
     (a frame inserted before srcdoc is set first loads about:blank; that load is ignored) */
  let armed = false, loads = 0, dead = false;
  f.addEventListener('load', () => {
    if (dead || !armed) return;
    if (++loads > 1) cb.onBlocked(); else cb.onReady?.();     // first load = the option is drawn (backs up 'ready')
  });
  const go = (l: VisLib) => { if (dead) return; armed = true; f.srcdoc = visSrcdoc(html, l); };
  const ready = libs.get(libKey(key, dir));
  if (ready) go(ready); else void visLib(key, dir).then(go);
  frames.set(f, { onError: cb.onError, onSize: cb.onSize, onReady: cb.onReady });
  return { iframe: f, dispose: () => { dead = true; frames.delete(f); f.remove(); } };
}

/** Test hook: forget the cached libraries. */
export function resetVisLibForTests(): void { libs.clear(); libPromises.clear(); }
