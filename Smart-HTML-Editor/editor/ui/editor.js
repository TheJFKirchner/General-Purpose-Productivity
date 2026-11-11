// Smart HTML Editor: the browser side.
// The page runs in an iframe served from /doc/<file>, where every element carries data-she-id="nX"
// (added by the server when serving; never written to the file). This script:
//  - outlines what's under the pointer and selects it on click (Select & edit mode);
//  - lets the person type into text in place (double-click), checking that only text changed;
//  - quick style controls and the theme panel (no model call);
//  - the assistant chat;
//  - answers the assistant's "what does this element look like" requests with computed colors/fonts
//    and matching CSS rules (never the page's text or data).
'use strict';

const $ = (id) => document.getElementById(id);
const frame = $('page');
const api = {
  get: (p) => fetch(p).then((r) => r.json()),
  post: (p, b) => fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then((r) => r.json()),
};
const S = {
  info: null, state: null, mode: 'edit', hideData: false,
  selected: null, structSeq: null, loadedReload: null, selectSeq: 0, lastStylesReq: 0,
  editing: null, loading: false, chatBusy: false, version: null,
};
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
};

// ------------------------------------------------------------------ small helpers
function toast(text, bad = false) {
  const t = $('toast');
  t.textContent = text;
  t.className = 'toast' + (bad ? ' bad' : '');
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.hidden = true; }, bad ? 6000 : 3200);
}
const doc = () => frame.contentDocument;
const win = () => frame.contentWindow;
const byId = (id) => (id && doc() ? doc().querySelector(`[data-she-id="${id}"]`) : null);
const squash = (s) => (s || '').replace(/\s+/g, ' ').trim();

function hex(c) {
  if (!c) return c;
  const m = c.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
  if (!m) return c;
  if (m[4] !== undefined && Number(m[4]) === 0) return 'transparent';
  const h = '#' + [m[1], m[2], m[3]].map((v) => Math.round(Number(v)).toString(16).padStart(2, '0')).join('');
  return m[4] !== undefined && Number(m[4]) < 1 ? `${h} at ${Math.round(Number(m[4]) * 100)}%` : h;
}
const toColorInput = (c) => { const h = hex(c) || ''; return /^#[0-9a-f]{6}$/i.test(h) ? h : '#000000'; };
const redactUrls = (s) => (s || '').replace(/url\((?:[^()]|\([^)]*\))*\)/gi, 'url(…)');

function tagLabel(el) {
  let s = el.tagName.toLowerCase();
  if (el.id) s += '#' + el.id;
  const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).filter((c) => c && !c.startsWith('she-')) : [];
  if (cls.length) s += '.' + cls.slice(0, 3).join('.');
  return s;
}

// ------------------------------------------------------------------ looks (for the assistant)
const RELEVANT = /^(color|background|font|border|text-|letter-spacing|line-height|padding|margin|box-shadow|border-radius|opacity|display|--)/;

function matchedRules(el) {
  const out = [];
  const w = win();
  const walk = (rules) => {
    for (const r of rules) {
      if (out.length > 40) return;
      if (r.selectorText !== undefined && r.style) {
        let hit = false;
        try { hit = el.matches(r.selectorText); } catch { hit = false; }
        if (!hit) continue;
        const decls = [];
        for (let i = 0; i < r.style.length; i++) {
          const p = r.style[i];
          if (RELEVANT.test(p)) decls.push(`${p}: ${redactUrls(r.style.getPropertyValue(p)).trim()}`);
        }
        if (decls.length) out.push(`${r.selectorText} { ${decls.join('; ')} }`.slice(0, 240));
      } else if (r.cssRules) {
        const cond = r.media ? r.media.mediaText : r.conditionText;
        if (r.media && cond && !w.matchMedia(cond).matches) continue;
        walk(r.cssRules);
      }
    }
  };
  for (const sheet of doc().styleSheets) {
    if (sheet.ownerNode && sheet.ownerNode.id === 'she-ui-style') continue;
    try { walk(sheet.cssRules); } catch { /* cross-origin sheet */ }
  }
  return out.slice(-8);   // later rules win; keep the last ones
}

function looksOf(el) {
  const cs = win().getComputedStyle(el);
  const px = (v) => (v && v !== '0px' ? v : null);
  return {
    node: el.dataset.sheId || null,
    tag: tagLabel(el),
    color: hex(cs.color),
    background: hex(cs.backgroundColor),
    backgroundImage: cs.backgroundImage && cs.backgroundImage !== 'none' ? (cs.backgroundImage.startsWith('url') ? 'image' : 'gradient') : null,
    font: `${cs.fontWeight} ${cs.fontSize} ${(cs.fontFamily || '').split(',')[0].replace(/["']/g, '')}`,
    border: px(cs.borderTopWidth) ? `${cs.borderTopWidth} ${cs.borderTopStyle} ${hex(cs.borderTopColor)}` : null,
    padding: cs.padding !== '0px' ? cs.padding : null,
    radius: px(cs.borderTopLeftRadius),
    shadow: cs.boxShadow && cs.boxShadow !== 'none' ? 'yes' : null,
    display: cs.display === 'none' ? 'none' : null,
    rules: matchedRules(el),
    inline: el.getAttribute('style') ? redactUrls(el.getAttribute('style')).slice(0, 200) : null,
  };
}

function looksChain(el, generated = false) {
  const chain = [];
  let cur = el;
  while (cur && cur.nodeType === 1 && chain.length < 5 && cur.tagName !== 'HTML') {
    chain.push(looksOf(cur));
    cur = cur.parentElement;
  }
  return { chain, generated };
}

// ------------------------------------------------------------------ frame setup
const UI_CSS = `
.she-box { position: fixed; pointer-events: none; z-index: 2147483646; border-radius: 3px; display: none; }
.she-hover { outline: 1.5px dashed #6366f1; background: rgba(99,102,241,.06); }
.she-selected { outline: 2px solid #4f46e5; }
.she-tag { position: fixed; pointer-events: none; z-index: 2147483647; display: none; font: 11px/1.4 ui-monospace, Consolas, monospace;
  background: #4f46e5; color: #fff; padding: 1px 6px; border-radius: 4px; white-space: nowrap; }
[contenteditable].she-editing { outline: 2px solid #f59e0b !important; outline-offset: 2px; background: rgba(245,158,11,.08) !important; cursor: text; }
html.she-hide [data-she-mask], html.she-hide svg, html.she-hide canvas, html.she-hide img, html.she-hide video,
html.she-hide td, html.she-hide iframe { filter: blur(7px) !important; }
html.she-edit-mode a, html.she-edit-mode button { cursor: default; }
`;

function setupFrame() {
  const d = doc();
  if (!d || !d.documentElement) return;
  const style = d.createElement('style');
  style.id = 'she-ui-style';
  style.textContent = UI_CSS;
  (d.head || d.documentElement).appendChild(style);
  for (const cls of ['she-box she-hover', 'she-box she-selected', 'she-tag']) {
    const div = d.createElement('div');
    div.className = cls;
    d.documentElement.appendChild(div);
  }
  applyModeClasses();
  d.addEventListener('mousemove', onHover, true);
  d.addEventListener('mouseleave', () => drawBox('.she-hover', null), true);
  d.addEventListener('click', onClick, true);
  d.addEventListener('dblclick', onDblClick, true);
  d.addEventListener('submit', (e) => { if (S.mode === 'edit') e.preventDefault(); }, true);
  d.addEventListener('keydown', onKey, true);
  win().addEventListener('scroll', redraw, true);
  win().addEventListener('resize', redraw);
}

function applyModeClasses() {
  const root = doc() && doc().documentElement;
  if (!root) return;
  root.classList.toggle('she-hide', S.hideData);
  root.classList.toggle('she-edit-mode', S.mode === 'edit');
  if (S.mode !== 'edit') drawBox('.she-hover', null);
}

function drawBox(sel, el, label) {
  const d = doc();
  if (!d) return;
  const box = d.querySelector(sel);
  if (!box) return;
  const r = el && el.isConnected && el.ownerDocument === d ? el.getBoundingClientRect() : null;
  if (!r || (!r.width && !r.height)) { box.style.display = 'none'; if (sel === '.she-hover') d.querySelector('.she-tag').style.display = 'none'; return; }
  Object.assign(box.style, { display: 'block', left: r.left + 'px', top: r.top + 'px', width: r.width + 'px', height: r.height + 'px' });
  if (label) {
    const tag = d.querySelector('.she-tag');
    tag.textContent = label;
    Object.assign(tag.style, { display: 'block', left: Math.max(0, r.left) + 'px', top: Math.max(0, r.top - 18) + 'px' });
  }
}

function redraw() {
  drawBox('.she-selected', byId(S.selected));
  if (S.hoverEl) drawBox('.she-hover', S.hoverEl, tagLabel(S.hoverEl));
}

const holderOf = (target) => (target && target.closest ? target.closest('[data-she-id]') : null);

function onHover(e) {
  if (S.mode !== 'edit' || S.editing) return;
  const el = holderOf(e.target);
  S.hoverEl = el;
  drawBox('.she-hover', el, el ? tagLabel(el) + (el !== e.target ? ' (holds script-drawn content)' : '') : '');
}

function onClick(e) {
  if (S.mode !== 'edit') return;
  if (S.editing && S.editing.el.contains(e.target)) return;   // clicking inside the text being typed
  e.preventDefault();
  e.stopPropagation();
  if (S.editing) commitEdit();
  const el = holderOf(e.target);
  if (el) select(el, { generated: el !== e.target && !e.target.dataset?.sheId });
}

function onDblClick(e) {
  if (S.mode !== 'edit') return;
  e.preventDefault();
  e.stopPropagation();
  const el = holderOf(e.target);
  if (el) startEdit(el, e);
}

function onKey(e) {
  if (S.editing) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commitEdit(); }
    else if (e.key === 'Enter') { e.preventDefault(); }
    else if (e.key === 'Escape') { e.preventDefault(); cancelEdit(); }
    return;
  }
  globalKeys(e);
}

function globalKeys(e) {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  else if (mod && e.key.toLowerCase() === 'z' && !isTyping(e)) { e.preventDefault(); undo(); }
  else if (e.key === 'Escape' && S.selected && !isTyping(e)) { setSelected(null); }
}
const isTyping = (e) => { const t = e.target; return t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable); };

// ------------------------------------------------------------------ loading the page
async function loadFrame() {
  if (S.editing) return;
  S.loading = true;
  let x = 0, y = 0;
  try { x = win().scrollX; y = win().scrollY; } catch { /* first load */ }
  const st = await api.get('/api/state');
  S.structSeq = st.struct_seq;
  S.loadedReload = st.reload_seq;
  frame.onload = async () => {
    S.hoverEl = null;
    setupFrame();
    try { win().scrollTo(x, y); } catch { /* ignore */ }
    S.loading = false;
    const after = await api.get('/api/state');
    if (after.struct_seq !== S.structSeq) return loadFrame();   // changed while loading
    if (S.selected && !byId(S.selected)) setSelected(null); else redraw();
  };
  frame.src = '/doc/' + encodeURIComponent(S.info.file) + '?v=' + st.version + '.' + st.reload_seq;
}

// ------------------------------------------------------------------ selection
async function select(el, { generated = false, fromServer = false, scroll = false } = {}) {
  S.selected = el.dataset.sheId;
  drawBox('.she-selected', el);
  if (scroll) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  if (fromServer) {
    const info = await api.get('/api/node?node=' + S.selected);
    renderSelection(info);
    return;
  }
  const res = await api.post('/api/select', { node: S.selected, struct_seq: S.structSeq, info: looksChain(el, generated) });
  if (res.error === 'stale') return loadFrame();
  renderSelection(res, generated);
}

function setSelected(id) {
  const el = byId(id);
  if (el) return select(el);
  S.selected = null;
  drawBox('.she-selected', null);
  api.post('/api/select', { node: null });
  renderSelection({ node: null });
}

function renderSelection(info, generated = false) {
  $('sel-empty').hidden = Boolean(info.node);
  $('sel-body').hidden = !info.node;
  if (!info.node) return;
  const crumbs = $('crumbs');
  crumbs.innerHTML = '';
  (info.path || []).forEach((p, i) => {
    if (i) crumbs.insertAdjacentHTML('beforeend', '<span class="sep">›</span>');
    const b = document.createElement('button');
    b.textContent = p.label;
    b.title = p.id;
    if (p.id === info.node) b.className = 'current';
    b.onclick = () => setSelected(p.id);
    crumbs.appendChild(b);
  });
  const el = byId(info.node);
  if (el) {
    const cs = win().getComputedStyle(el);
    $('q-color').value = toColorInput(cs.color);
    $('q-bg').value = toColorInput(cs.backgroundColor);
  }
  const note = $('sel-note');
  const notes = [];
  if (info.hidden) notes.push(`This is inside a hidden part (${info.hidden}); it can't be edited here.`);
  if (generated) notes.push('You clicked content drawn by the page\'s script; the element that holds it is selected.');
  note.textContent = notes.join(' ');
  note.hidden = !notes.length;
  $('quick').style.opacity = info.hidden ? 0.4 : 1;
}

// ------------------------------------------------------------------ typing in place
const plainOnly = (() => { const d = document.createElement('div'); d.contentEditable = 'plaintext-only'; return d.contentEditable === 'plaintext-only'; })();

async function startEdit(el, evt) {
  if (S.editing) await commitEdit();
  if (S.hideData && el.closest('[data-she-mask]')) return toast('Turn off Hide data to edit this text.');
  const els = [el, ...el.querySelectorAll('[data-she-id]')];
  if (els.length > 60) return toast('Too much inside this element. Double-click a smaller piece of text.');
  const res = await api.get('/api/runs?nodes=' + els.map((e) => e.dataset.sheId).join(','));
  if (res.struct_seq !== S.structSeq) return loadFrame();
  const map = [];
  for (const e of els) {
    const dom = [...e.childNodes].filter((n) => n.nodeType === 3 && n.nodeValue.trim());
    const src = (res.runs[e.dataset.sheId] || []).filter((r) => r.text.trim());
    if (dom.length !== src.length) return toast(e === el ? "This text can't be typed into here (the page's script changes it). Ask the assistant instead." : 'Part of this text is drawn by a script. Double-click a smaller piece.');
    for (let i = 0; i < dom.length; i++) {
      if (squash(dom[i].nodeValue) !== squash(src[i].text) || !src[i].editable) return toast("This text can't be typed into here. Ask the assistant instead.");
      map.push({ tn: dom[i], run: src[i].id, old: src[i].text, domOld: dom[i].nodeValue });
    }
  }
  if (!map.length) return toast('No text in this element. Select it and use the controls or the assistant.');
  if (S.selected !== el.dataset.sheId) select(el);
  S.editing = { el, map, count: el.querySelectorAll('*').length, hadChildren: el.children.length > 0 };
  el.contentEditable = plainOnly ? 'plaintext-only' : 'true';
  el.classList.add('she-editing');
  drawBox('.she-hover', null);
  el.focus();
  placeCaret(evt);
  el.addEventListener('blur', onEditBlur);
  el.addEventListener('paste', onPaste);
  $('frame-hint').textContent = 'Typing · Enter to keep · Esc to cancel';
  $('frame-hint').classList.remove('gone');
}

function placeCaret(evt) {
  if (!evt) return;
  const d = doc();
  const sel = win().getSelection();
  let range = null;
  if (d.caretRangeFromPoint) range = d.caretRangeFromPoint(evt.clientX, evt.clientY);
  else if (d.caretPositionFromPoint) {
    const p = d.caretPositionFromPoint(evt.clientX, evt.clientY);
    if (p) { range = d.createRange(); range.setStart(p.offsetNode, p.offset); }
  }
  if (range) { sel.removeAllRanges(); sel.addRange(range); }
}

function onPaste(e) {
  e.preventDefault();
  const text = (e.clipboardData.getData('text/plain') || '').replace(/\s*\n\s*/g, ' ');
  doc().execCommand('insertText', false, text);
}

function onEditBlur() { setTimeout(() => { if (S.editing && doc().activeElement !== S.editing.el) commitEdit(); }, 0); }

function endEditing() {
  const ed = S.editing;
  S.editing = null;
  ed.el.removeAttribute('contenteditable');
  ed.el.classList.remove('she-editing');
  ed.el.removeEventListener('blur', onEditBlur);
  ed.el.removeEventListener('paste', onPaste);
  $('frame-hint').textContent = 'Click anything to select it · double-click text to type · Esc to stop';
  return ed;
}

async function commitEdit() {
  if (!S.editing) return;
  const ed = endEditing();
  const intact = ed.el.querySelectorAll('*').length === ed.count && ed.map.every((m) => m.tn.isConnected && m.tn.parentNode);
  let changes;
  let reloadAfter = false;
  if (intact) {
    changes = ed.map.filter((m) => m.tn.nodeValue !== m.domOld).map((m) => ({ run: m.run, old: m.old, text: m.tn.nodeValue }));
  } else if (ed.map.length === 1 && !ed.hadChildren) {
    changes = [{ run: ed.map[0].run, old: ed.map[0].old, text: ed.el.textContent }];   // a plain text element: take all its text
    reloadAfter = true;
  } else {
    toast('That edit changed more than the text, so it was undone. Ask the assistant for bigger changes.', true);
    return loadFrame();
  }
  for (const c of changes) {
    const res = await api.post('/api/text', { ...c, struct_seq: S.structSeq });
    if (!res.ok) { toast(res.error || 'Could not save that text.', true); reloadAfter = true; break; }
    if (res.struct_seq !== S.structSeq) reloadAfter = true;
    updateBar(res);
  }
  if (reloadAfter) loadFrame();
  else redraw();
}

function cancelEdit() {
  if (!S.editing) return;
  const ed = endEditing();
  const intact = ed.el.querySelectorAll('*').length === ed.count && ed.map.every((m) => m.tn.isConnected);
  if (!intact) return loadFrame();
  for (const m of ed.map) m.tn.nodeValue = m.domOld;
  redraw();
}

// ------------------------------------------------------------------ quick styles (no model call)
async function quickStyle(styles, reload = false) {
  if (!S.selected) return;
  const el = byId(S.selected);
  const res = await api.post('/api/style', { node: S.selected, styles, reload });
  if (!res.ok) return toast(res.error, true);
  if (el && !reload) for (const [p, v] of Object.entries(styles)) v ? el.style.setProperty(p, v) : el.style.removeProperty(p);
  updateBar(res);
  redraw();
}

function wireQuick() {
  const live = (input, prop) => {
    input.addEventListener('input', () => { const el = byId(S.selected); if (el) el.style.setProperty(prop, input.value); });
    input.addEventListener('change', () => quickStyle({ [prop]: input.value }));
  };
  live($('q-color'), 'color');
  live($('q-bg'), 'background-color');
  const size = (delta) => {
    const el = byId(S.selected);
    if (!el) return;
    const px = parseFloat(win().getComputedStyle(el).fontSize) || 16;
    quickStyle({ 'font-size': Math.max(6, Math.round(px + delta)) + 'px' });
  };
  $('q-smaller').onclick = () => size(-2);
  $('q-bigger').onclick = () => size(2);
  $('q-bold').onclick = () => { const el = byId(S.selected); if (el) quickStyle({ 'font-weight': Number(win().getComputedStyle(el).fontWeight) >= 600 ? '400' : '700' }); };
  $('q-italic').onclick = () => { const el = byId(S.selected); if (el) quickStyle({ 'font-style': win().getComputedStyle(el).fontStyle === 'italic' ? 'normal' : 'italic' }); };
  document.querySelectorAll('[data-align]').forEach((b) => { b.onclick = () => quickStyle({ 'text-align': b.dataset.align }); });
  $('q-hide').onclick = async () => { await quickStyle({ display: 'none' }); toast('Hidden. Undo brings it back.'); };
  $('step-out').onclick = () => {
    const el = byId(S.selected);
    const up = el && el.parentElement ? el.parentElement.closest('[data-she-id]') : null;
    if (up && up.tagName !== 'HTML') select(up); else toast('Already at the top.');
  };
  $('edit-text').onclick = () => { const el = byId(S.selected); if (el) startEdit(el); };
}

// ------------------------------------------------------------------ toolbar
function updateBar(st) {
  if (!st || st.dirty === undefined) return;
  S.state = { ...(S.state || {}), ...st };
  const status = $('status');
  status.textContent = st.dirty ? `● ${st.changes || ''} unsaved change${st.changes === 1 ? '' : 's'}`.replace('●  ', '● ') : 'All changes saved';
  status.classList.toggle('dirty', st.dirty);
  $('save').disabled = !st.dirty;
  $('discard').disabled = !st.dirty;
  $('undo').disabled = !st.can_undo;
}

async function save() {
  if (S.editing) await commitEdit();
  const res = await api.post('/api/save');
  toast(res.message, !res.ok);
  updateBar(res);
}
async function undo() {
  if (S.editing) return;
  const res = await api.post('/api/undo');
  toast(res.message);
  updateBar(res);
}

function setMode(mode) {
  if (S.editing) commitEdit();
  S.mode = mode;
  $('mode-edit').classList.toggle('on', mode === 'edit');
  $('mode-interact').classList.toggle('on', mode === 'interact');
  $('frame-hint').textContent = mode === 'edit' ? 'Click anything to select it · double-click text to type · Esc to stop' : 'Interact: the page works normally. Switch back to Select & edit to change it.';
  $('frame-hint').classList.remove('gone');
  setTimeout(() => $('frame-hint').classList.add('gone'), 3500);
  applyModeClasses();
}

// ------------------------------------------------------------------ theme panel
function renderTheme(info) {
  const vars = $('vars');
  vars.innerHTML = '';
  if (!info.vars.length) vars.innerHTML = '<p class="muted small">This page has no theme variables. Ask the assistant for page-wide looks ("make every heading teal"); it adds page rules.</p>';
  for (const v of info.vars) {
    const row = document.createElement('div');
    row.className = 'var';
    const isColor = /^#([0-9a-f]{3,8})$|^rgba?\(/i.test(v.value.trim());
    row.innerHTML = `<span class="name"></span><span class="ctx"></span><span class="inputs">${isColor ? '<input type="color">' : ''}<input type="text"></span>`;
    row.querySelector('.name').textContent = v.name;
    row.querySelector('.ctx').textContent = v.context;
    const text = row.querySelector('input[type=text]');
    text.value = v.value;
    const send = async (value) => {
      const res = await api.post('/api/var', { var: v.id, value });
      if (!res.ok) toast(res.error, true); else updateBar(res);
    };
    text.addEventListener('change', () => send(text.value));
    const color = row.querySelector('input[type=color]');
    if (color) {
      color.value = toColorInput(v.value.trim().length === 4 ? v.value.trim().replace(/^#(.)(.)(.)$/, '#$1$1$2$2$3$3') : v.value);
      color.addEventListener('input', () => { text.value = color.value; try { doc().documentElement.style.setProperty(v.name, color.value); } catch { /* ignore */ } });
      color.addEventListener('change', () => send(color.value));
    }
    vars.appendChild(row);
  }
  const rules = $('rules');
  rules.innerHTML = info.rules.length ? '' : '<p class="muted small">None yet.</p>';
  for (const r of info.rules) {
    const row = document.createElement('div');
    row.className = 'rule';
    row.innerHTML = '<span></span><button title="Remove this rule">✕</button>';
    row.querySelector('span').textContent = `${r.selector} { ${r.declarations} }`;
    row.querySelector('button').onclick = async () => { const res = await api.post('/api/rule', { selector: r.selector, declarations: '' }); updateBar(res); refreshInfo(); };
    rules.appendChild(row);
  }
  $('summary').textContent = info.summary;
}

async function refreshInfo() {
  S.info = await api.get('/api/info');
  renderTheme(S.info);
  const h = S.info.health;
  const box = $('health');
  box.hidden = h.ok && !h.test_mode;
  box.textContent = h.test_mode ? 'Test mode: the assistant is a scripted stand-in (send FAKE: [steps]).' : h.problems.join(' ');
}

// ------------------------------------------------------------------ chat
function addMsg(cls, text, meta) {
  const m = document.createElement('div');
  m.className = 'msg ' + cls;
  m.textContent = text;
  if (meta) { const s = document.createElement('span'); s.className = 'meta'; s.textContent = meta; m.appendChild(s); }
  $('messages').appendChild(m);
  $('messages').scrollTop = $('messages').scrollHeight;
  return m;
}

async function sendChat(e) {
  e.preventDefault();
  const text = $('prompt').value.trim();
  if (!text || S.chatBusy) return;
  if (S.editing) await commitEdit();
  S.chatBusy = true;
  $('send').disabled = true;
  $('prompt').value = '';
  addMsg('user', text);
  const wait = addMsg('bot thinking', 'Working…');
  try {
    const res = await api.post('/api/chat', { message: text });
    wait.remove();
    if (res.error && !res.reply) addMsg('err', res.error);
    else {
      const meta = res.cost ? `≈ ${res.cost.cents.toFixed(2)}¢ · chat ≈ ${res.chat_cents.toFixed(2)}¢ (estimate)` : '';
      addMsg('bot', res.reply, meta);
      if (res.edits) refreshInfo();
    }
  } catch (err) {
    wait.remove();
    addMsg('err', 'The editor server did not answer: ' + err);
  } finally {
    S.chatBusy = false;
    $('send').disabled = false;
    $('prompt').focus();
  }
}

// ------------------------------------------------------------------ polling
async function poll() {
  let st;
  try { st = await api.get('/api/state'); } catch { $('status').textContent = 'Editor stopped'; return setTimeout(poll, 2000); }
  updateBar(st);
  $('disk-banner').hidden = !st.on_disk_changed;
  if (!S.loading && !S.editing && st.reload_seq !== S.loadedReload) {
    await loadFrame();
    if (S.version !== st.version && !$('tab-theme').hidden) refreshInfo();
  }
  S.version = st.version;
  if (st.select_seq !== S.selectSeq) {
    S.selectSeq = st.select_seq;
    const el = byId(st.selected);
    if (el && st.selected !== S.selected) select(el, { fromServer: true, scroll: true });
  }
  const req = st.styles_req;
  if (req && req.id !== S.lastStylesReq && !S.loading && S.loadedReload >= req.after) {
    S.lastStylesReq = req.id;
    const el = byId(req.node);
    api.post('/api/styles', { id: req.id, info: el ? looksChain(el) : { chain: [] } });
  }
  setTimeout(poll, 600);
}

// ------------------------------------------------------------------ start
async function start() {
  S.hideData = store.get('she-hide-data') === '1';
  $('hide-data').checked = S.hideData;
  await refreshInfo();
  $('file-name').textContent = S.info.file;
  document.title = S.info.file + ' · Smart HTML Editor';
  updateBar(S.info);
  S.selectSeq = S.info.select_seq;
  wireQuick();
  $('mode-edit').onclick = () => setMode('edit');
  $('mode-interact').onclick = () => setMode('interact');
  $('hide-data').onchange = (e) => { S.hideData = e.target.checked; store.set('she-hide-data', S.hideData ? '1' : '0'); applyModeClasses(); };
  $('save').onclick = save;
  $('undo').onclick = undo;
  $('discard').onclick = async () => {
    if (!confirm('Discard every unsaved change?')) return;
    const res = await api.post('/api/discard'); toast(res.message); updateBar(res);
  };
  $('reload-disk').onclick = async () => {
    if (S.state && S.state.dirty && !confirm('Reload from disk and lose your unsaved changes?')) return;
    const res = await api.post('/api/reload'); toast(res.message); updateBar(res); refreshInfo();
  };
  document.querySelectorAll('.tabs button').forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll('.tabs button').forEach((x) => x.classList.toggle('on', x === b));
      $('tab-assistant').hidden = b.dataset.tab !== 'assistant';
      $('tab-theme').hidden = b.dataset.tab !== 'theme';
      if (b.dataset.tab === 'theme') refreshInfo();
    };
  });
  $('ask').addEventListener('submit', sendChat);
  $('prompt').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) sendChat(e); });
  $('new-chat').onclick = async () => {
    await api.post('/api/chat/reset');
    $('messages').querySelectorAll('.msg:not(.sys)').forEach((m) => m.remove());
    $('cost').textContent = '';
  };
  document.addEventListener('keydown', (e) => {
    if (isTyping(e)) return globalKeys(e);
    if (e.key === 'e' || e.key === 'E') setMode('edit');
    else if (e.key === 'i' || e.key === 'I') setMode('interact');
    else globalKeys(e);
  });
  window.addEventListener('beforeunload', (e) => { if (S.state && S.state.dirty) { e.preventDefault(); e.returnValue = ''; } });
  setTimeout(() => $('frame-hint').classList.add('gone'), 5000);
  await loadFrame();
  poll();
}

start();
