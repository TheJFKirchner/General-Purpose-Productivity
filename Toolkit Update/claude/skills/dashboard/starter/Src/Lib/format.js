// Number formats (FORMATS, also used by sections when drawing) and section notes: text with {metric|format} or
// {metric|format:arg} references, never typed numbers. Metric values come from the section's analytic
// ("metrics" in its result) for the current filters, so a note updates with filters and survives export.
// Bad reference (unknown metric/format) -> visible "[missing: ...]"; Tools/check.mjs fails on it.
// Metric that is null (e.g. not enough history) -> "n/a".

const NA = 'n/a';
const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** 913200 -> "913.2K", 150000 -> "150K", 90 -> "90": a decimal only when it says something */
const abbreviate = (v) => {
  const a = Math.abs(v);
  const [div, unit] = a >= 1e9 ? [1e9, 'B'] : a >= 1e6 ? [1e6, 'M'] : a >= 1e3 ? [1e3, 'K'] : [1, ''];
  return `${(a / div).toFixed(unit ? 1 : 0).replace(/\.0$/, '')}${unit}`;
};

export const FORMATS = {
  // percent of a fraction (0.052 -> "5.2%"); shows magnitude only, pair with {x|direction} for the sign
  pct: (v, arg = '1') => {
    const d = Number(arg);
    if (!Number.isInteger(d) || d < 0 || d > 6) throw new Error(`pct decimals must be 0-6, got "${arg}"`);
    return isNum(v) ? `${(Math.abs(v) * 100).toFixed(d)}%` : NA;
  },
  // difference of two rates (0.06) -> "6.0 points"; magnitude only, pair with direction or wording for the sign
  pts: (v, arg = '1') => {
    const d = Number(arg);
    if (!Number.isInteger(d) || d < 0 || d > 3) throw new Error(`pts decimals must be 0-3, got "${arg}"`);
    return isNum(v) ? `${(Math.abs(v) * 100).toFixed(d)} points` : NA;
  },
  // currency; default: no decimals unless |v| < 100; money:0 / money:2 force decimals
  money: (v, arg) => {
    const d = arg === undefined ? null : Number(arg);
    if (d !== null && (!Number.isInteger(d) || d < 0 || d > 2)) throw new Error(`money decimals must be 0-2, got "${arg}"`);
    if (!isNum(v)) return NA;
    const digits = d ?? (Math.abs(v) < 100 ? 2 : 0);
    return v.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits });
  },
  // short currency: $913.2M, $1.4B, $45.3K
  compact: (v) => (isNum(v) ? `${v < 0 ? '-' : ''}$${abbreviate(v)}` : NA),
  // short plain number (no currency): 913.2M, 1.4B, 45.3K
  short: (v) => (isNum(v) ? `${v < 0 ? '-' : ''}${abbreviate(v)}` : NA),
  // "2026-06" or "2026-06-01" -> "Jun 26" (chart axes and tables)
  month: (v) => {
    const m = /^(\d{4})-(\d{2})/.exec(String(v ?? ''));
    if (m) return `${MONTHS[Number(m[2]) - 1]} ${m[1].slice(2)}`;
    return v === null || v === undefined ? NA : String(v);
  },
  int: (v) => (isNum(v) ? Math.round(v).toLocaleString('en-US') : NA),
  // plain number with N decimals (default 1): 4.8
  num: (v, arg = '1') => {
    const d = Number(arg);
    if (!Number.isInteger(d) || d < 0 || d > 6) throw new Error(`num decimals must be 0-6, got "${arg}"`);
    return isNum(v) ? v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : NA;
  },
  // fractional change in words: "up 5.2%", "down 3.1%", or "flat" within half a percent; arg = decimals (default 1)
  change: (v, arg = '1') => {
    const d = Number(arg);
    if (!Number.isInteger(d) || d < 0 || d > 3) throw new Error(`change decimals must be 0-3, got "${arg}"`);
    if (!isNum(v)) return NA;
    return v > 0.005 ? `up ${(v * 100).toFixed(d)}%` : v < -0.005 ? `down ${(-v * 100).toFixed(d)}%` : 'flat';
  },
  // fractional change -> rose / fell / was flat; arg = flat band in percent (default 0.5)
  direction: (v, arg = '0.5') => {
    const band = Number(arg);
    if (!Number.isFinite(band) || band < 0) throw new Error(`direction band must be a number >= 0, got "${arg}"`);
    if (!isNum(v)) return NA;
    return v > band / 100 ? 'rose' : v < -band / 100 ? 'fell' : 'was flat';
  },
  name: (v) => (v === null || v === undefined || v === '' ? NA : String(v)),
};

const REF = /\{([^{}]*)\}/g;

/** All {…} references in a template: [{ raw, metric, format, arg }]. */
export function parseRefs(template) {
  return [...template.matchAll(REF)].map((m) => {
    const [metric = '', fmt = ''] = m[1].split('|').map((s) => s.trim());
    const [format, arg] = fmt.split(':').map((s) => s.trim());
    return { raw: m[0], inner: m[1], metric, format: format || null, arg: arg || undefined };
  });
}

/** Render one template string with metric values -> { segments: [{ text, missing? }], problems: [string] }. */
export function renderTemplate(template, values = {}) {
  const segments = [];
  const problems = [];
  let last = 0;
  for (const m of template.matchAll(REF)) {
    if (m.index > last) segments.push({ text: template.slice(last, m.index) });
    last = m.index + m[0].length;
    const [ref] = parseRefs(m[0]);
    const fail = (why) => {
      problems.push(`${m[0]}: ${why}`);
      segments.push({ text: `[missing: ${ref.inner}]`, missing: true });
    };
    if (!ref.metric || !(ref.metric in values)) fail(`unknown metric "${ref.metric}" (the section's analytic returns: ${Object.keys(values).join(', ') || 'none'})`);
    else if (!ref.format) fail('no format (use {metric|format})');
    else if (!(ref.format in FORMATS)) fail(`unknown format "${ref.format}"`);
    else {
      try {
        segments.push({ text: FORMATS[ref.format](values[ref.metric], ref.arg) });
      } catch (e) {
        fail(e.message);
      }
    }
  }
  if (last < template.length) segments.push({ text: template.slice(last) });
  return { segments, problems };
}

/** Split a note into blocks: paragraphs and "- " bullet lists. HTML comments are dropped. */
export function parseBlocks(markdown) {
  const clean = markdown.replace(/<!--[\s\S]*?-->/g, '').trim();
  if (!clean) return [];
  return clean.split(/\n\s*\n/).map((chunk) => {
    const lines = chunk.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.every((l) => l.startsWith('- '))) return { type: 'list', items: lines.map((l) => l.slice(2)) };
    return { type: 'p', text: lines.join(' ') };
  });
}

/** A full note with metric values -> { blocks: [{ type, segments | items: segments[] }], problems }. */
export function renderNote(markdown, values = {}) {
  const problems = [];
  const render = (t) => {
    const r = renderTemplate(t, values);
    problems.push(...r.problems);
    return r.segments;
  };
  const blocks = parseBlocks(markdown).map((b) =>
    b.type === 'list' ? { type: 'list', items: b.items.map(render) } : { type: 'p', segments: render(b.text) },
  );
  return { blocks, problems };
}
