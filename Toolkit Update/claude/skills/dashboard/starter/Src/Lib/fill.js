// Puts a section's data rows into its copied design-library item, at every draw (data or filter change).
// Only the data lists are replaced; everything else in the copy (names, colours, axis ranges, labels) is kept, so
// hand edits survive. The wiring sits at the top of each section file:
//   slots:  which column fills which slot of the item: { label: 'region', value: ['paid_amount'] };
//           '*' = every column not used by another slot; a number = a figure given as is
//   names:  words the reader sees for a column (legend, table headings): { paid_amount: 'Paid' }
//   format: number format per column: '$short' ($4.1M), 'short', 'comma', '$comma', 'pct' (12%, values 0-100),
//           '.1%' (a fraction as a percent), 'month' (2025-06 -> Jun 25), or a pattern like '{value} days'
// Rules follow the design library's AUTHORING.md, "Adding an item to a project". The chart part runs in Node too
// (Tools/new-section.mjs writes the first copy with it); the HTML part needs a browser.
import { FORMATS } from './format.js';

export const SAMPLE_WORDS = ['Sample values', 'What is measured, the period and the basis', 'Heading: what', 'Caption: the'];
export const FORMAT_NAMES = ['$short', 'short', 'comma', ',', '$comma', '$,', '$', 'pct', 'month'];
export const goodFormat = (s) => FORMAT_NAMES.includes(s) || /^\$?\.\d%$/.test(s) || String(s).includes('{');
const AXIS_TYPES = ['category', 'value', 'time', 'log'];
const STATES = /^(good|bad|neutral|over|under|up|down|dn)$/;
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const clone = (o) => (o === undefined ? o : JSON.parse(JSON.stringify(o)));
export const pretty = (c) => String(c).replace(/_/g, ' ').replace(/^./, (x) => x.toUpperCase());

// ---- number formats
const abbreviate = (a) => {
  const [div, unit] = a >= 1e9 ? [1e9, 'B'] : a >= 1e6 ? [1e6, 'M'] : a >= 1e3 ? [1e3, 'K'] : [1, ''];
  const n = a / div;
  return (unit ? n.toFixed(n < 10 ? 1 : 0).replace(/\.0$/, '') : n.toLocaleString('en-US', { maximumFractionDigits: 2 })) + unit;
};

/** One value as text in a column's format. */
export function fmt(v, spec = '') {
  if (v === null || v === undefined || v === '') return '';
  if (spec === 'month') return FORMATS.month(v);
  if (!isNum(v)) return String(v);
  const s = String(spec || '');
  if (s.includes('{')) return s.replace(/\{(?:value|c)(?::\w+)?\}/g, () => fmt(v, /\{(?:value|c):short\}/.test(s) ? 'short' : 'comma'));
  const cur = s.startsWith('$') ? '$' : '';
  const rest = cur ? s.slice(1) : s;
  const sign = v < 0 ? '-' : '';
  const a = Math.abs(v);
  if (/^\.\d%$/.test(rest)) return `${sign}${(a * 100).toFixed(Number(rest[1]))}%`;
  if (rest === 'pct') return `${sign}${a.toLocaleString('en-US', { maximumFractionDigits: a < 10 ? 1 : 0 })}%`;
  if (rest === 'short') return sign + cur + abbreviate(a);
  if (rest === 'comma' || rest === ',' || cur) return sign + cur + a.toLocaleString('en-US', { maximumFractionDigits: cur ? 0 : 2 });
  return sign + a.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

/** A column format as a formatter pattern the page's host-runtime understands (tooltips included); token is
 *  'value' (axes) or 'c' (labels). null when the format needs code (a fraction shown as a percent). */
export function pattern(spec, token = 'c') {
  const s = String(spec || '');
  if (s.includes('{')) return s.replace(/\{(value|c)(:\w+)?\}/g, (m, t, f) => `{${token}${f ?? ''}}`);
  const cur = s.startsWith('$') ? '$' : '';
  const rest = cur ? s.slice(1) : s;
  if (rest === 'short') return `${cur}{${token}:short}`;
  if (rest === 'comma' || rest === ',' || (cur && !rest)) return `${cur}{${token}:comma}`;
  if (rest === 'pct') return `{${token}}%`;
  if (!s || s === 'month') return `{${token}:comma}`;
  return null;
}

// ---- wiring
const asList = (v) => (Array.isArray(v) ? v : v === undefined || v === null ? [] : [v]);

/** { slot: [column | number, ...] } with '*' expanded against the data's columns. */
export function slotMap(slots = {}, columns = []) {
  const used = new Set(Object.values(slots).flatMap(asList).filter((c) => typeof c === 'string' && c !== '*'));
  return Object.fromEntries(Object.entries(slots).map(([k, v]) => [k, asList(v).flatMap((c) => (c === '*' ? columns.filter((x) => !used.has(x)) : [c]))]));
}

export const columnsOf = (rows) => [...new Set((rows ?? []).flatMap((r) => (r && typeof r === 'object' ? Object.keys(r) : [])))];

class Fill {
  constructor(rows, wiring = {}) {
    this.rows = rows ?? [];
    this.cols = columnsOf(this.rows);
    this.smap = slotMap(wiring.slots, this.cols);
    this.names = wiring.names ?? {};
    this.fmts = wiring.format ?? {};
    this.problems = [];
    this.dropped = [];
    // slots set to null: not filled yet (MANUAL); their marks keep the item's sample data
    this.todo = new Set(Object.entries(wiring.slots ?? {}).filter(([, v]) => v === null).map(([k]) => k));
  }
  label(c) { return String(this.names[c] ?? pretty(c)); }
  fmt(c) { return this.fmts[c] ?? this.fmts['*'] ?? ''; }
  need(c) {
    if (typeof c === 'string' && !this.cols.includes(c) && this.rows.length) {
      this.problems.push(`slots name "${c}", which is not a column of the data (columns: ${this.cols.join(', ') || 'none'})`);
      return false;
    }
    return true;
  }
  column(c) {
    if (!this.need(c)) return [];
    const v = this.rows.map((r) => r[c] ?? null);
    while (v.length && v.at(-1) === null) v.pop();
    return v;
  }
  /** a value shown as text: its format, or its reader words when the value is itself a column name. In a row that
   *  names a column in its label (a totals section: one row per measure), the value takes that column's format. */
  show(v, c, row) {
    if (typeof v === 'string' && this.names[v] !== undefined) return String(this.names[v]);
    const own = row && typeof row.label === 'string' && c !== 'label' ? this.fmts[row.label] : undefined;
    return fmt(v, own ?? this.fmt(c));
  }
  figure(c) {
    if (typeof c === 'string' && this.cols.includes(c)) return this.column(c).find((v) => v !== null) ?? null;
    return typeof c === 'string' && /^-?\d+(\.\d+)?$/.test(c) ? Number(c) : c;
  }
}

const slotNames = (spec) => String(spec).split(':')[0].split(',').map((s) => s.trim().replace(/^=/, ''));   // "=value" follows the value slot

function marks(o) {
  const out = [];
  const go = (x, parent, key) => {
    if (Array.isArray(x)) x.forEach((v, i) => go(v, x, i));
    else if (x && typeof x === 'object') {
      if (typeof x.slot === 'string') out.push([x, parent, key]);
      for (const k of Object.keys(x)) go(x[k], x, k);
    }
  };
  go(o, null, null);
  return out;
}

function restyle(old, v) {
  if (!old || typeof old !== 'object' || Array.isArray(old) || !('value' in old)) return v;
  const o = clone(old);
  o.value = v;
  if (o.label && typeof o.label === 'object') {
    delete o.label.formatter;
    if (!Object.keys(o.label).length) delete o.label;
  }
  return o;
}

function dropColour(o) {
  for (const k of ['itemStyle', 'lineStyle', 'areaStyle', 'endLabel', 'label']) {
    if (o[k] && typeof o[k] === 'object') {
      delete o[k].color;
      delete o[k].borderColor;
    }
  }
}

const axesOf = (o, key) => asList(o[key]).filter((a) => a && typeof a === 'object');

/** Fills a chart's slots in place. first: as when adding (series names left to `names`, the sample's fixed
 *  value-axis ranges dropped, sample label formats tied to the column format). Returns the problems found. */
export function fillChart(o, rows, wiring, { first = false } = {}) {
  const f = new Fill(rows, wiring);
  const filled = new Map();   // series object -> column
  const pairs = new Map();    // "x,y" series -> [x column, y column]
  const single = new Map();   // "x,y" series with one number part -> its index (its {@[i]} is that number)
  const done = new Set();
  const removable = (m) => Array.isArray(m[1]) && !AXIS_TYPES.includes(String(m[0].type ?? ''));
  const remove = (m) => {
    if (removable(m)) {
      const i = m[1].indexOf(m[0]);
      if (i >= 0) m[1].splice(i, 1);
    }
  };
  const categories = (c) => [...new Set(f.column(c).filter((v) => v !== null).map((v) => f.show(v, c)))];
  const names = [...new Set(marks(o).flatMap((m) => slotNames(m[0].slot)))];
  const isAxis = (m) => AXIS_TYPES.includes(String(m[0].type ?? ''));
  const drop = (m, name) => {
    if (!removable(m)) return;
    if (m[0].type && !first) f.problems.push(`series "${m[0].name || m[0].type}" (slot ${name}) left out: no column for it`);
    else if (m[0].type && first) f.dropped.push(`series "${m[0].name || m[0].type}" (slot ${name}) left out: no column for it`);
    remove(m);
  };
  for (const name of names) {
    if (f.todo.has(name)) {
      f.problems.push(`slot ${name} is not filled yet: it shows the item's sample data (MANUAL)`);
      continue;
    }
    const ms = marks(o).filter((m) => slotNames(m[0].slot).includes(name));
    const cols = f.smap[name] ?? [];
    if (ms.some((m) => m[0].slot.includes(':'))) {   // "target:yAxis": one property takes a figure
      for (const m of ms) {
        const prop = m[0].slot.split(':')[1];
        if (cols.length) m[0][prop] = f.figure(cols[0]);
        else remove(m);
      }
      continue;
    }
    const tuple = ms.filter((x) => slotNames(x[0].slot).length > 1);
    for (const m of tuple) {   // "x,y": rows of [x, y]; a row with an empty cell is left out
      if (done.has(m[0])) continue;
      done.add(m[0]);
      const parts = slotNames(m[0].slot);
      if (parts.some((p) => f.todo.has(p))) continue;   // a part not filled yet: the sample points stay
      if (parts.some((p) => !(f.smap[p] ?? []).length)) {
        drop(m, name);
        continue;
      }
      if (!parts.every((p) => f.need(f.smap[p][0]))) continue;
      const old = m[0].data ?? [];
      const data = f.rows.map((r) => parts.map((p) => r[f.smap[p][0]] ?? null)).filter((t) => t.every((v) => v !== null));
      m[0].data = data.map((t, i) => restyle(old[i], t));
      // the point's one number column (a [value, "name"] point), for its format; else its second part
      const numeric = parts.map((p, k) => [k, f.smap[p][0]]).filter(([, c]) => data.some((t) => typeof t[parts.findIndex((q) => f.smap[q][0] === c)] === 'number'));
      filled.set(m[0], numeric.length === 1 ? numeric[0][1] : f.smap[parts[1] ?? parts[0]][0]);
      if (numeric.length === 1) single.set(m[0], numeric[0][0]);
      pairs.set(m[0], [f.smap[parts[0]][0], f.smap[parts[1] ?? parts[0]][0]]);
      if (first) delete m[0].name;
    }
    if (tuple.length === ms.length) continue;
    // every marked axis takes the slot's first column (panels share one category column)
    for (const m of ms.filter((x) => slotNames(x[0].slot).length === 1 && isAxis(x))) {
      if (!cols.length) continue;
      m[0].data = m[0].type === 'category' ? categories(cols[0]) : f.column(cols[0]);
    }
    // a follower ("slot": "=value", a lollipop's dot) takes the slot's first column too, never counting as one of its series
    for (const m of ms.filter((x) => /^=/.test(x[0].slot))) {
      if (!cols.length) {
        drop(m, name);
        continue;
      }
      const old = m[0].data ?? [];
      m[0].data = f.column(cols[0]).map((v, k) => restyle(old[k], v));
      filled.set(m[0], cols[0]);
    }
    const plain = ms.filter((m) => slotNames(m[0].slot).length === 1 && !isAxis(m) && !/^=/.test(m[0].slot));
    if (!plain.length) continue;
    if (!cols.length) {
      [...plain].reverse().forEach((m) => drop(m, name));
      continue;
    }
    cols.forEach((c, i) => {
      let obj;
      if (i < plain.length) obj = plain[i][0];
      else {   // more columns than marked series: repeat the last one, without its fixed colours
        const last = plain.at(-1);
        obj = clone(last[0]);
        dropColour(obj);
        delete obj.name;
        if (Array.isArray(last[1])) last[1].splice(last[1].indexOf(last[0]) + (i - plain.length) + 1, 0, obj);
      }
      if (obj.type === 'category') {
        obj.data = categories(c);
        return;
      }
      const old = obj.data ?? [];
      obj.data = f.column(c).map((v, k) => restyle(old[k], v));
      if (obj.type && obj.type !== 'value') {
        if (first) delete obj.name;
        else if (!obj.name) obj.name = f.label(c);
        filled.set(obj, c);
      }
    });
    for (const m of [...plain.slice(cols.length)].reverse()) drop(m, name);
  }
  const series = asList(o.series).filter((s) => s && typeof s === 'object');
  if (f.rows.length) {   // a series that ends up with nothing to draw
    for (const s of series) {
      if (typeof s.slot === 'string' && Array.isArray(s.data) && !s.data.some((d) => (d && typeof d === 'object' && !Array.isArray(d) ? d.value : d) !== null && (d && typeof d === 'object' && !Array.isArray(d) ? d.value : d) !== undefined)) {
        f.problems.push(`series "${s.name || s.type}" (slot ${s.slot}) has no data`);
      }
    }
  }
  const axisCol = (key, j) => series.map((s) => filled.has(s) && Number(s[`${key}Index`] ?? 0) === j && (pairs.get(s)?.[key === 'xAxis' ? 0 : 1] ?? filled.get(s))).find(Boolean);
  if (first && names.length) {
    for (const key of ['xAxis', 'yAxis']) {
      axesOf(o, key).forEach((a, j) => {
        if ((a.type ?? (key === 'yAxis' ? 'value' : 'category')) !== 'value' || a.show === false) return;
        for (const k of ['min', 'max', 'interval']) delete a[k];
        const c = axisCol(key, j);
        if (c && typeof a.axisLabel?.formatter === 'string') a.axisLabel.formatter = tieFormat(a.axisLabel.formatter, 'value');
        if (c && typeof a.name === 'string' && a.name) a.name = f.label(c);
      });
    }
    for (const s of series) {
      if (!filled.has(s)) continue;
      for (const k of ['label', 'endLabel']) {
        if (typeof s[k]?.formatter !== 'string') continue;
        if (single.has(s)) s[k].formatter = s[k].formatter.replace(new RegExp(`\\$?\\{@\\[${single.get(s)}\\]\\}(%|[KMB](?![a-z]))?`, 'g'), '{c:fmt}');
        s[k].formatter = tieFormat(s[k].formatter, 'c');
      }
      for (const ml of [s.markLine, s.markPoint]) if (ml?.label && typeof ml.label.formatter === 'string') ml.label.formatter = /\{/.test(ml.label.formatter) ? tieFormat(ml.label.formatter, 'c') : '{c:fmt}';
    }
  }
  if (first) return [...f.problems, ...f.dropped];   // the copy keeps {c:fmt}: the column's format applies at every draw
  // a waterfall whose bars all sit well above zero: the value axis starts near the lowest bar (unless set)
  const base = series.find((x) => x.slot === 'base');
  const totalS = series.find((x) => x.slot === 'total');
  const axis = axesOf(o, 'yAxis')[0];
  if (base && totalS && axis && axis.min === undefined && axis.type !== 'category') {
    const v = (d) => (d && typeof d === 'object' ? d.value : d);
    const lows = (base.data ?? []).map((b, i) => (isNum(v(totalS.data?.[i])) ? v(totalS.data[i]) : v(b))).filter(isNum);
    const low = Math.min(...lows);
    const high = Math.max(...lows);
    if (lows.length && low > 0 && low > 0.3 * high) {
      const step = 10 ** Math.floor(Math.log10(Math.max(high - low, low * 0.05)));
      axis.min = Math.floor((low - (high - low) * 0.15) / step) * step;
    }
  }
  // the column formats: {c:fmt} / {value:fmt} become the column's pattern; unformatted labels and axes get it too
  const resolve = (x, c, token) => {
    const p = pattern(f.fmt(c), token) ?? `{${token}}`;
    return x.replace(/\$?\{(c|value):fmt\}%?/g, () => p);
  };
  // a point [value, "name"] whose label prints its number raw ({@[0]}, e.g. a part filled after adding): the column's format
  for (const s of series) {
    if (!single.has(s)) continue;
    for (const k of ['label', 'endLabel']) {
      if (typeof s[k]?.formatter === 'string') s[k].formatter = s[k].formatter.replace(new RegExp(`\\$?\\{@\\[${single.get(s)}\\]\\}(%|[KMB](?![a-z]))?`, 'g'), '{c:fmt}');
    }
  }
  const codeFormats = [];
  for (const s of series) {
    const c = filled.get(s);
    walkFormatters(s, (holder) => {
      holder.formatter = resolve(holder.formatter, c, 'c');
    });
    if (c && s.label && typeof s.label === 'object' && s.label.formatter === undefined) {
      const p = pattern(f.fmt(c), 'c');
      if (p) s.label.formatter = p;
      else if (f.fmt(c)) codeFormats.push([s.label, f.fmt(c)]);
    }
  }
  for (const key of ['xAxis', 'yAxis']) {
    axesOf(o, key).forEach((a, j) => {
      const c = axisCol(key, j);
      if (typeof a.axisLabel?.formatter === 'string') a.axisLabel.formatter = resolve(a.axisLabel.formatter, c, 'value');
      if ((a.type ?? (key === 'yAxis' ? 'value' : 'category')) !== 'value' || !c || a.axisLabel?.formatter !== undefined) return;
      const p = pattern(f.fmt(c), 'value');
      a.axisLabel = { ...(a.axisLabel ?? {}) };
      if (p) a.axisLabel.formatter = p;
      else if (f.fmt(c)) codeFormats.push([a.axisLabel, f.fmt(c)]);
    });
  }
  // formats that need code (a fraction as a percent): a function, set after the host has prepared the option
  o.__code = codeFormats;
  return f.problems;
}

function walkFormatters(x, fn) {
  if (Array.isArray(x)) x.forEach((v) => walkFormatters(v, fn));
  else if (x && typeof x === 'object') {
    if (typeof x.formatter === 'string' && /\{(c|value):fmt\}/.test(x.formatter)) fn(x);
    for (const k of Object.keys(x)) if (k !== 'data') walkFormatters(x[k], fn);
  }
}

/** "+${c}" -> "+{c:fmt}", "{value}%" -> "{value:fmt}": a sample label's number tied to the column's format. */
function tieFormat(t, token) {
  return t.replace(new RegExp(`\\$?\\{${token}(?::(?:short|comma))?\\}(%|[KMB](?![a-z]))?`, 'g'), `{${token}:fmt}`);
}

/** After ItemHost.prepare: formats the host cannot express become functions. */
export function codeFormats(o) {
  for (const [holder, spec] of o.__code ?? []) holder.formatter = (p) => fmt(p && typeof p === 'object' ? (Array.isArray(p.value) ? p.value.at(-1) : p.value) : p, spec);
  delete o.__code;
  return o;
}

// ---- HTML items (tables, hero cards): browser only
/** The block with its rows repeated and slots filled. text(s) fills free text ({metric|format}). */
export function fillHtml(markup, rows, wiring, text = null) {
  const f = new Fill(rows, wiring);
  const records = [];   // an item that builds itself from records keeps them in JSON marked like a chart
  markup = String(markup).replace(/(<script type="application\/json"[^>]*>)([\s\S]*?)(<\/script>)/g, (m, a, j, b) => {
    try {
      const o = JSON.parse(j);
      records.push(...fillChart(o, rows, wiring));
      delete o.__code;
      return a + JSON.stringify(o).replace(/<\//g, '<\\/') + b;
    } catch {
      return m;
    }
  });
  const tpl = document.createElement('template');
  tpl.innerHTML = markup;
  const root = tpl.content;
  for (const box of root.querySelectorAll('[data-rows]')) {   // keep one row: the template
    const kids = [...box.children];
    const keep = kids.find((k) => k.hasAttribute('data-template')) ?? kids[0];
    for (const k of kids) if (k !== keep) k.remove();
  }
  expandColumns(root, f, true);
  const apply = (el, row, inHead) => {
    for (const tok of (el.getAttribute('data-slot') ?? '').split(/\s+/).filter(Boolean)) {
      const [nameIdx, prop] = tok.split('@');
      const [name, idx] = nameIdx.split('=');
      if (f.todo.has(name)) {   // not filled yet: the sample text stays
        if (!f.problems.some((p) => p.startsWith(`slot ${name} `))) f.problems.push(`slot ${name} is not filled yet: it shows the item's sample data (MANUAL)`);
        continue;
      }
      const cols = f.smap[name] ?? [];
      const c = idx !== undefined ? cols[Number(idx)] : cols[0];
      if (c === undefined) {
        if (!prop && !row && !inHead) el.textContent = '';
        continue;
      }
      let v;
      if (inHead) v = f.label(c);
      else if (row) v = f.need(c) ? row[c] ?? null : null;
      else v = f.figure(c);
      const shown = inHead ? v : f.show(v, c, row);
      if (!prop) el.textContent = shown;
      else if (prop === 'class') {
        const cls = [...el.classList].filter((x) => !STATES.test(x));
        if (v !== null && v !== '') cls.push(String(v));
        el.className = cls.join(' ');
      } else if (/^(aria-|title$)/.test(prop)) el.setAttribute(prop, shown);
      else if (v !== null && v !== '') el.style.setProperty(prop, /^-?\d+(\.\d+)?$/.test(String(v)) ? `${v}%` : String(v));
    }
    el.setAttribute('data-slot', (el.getAttribute('data-slot') ?? '').replace(/=[^@\s]+/g, ''));
  };
  for (const box of root.querySelectorAll('[data-rows]')) {
    const t = box.firstElementChild;
    if (!t) continue;
    t.remove();
    for (const r of f.rows) {
      const k = t.cloneNode(true);
      k.removeAttribute('data-template');
      k.classList.remove('on');
      if (!k.classList.length) k.removeAttribute('class');
      for (const el of [k, ...k.querySelectorAll('[data-slot]')]) if (el.hasAttribute('data-slot')) apply(el, r, false);
      box.appendChild(k);
    }
  }
  for (const el of root.querySelectorAll('[data-slot]')) {
    if (el.closest('[data-rows]')) continue;
    apply(el, null, Boolean(el.closest('thead')));
  }
  if (text) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (n.parentElement?.closest('script, style, [data-slot]')) continue;
      if (/\{[^{}|]+\|[^{}]+\}/.test(n.nodeValue)) n.nodeValue = text(n.nodeValue);
    }
  }
  const div = document.createElement('div');
  div.appendChild(root.cloneNode(true));
  return { html: div.innerHTML, problems: [...f.problems, ...records] };
}

/** A cell whose slot has several columns repeats once per column; extra sample cells of that slot go. */
function expandColumns(parent, f, keep) {
  const done = new Set();
  for (const c of [...parent.children]) {
    const spec = c.getAttribute('data-slot');
    const t = spec ? (spec.split(/\s+/).find((x) => !x.includes('@')) ?? '') : '';
    if (t) {
      if (done.has(t)) {
        c.remove();
        continue;
      }
      done.add(t);
      const cols = f.smap[t] ?? [];
      if (!cols.length) {
        if (!keep && !f.todo.has(t)) c.remove();
        continue;
      }
      let at = c;
      for (let i = 1; i < cols.length; i++) {
        const k = c.cloneNode(true);
        k.setAttribute('data-slot', spec.replace(new RegExp(`(^|\\s)${t}(@|\\s|$)`), `$1${t}=${i}$2`));
        at.after(k);
        at = k;
      }
      if (cols.length > 1) c.setAttribute('data-slot', spec.replace(new RegExp(`(^|\\s)${t}(@|\\s|$)`), `$1${t}=0$2`));
    }
  }
  for (const c of [...parent.children]) if (!['SCRIPT', 'STYLE'].includes(c.tagName)) expandColumns(c, f, keep && !c.hasAttribute('data-rows') && c.tagName !== 'THEAD');
}

/** How many series (not axes, not followers) each slot marks in a chart option. */
export function seriesPerSlot(o) {
  const out = {};
  for (const [m] of marks(o)) {
    if (AXIS_TYPES.includes(String(m.type ?? '')) || /^=/.test(m.slot) || m.slot.includes(':') || m.slot.includes(',')) continue;
    out[m.slot] = (out[m.slot] ?? 0) + 1;
  }
  return out;
}

/** What a slot mapping is missing against an item's data note ([{ name, kind, count }]). */
export function checkSlots(note, slots = {}) {
  const out = [];
  for (const s of note) {
    const n = new Set(asList(slots[s.name])).size;   // one column named for several series counts once
    const star = asList(slots[s.name]).includes('*');
    if (s.count === 'one' && n !== 1 && !star) out.push(`${s.name} needs one column`);
    if (s.count === 'one or more' && n < 1) out.push(`${s.name} needs one or more columns`);
    if (s.count === 'optional' && n > 1) out.push(`${s.name} takes at most one column`);
  }
  const known = note.map((s) => s.name);
  for (const k of Object.keys(slots)) if (!known.includes(k)) out.push(`${k} is not a slot of this item (its slots: ${known.join(', ')})`);
  return out;
}
