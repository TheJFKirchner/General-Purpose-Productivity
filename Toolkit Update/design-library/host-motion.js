/* host-motion.js: plays copied design-library animations (AUTHORING.md, "Adding an animation"). Copy verbatim once,
   before the first animation's script; host-runtime.js still comes last. Each copy (<div data-item="AN-..">) stays in its
   end state until it plays: when it scrolls into view, or, with data-trigger="manual", when the host calls
   ItemMotion.play(el) (a deck, when its slide shows). A Replay button replays it. Reduced motion: no autoplay, Replay
   still plays. Print and html.is-export: end state, no button. */
(function () {
  var root = document.documentElement, still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var recs = [];
  function rec(el) { for (var i = 0; i < recs.length; i++) if (recs[i].el === el) return recs[i]; var r = { el: el, forced: false, started: false, replay: [] }; recs.push(r); return r; }
  function moving(r) { return r.started && !root.classList.contains('is-export') && (r.forced || !still); }
  function show(el, v) { var d = +(el.getAttribute('data-decimals') || 0); el.textContent = (el.getAttribute('data-prefix') || '') + v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) + (el.getAttribute('data-suffix') || ''); }
  function tickUp(r) {
    Array.prototype.forEach.call(r.el.querySelectorAll('[data-tick-up]'), function (el) {
      var to = +el.getAttribute('data-tick-up'), from = to * 0.9, t0 = null;
      function step(ts) { if (t0 === null) t0 = ts; var k = Math.min(1, (ts - t0) / 800), e = 1 - Math.pow(1 - k, 3); show(el, k < 1 ? from + (to - from) * e : to); if (k < 1) requestAnimationFrame(step); }
      requestAnimationFrame(step);
    });
  }
  /* plays one copy: CSS motion under .play, charts draw in, count-ups, then the copy's own script hears item:replay */
  function play(el, explicit) {
    var r = rec(el);
    r.started = true;
    if (explicit) { r.forced = true; if (still) root.classList.add('forced'); }
    var go = moving(r);
    el.classList.remove('play');
    if (go) { void el.offsetWidth; el.classList.add('play'); tickUp(r); }
    if (window.ItemHost) ItemHost.draw(function (box) { return go && el.contains(box); });
    var ev = new CustomEvent('item:replay', { detail: { explicit: !!explicit } });
    r.replay.forEach(function (fn) { fn(ev); });
  }
  /* runs a copy's own script inside that copy: document lookups, its Replay hook and ItemEngine all see only it */
  function attach(id, fn) {
    Array.prototype.forEach.call(document.querySelectorAll('[data-item="' + id + '"]'), function (el) {
      if (el._motion) return;
      el._motion = true;
      var r = rec(el);
      var doc = new Proxy(document, { get: function (t, k) {
        if (k === 'querySelector') return function (s) { return el.querySelector(s); };
        if (k === 'querySelectorAll') return function (s) { return el.querySelectorAll(s); };
        if (k === 'getElementById') return function (s) { return el.querySelector('#' + CSS.escape(s)); };
        var v = t[k]; return typeof v === 'function' ? v.bind(t) : v;
      } });
      function listen(type, f, o) { if (type === 'item:replay') r.replay.push(f); else window.addEventListener(type, f, o); }
      var win = new Proxy(window, { get: function (t, k) {
        if (k === 'addEventListener') return listen;
        if (k === 'document') return doc;
        if (k === 'ItemEngine') return eng;
        var v = t[k]; return typeof v === 'function' && !/^[A-Z]/.test(k) ? v.bind(t) : v;
      } });
      var eng = {
        motion: function () { return moving(r); },
        play: function () { play(el, true); },
        force: function () { r.started = true; r.forced = true; if (still) root.classList.add('forced'); el.classList.add('play'); },
        chart: function (x) { return window.ItemHost ? ItemHost.chart(x || el.querySelector('.chart[data-echart]')) : null; },
        redraw: function () { if (window.ItemHost) ItemHost.draw(); }
      };
      fn.call(win, doc, win, eng, listen);
    });
  }
  function button(el) {
    if (el.getAttribute('data-replay') === 'off' || el.querySelector('.item-replay')) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'item-replay'; b.textContent = 'Replay';
    b.addEventListener('click', function () { play(el, true); });
    el.appendChild(b);
  }
  function start() {
    var els = Array.prototype.slice.call(document.querySelectorAll('[data-item^="AN-"]'));
    els.forEach(function (el) { rec(el); button(el); });
    var auto = els.filter(function (el) { return el.getAttribute('data-trigger') !== 'manual'; });
    if (!window.IntersectionObserver) { auto.forEach(function (el) { play(el); }); return; }
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); play(e.target); } }); }, { threshold: 0.4 });
    auto.forEach(function (el) { io.observe(el); });
  }
  if (document.readyState === 'complete') setTimeout(start, 0); else window.addEventListener('load', function () { setTimeout(start, 0); });
  window.addEventListener('beforeprint', function () { recs.forEach(function (r) { r.el.classList.remove('play'); }); if (window.ItemHost) ItemHost.draw(); });
  window.ItemMotion = { attach: attach, play: function (el, explicit) { play(el, explicit); } };
})();
