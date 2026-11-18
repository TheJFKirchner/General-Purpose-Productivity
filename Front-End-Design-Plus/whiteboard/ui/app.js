/* Design whiteboard page. Plain JavaScript, no framework, no network calls
   except to this server (/api/*, /vendor/*). */
(function () {
  'use strict';

  // Session library -> vendor files (loaded in order) and the global handed to render().
  var LIBS = {
    echarts: { files: ['echarts.min.js'], global: 'echarts' },
    plotly: { files: ['plotly.min.js'], global: 'Plotly' },
    chartjs: { files: ['chart.umd.min.js'], global: 'Chart' },
    vegalite: { files: ['vega.min.js', 'vega-lite.min.js', 'vega-embed.min.js'], global: 'vegaEmbed' },
    d3: { files: ['d3.min.js'], global: 'd3' },
    html: { files: [], global: null }
  };
  var EXAMPLES = [
    'Show me four different ways to compare the main numbers across categories.',
    'Give me a table of the top 10 rows, sorted by the largest value.',
    'Make a trend chart over time, then a cleaner version of it.'
  ];

  var $ = function (id) { return document.getElementById(id); };
  var state = {
    library: 'echarts', columns: [], style: '', rows: [],
    cards: [], saved: {}, busy: false, reported: {}, frames: [], loading: false, beat: null
  };

  // ---------- helpers ----------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function api(path, body) {
    return fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
  }
  function getJSON(path) {
    return api(path).then(function (r) {
      if (!r.ok) throw new Error(path + ' returned ' + r.status);
      return r.json();
    });
  }
  function colName(c) { return typeof c === 'string' ? c : (c && c.name) || String(c); }

  // ---------- sealed mini-page ----------
  // The frame makes no network request at all: the parent fetches each library file once,
  // sends the text in, and the frame evaluates it. The frame stays sealed (no same-origin).
  var libCache = {};
  function fetchLib(file) {
    if (!libCache[file]) {
      libCache[file] = fetch('/vendor/' + file).then(function (r) {
        if (!r.ok) throw new Error(file + ' returned ' + r.status);
        return r.text();
      });
      libCache[file].catch(function () { delete libCache[file]; });
    }
    return libCache[file];
  }
  function loadLibs(library) {
    return Promise.all(((LIBS[library] || LIBS.html).files).map(fetchLib));
  }

  function frameHtml() {
    var runner = function () {
      var parentWin = window.parent;
      function send(m) { parentWin.postMessage(m, '*'); }
      function msg(err) { return err && err.message ? (err.name ? err.name + ': ' : '') + err.message : String(err); }
      // Strict reporting: only an exception thrown by the recipe's own code (synchronously, or
      // from the promise it returns) is an error. Window "error" events (for example the browser's
      // ResizeObserver loop warnings) are deliberately not listened to.
      function runWhenSized(box, go) {
        var done = false, ro = null, timer = null;
        function check() {
          if (done) return;
          if (box.clientWidth > 0 && box.clientHeight > 0) {
            done = true;
            if (ro) ro.disconnect();
            clearInterval(timer);
            go();
          }
        }
        if (typeof ResizeObserver === 'function') { ro = new ResizeObserver(check); ro.observe(box); }
        timer = setInterval(check, 100);
        check();
      }
      window.addEventListener('message', function (ev) {
        var m = ev.data;
        if (!m || m.type !== 'run') return;
        var lib;
        try {
          for (var i = 0; i < m.libs.length; i++) (0, eval)(m.libs[i]);
          if (m.global) {
            lib = window[m.global];
            if (lib === undefined) throw new Error('Library "' + m.global + '" did not define its global.');
          }
        } catch (err) {
          send({ type: 'pageerror', error: msg(err) });
          return;
        }
        var box = document.getElementById('box');
        box.className = m.table ? 'scroll-y' : '';
        runWhenSized(box, function () {
          try {
            box.innerHTML = '';
            var fn = new Function('el', 'rows', 'lib', m.code);
            Promise.resolve(fn(box, m.rows, lib)).then(
              function () { send({ type: 'ok' }); },
              function (err) { send({ type: 'error', error: msg(err) }); }
            );
          } catch (err) {
            send({ type: 'error', error: msg(err) });
          }
        });
      });
      send({ type: 'ready' });
    };
    return '<!DOCTYPE html><html><head><meta charset="utf-8"><style>' +
      'html,body{margin:0;height:100%;background:#fff;font:13px/1.4 "Segoe UI",system-ui,Arial,sans-serif;color:#1c2733}' +
      'html,body{overflow:hidden}' +
      '#box{width:100%;height:100%;overflow:hidden;position:relative}' +
      '#box.scroll-y{overflow-x:hidden;overflow-y:auto}' +
      'table{border-collapse:collapse;width:100%}th,td{padding:5px 9px;border-bottom:1px solid #d9e0e8;text-align:left}' +
      'th{background:#e8f0fa;color:#17497f;position:sticky;top:0}' +
      '</style></head><body><div id="box"></div>' +
      '<script>(' + runner.toString() + ')();<\/script></body></html>';
  }

  // Mount a sealed frame into `host`.
  // onError(text): the recipe itself threw (reported to the server).
  // onPageProblem(text): the page could not provide the library (never reported).
  function mountSealed(host, card, onError, onPageProblem) {
    var lib = LIBS[card.library] ? card.library : state.library;
    var f = document.createElement('iframe');
    f.setAttribute('sandbox', 'allow-scripts');   // no allow-same-origin: sealed
    f.setAttribute('title', 'Card ' + card.id);
    var failed = false;
    function fail(fn, text) { if (!failed) { failed = true; fn(text); } }
    function onMsg(ev) {
      if (ev.source !== f.contentWindow) return;
      var m = ev.data || {};
      if (m.type === 'ready') {
        loadLibs(lib).then(function (texts) {
          if (!f.isConnected) return;
          f.contentWindow.postMessage({
            type: 'run', code: String(card.code || ''), rows: state.rows,
            table: card.kind === 'table', libs: texts, global: (LIBS[lib] || LIBS.html).global
          }, '*');
        }, function (e) {
          fail(onPageProblem, 'The ' + lib + ' library file could not be loaded (' + e.message + ').');
        });
      } else if (m.type === 'pageerror') {
        fail(onPageProblem, 'The ' + lib + ' library failed to start: ' + (m.error || 'unknown error'));
      } else if (m.type === 'error') {
        fail(onError, m.error || 'Unknown error');
      }
    }
    window.addEventListener('message', onMsg);
    f.srcdoc = frameHtml();
    host.appendChild(f);
    var handle = { destroy: function () { window.removeEventListener('message', onMsg); f.remove(); } };
    state.frames.push(handle);
    return handle;
  }

  // ---------- cards ----------
  function cardNode(card) {
    var node = el('article', 'card');
    node.dataset.id = card.id;

    var head = el('div', 'card-head');
    var idb = el('button', 'id-badge', card.id);
    idb.type = 'button';
    idb.title = 'Insert ' + card.id + ' into the chat';
    idb.addEventListener('click', function () { insertId(card.id); });
    head.appendChild(idb);
    head.appendChild(el('div', 'card-title', card.title || '(untitled)'));
    head.appendChild(el('span', 'tag', card.kind === 'table' ? 'table' : (card.library || state.library)));
    node.appendChild(head);

    var sub = el('div', 'card-sub');
    sub.appendChild(el('span', 'from', card.parent ? 'from ' + card.parent : ''));
    sub.appendChild(el('span', 'tag saved', 'Saved'));
    node.appendChild(sub);

    var view = el('div', 'card-view');
    var err = el('div', 'card-error');
    view.appendChild(err);
    node.appendChild(view);
    node._handle = mountSealed(view, card, function (text) {
      view.classList.add('failed');
      err.className = 'card-error';
      err.textContent = 'This card could not be drawn.\n\n' + text;
      reportError(card, text);
    }, function (text) {
      view.classList.add('failed');
      err.className = 'card-error page-problem';
      err.textContent = 'Page problem, not the card\'s fault.\n\n' + text + '\n\nReload the page to try again.';
    });

    var foot = el('div', 'card-foot');
    var save = el('button', 'btn small save-btn', 'Save');
    save.type = 'button';
    save.addEventListener('click', function () { toggleSave(card); });
    var enl = el('button', 'btn small', 'Enlarge');
    enl.type = 'button';
    enl.addEventListener('click', function () { openModal(card); });
    var del = el('button', 'btn small danger', 'Delete');
    del.type = 'button';
    del.addEventListener('click', function () { deleteCard(card); });
    foot.appendChild(save); foot.appendChild(enl);
    foot.appendChild(el('span', 'sp'));
    foot.appendChild(del);
    node.appendChild(foot);
    applySaved(node, !!state.saved[card.id]);
    return node;
  }

  // Saved styling only: never touches the frame.
  function applySaved(node, saved) {
    node.classList.toggle('saved', saved);
    var b = node.querySelector('.save-btn');
    b.textContent = saved ? 'Unsave' : 'Save';
    b.title = saved ? 'Saved. Click to unsave.' : 'Save this card';
  }

  function reportError(card, text) {
    var key = card.id + '\u0000' + card.code;
    if (state.reported[key]) return;
    state.reported[key] = true;
    api('/api/card-error', { id: card.id, error: text }).then(function (r) { return r.json(); }).then(function (res) {
      if (res && res.fixed && res.card) {
        upsertCard(res.card);
        if (res.text) addMsg('agent', res.text);
      }
    }).catch(function () { /* the card keeps showing its error */ });
  }

  function upsertCard(card) {
    if (card.saved) state.saved[card.id] = true;
    var i = state.cards.findIndex(function (c) { return c.id === card.id; });
    if (i >= 0) state.cards[i] = card; else state.cards.push(card);
    var grid = $('grid');
    var fresh = cardNode(card);
    var old = grid.querySelector('[data-id="' + card.id + '"]');
    if (old) {
      if (old._handle) old._handle.destroy();
      grid.replaceChild(fresh, old);
    } else {
      grid.appendChild(fresh);
      if (!state.loading) fresh.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    refreshBoard();
  }

  function refreshBoard() {
    var n = state.cards.length;
    $('empty').hidden = n > 0;
    $('grid').hidden = n === 0;
    $('count').textContent = n ? '(' + n + ')' : '';
  }

  // POST and read the {ok, error} reply; failures are shown in the chat.
  function action(path, id, what) {
    return api(path, { id: id }).then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .catch(function () { return { ok: false, error: 'the server did not answer' }; })
      .then(function (res) {
        if (!res || res.ok === false) {
          addMsg('error', 'Could not ' + what + ' ' + id + (res && res.error ? ': ' + res.error : '.'));
          return false;
        }
        return true;
      });
  }
  function toggleSave(card) {
    var want = !state.saved[card.id];
    action(want ? '/api/save' : '/api/unsave', card.id, want ? 'save' : 'unsave').then(function (ok) {
      if (!ok) return;
      if (want) state.saved[card.id] = true; else delete state.saved[card.id];
      var node = $('grid').querySelector('[data-id="' + card.id + '"]');
      if (node) applySaved(node, want);
    });
  }
  function deleteCard(card) {
    action('/api/delete', card.id, 'delete').then(function (ok) {
      if (!ok) return;
      var node = $('grid').querySelector('[data-id="' + card.id + '"]');
      if (node) { if (node._handle) node._handle.destroy(); node.remove(); }
      state.cards = state.cards.filter(function (c) { return c.id !== card.id; });
      delete state.saved[card.id];
      refreshBoard();
    });
  }

  // ---------- enlarge ----------
  var modalHandle = null;
  function openModal(card) {
    $('modal-id').textContent = card.id;
    $('modal-title').textContent = card.title || '';
    var body = $('modal-body');
    body.textContent = '';
    var err = el('div', 'card-error');
    err.style.display = 'none';
    body.appendChild(err);
    $('modal').hidden = false;
    modalHandle = mountSealed(body, card, function (text) {
      err.className = 'card-error';
      err.style.display = 'block';
      err.textContent = 'This card could not be drawn.\n\n' + text;
    }, function (text) {
      err.className = 'card-error page-problem';
      err.style.display = 'block';
      err.textContent = 'Page problem, not the card\'s fault.\n\n' + text;
    });
  }
  function closeModal() {
    $('modal').hidden = true;
    if (modalHandle) { modalHandle.destroy(); modalHandle = null; }
  }
  $('modal-close').addEventListener('click', closeModal);
  $('modal').addEventListener('click', function (e) { if (e.target === $('modal')) closeModal(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !$('modal').hidden) closeModal(); });

  // ---------- chat ----------
  function insertId(id) {
    var t = $('input');
    if (t.disabled) return;
    var v = t.value;
    var pre = v && !/\s$/.test(v) ? ' ' : '';
    t.value = v + pre + id + ' ';
    t.focus();
    t.setSelectionRange(t.value.length, t.value.length);
  }

  // Small safe Markdown: paragraphs, "-"/"*"/"1." lists, # headings, **bold**, `code`.
  // Built with DOM nodes and textContent only, so nothing from the reply is parsed as HTML.
  function inline(parent, text) {
    var re = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g, last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
      var tok = m[0];
      if (tok.charAt(0) === '`') parent.appendChild(el('code', null, tok.slice(1, -1)));
      else parent.appendChild(el('strong', null, tok.slice(2, -2)));
      last = m.index + tok.length;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  }
  function renderMarkdown(target, text) {
    target.textContent = '';
    var lines = String(text).replace(/\r/g, '').split('\n');
    var list = null, para = null;
    lines.forEach(function (line) {
      var li = /^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/.exec(line);
      var h = /^\s*#{1,6}\s+(.*)$/.exec(line);
      if (li) {
        para = null;
        var ordered = li[1] !== undefined;
        if (!list || list.tagName !== (ordered ? 'OL' : 'UL')) {
          list = el(ordered ? 'ol' : 'ul');
          target.appendChild(list);
        }
        var item = el('li');
        inline(item, li[2]);
        list.appendChild(item);
      } else if (h) {
        list = null; para = null;
        var hd = el('p', 'md-h');
        inline(hd, h[1]);
        target.appendChild(hd);
      } else if (!line.trim()) {
        list = null; para = null;
      } else {
        list = null;
        if (!para) { para = el('p'); target.appendChild(para); }
        else para.appendChild(document.createElement('br'));
        inline(para, line.trim());
      }
    });
  }

  function addMsg(cls, text) {
    var m = el('div', 'msg ' + cls);
    if (cls === 'agent') { m._raw = text || ''; renderMarkdown(m, m._raw); m.classList.add('md'); }
    else m.textContent = text;
    var box = $('messages');
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
    return m;
  }
  function setBusy(b) {
    state.busy = b;
    $('input').disabled = b;
    $('send').disabled = b;
    $('status').textContent = b ? 'Working...' : '';
    if (!b) $('input').focus();
  }
  function payload(data) {
    try { return JSON.parse(data); } catch (e) { return data; }
  }
  function textOf(p) {
    if (typeof p === 'string') return p;
    if (p && typeof p === 'object') return p.text || p.delta || p.message || p.error || '';
    return '';
  }

  function sendMessage(message) {
    addMsg('user', message);
    setBusy(true);
    var current = null;
    function handle(evt, data) {
      var p = payload(data);
      if (evt === 'text') {
        if (!current) current = addMsg('agent', '');
        current._raw += textOf(p);
        renderMarkdown(current, current._raw);
        $('messages').scrollTop = $('messages').scrollHeight;
      } else if (evt === 'card') {
        var card = (p && p.card) || p;
        if (card && card.id) {
          upsertCard(card);
          current = null;
          addMsg('note', 'Card ' + card.id + ' added: ' + (card.title || ''));
        }
      } else if (evt === 'error') {
        addMsg('error', textOf(p) || 'Something went wrong.');
      }
    }
    return fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
      body: JSON.stringify({ message: message })
    }).then(function (resp) {
      if (!resp.ok || !resp.body) throw new Error('The server returned ' + resp.status + '.');
      var reader = resp.body.getReader();
      var dec = new TextDecoder();
      var buf = '';
      function flushBlock(block) {
        var evt = 'message', lines = [];
        block.split(/\r?\n/).forEach(function (line) {
          if (line.indexOf('event:') === 0) evt = line.slice(6).trim();
          else if (line.indexOf('data:') === 0) lines.push(line.slice(line[5] === ' ' ? 6 : 5));
        });
        if (lines.length || evt !== 'message') handle(evt, lines.join('\n'));
      }
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) {
            if (buf.trim()) flushBlock(buf);
            return;
          }
          buf += dec.decode(r.value, { stream: true });
          var parts = buf.split(/\r?\n\r?\n/);
          buf = parts.pop();
          parts.forEach(flushBlock);
          return pump();
        });
      }
      return pump();
    }).catch(function (e) {
      addMsg('error', 'Connection problem: ' + e.message);
    }).then(function () {
      setBusy(false);
    });
  }

  $('composer').addEventListener('submit', function (e) {
    e.preventDefault();
    var v = $('input').value.trim();
    if (!v || state.busy) return;
    $('input').value = '';
    sendMessage(v);
  });
  $('input').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('composer').requestSubmit(); }
  });

  // ---------- done ----------
  $('done').addEventListener('click', function () {
    $('done').disabled = true;
    api('/api/done', {}).catch(function () { /* the server may already be stopping */ }).then(function () {
      setBusy(true);
      $('status').textContent = '';
      $('finished').hidden = false;
      clearInterval(state.beat);
      try { window.close(); } catch (e) { /* ignored; the message tells the user */ }
    });
  });

  // ---------- start-up ----------
  function renderMeta() {
    var m = $('meta');
    m.textContent = '';
    m.appendChild(document.createTextNode('Library: '));
    m.appendChild(el('b', null, state.library));
    m.appendChild(document.createTextNode(' · ' + state.rows.length + ' rows'));
    m.appendChild(document.createElement('br'));
    m.appendChild(document.createTextNode('Columns: ' + (state.columns.map(colName).join(', ') || 'none')));
    if (state.style) {
      m.appendChild(document.createElement('br'));
      m.appendChild(document.createTextNode('Style: ' + state.style));
    }
  }

  function heartbeat() { api('/api/heartbeat', {}).catch(function () { /* best effort */ }); }

  function init() {
    var ex = $('examples');
    EXAMPLES.forEach(function (t) {
      var li = el('li');
      var b = el('span', 'ex', t);
      b.setAttribute('role', 'button');
      b.tabIndex = 0;
      function use() { $('input').value = t; $('input').focus(); }
      b.addEventListener('click', use);
      b.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); use(); } });
      li.appendChild(b);
      ex.appendChild(li);
    });

    heartbeat();
    state.beat = setInterval(heartbeat, 15000);

    Promise.all([getJSON('/api/session'), getJSON('/api/data')]).then(function (res) {
      var s = res[0] || {}, d = res[1];
      state.library = s.library || 'echarts';
      state.columns = s.columns || [];
      state.style = s.style || '';
      state.rows = Array.isArray(d) ? d : (d && (d.rows || d.data)) || [];
      var cards = s.cards || [];
      renderMeta();
      (s.chat || []).forEach(function (m) {
        if (m && m.text) addMsg(m.role === 'user' ? 'user' : 'agent', m.text);
      });
      state.loading = true;
      cards.forEach(upsertCard);
      state.loading = false;
      refreshBoard();
      $('grid').scrollTop = 0;
      if (cards.length) {
        addMsg('note', (s.chat || []).length
          ? 'Resumed with ' + cards.length + ' card' + (cards.length === 1 ? '' : 's') + '.'
          : 'Starting from the existing visual' + (cards.length === 1 ? '' : 's') + '.');
      }
      $('input').focus();
    }).catch(function (e) {
      $('meta').textContent = 'Could not load the session: ' + e.message;
      addMsg('error', 'Could not load the session: ' + e.message);
      refreshBoard();
    });
  }
  init();
})();
