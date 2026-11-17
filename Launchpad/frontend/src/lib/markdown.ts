/* Safe markdown subset, ported unchanged from the vanilla page.
   Everything is HTML-escaped FIRST; only tags generated here are added. Headings, paragraphs, bold/italic, inline
   code, code fences, lists (incl. task boxes), tables, quotes, rules. Links [text](target) show the text, styled,
   with the target as a tooltip; they are not clickable (no navigation away from the app).
   The output of md() / docHtml() is the ONLY string ever given to dangerouslySetInnerHTML (see components/Markdown). */
import { STEP_LABEL } from './labels';

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s: unknown): string => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);

function inline(s: string): string {
  return esc(s).split(/(`[^`\n]+`)/g).map(p => /^`[^`]+`$/.test(p) ? `<code>${p.slice(1, -1)}</code>`
    : p.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, '<span class="mdlink" title="$2">$1</span>')
       .replace(/\*\*([^*]+?)\*\*/g, '<b>$1</b>').replace(/(^|[^\w])__([^_]+?)__(?!\w)/g, '$1<b>$2</b>')
       .replace(/(^|[\s(>])\*([^*\s][^*]*?)\*(?=[\s).,;:!?<]|$)/g, '$1<i>$2</i>')
       .replace(/(^|[\s(>])_([^_\s][^_]*?)_(?=[\s).,;:!?<]|$)/g, '$1<i>$2</i>')).join('');
}

export interface FrontMatter { meta: Record<string, unknown>; steps: Record<string, unknown>[]; body: string }

/** Documents with a YAML header (plan.md, agent files): returns the header fields, the step list and the body. */
export function splitFrontMatter(text: unknown): FrontMatter | null {
  const t = String(text ?? '').replace(/\r\n?/g, '\n').replace(/^﻿/, '');
  if (!t.startsWith('---\n')) return null;
  const end = t.indexOf('\n---', 4); if (end < 0) return null;
  const meta: Record<string, unknown> = {}, steps: Record<string, unknown>[] = [];
  for (const line of t.slice(4, end).split('\n')) {
    let m: RegExpMatchArray | null;
    if ((m = line.match(/^\s*-\s*(\{.*\})\s*$/))) {
      let o: Record<string, unknown>;
      try { o = JSON.parse(m[1].replace(/([{,]\s*)([A-Za-z_][\w-]*)\s*:/g, '$1"$2":')); } catch { o = { title: m[1] }; }
      steps.push(o);
    } else if ((m = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/))) {
      let v: unknown = m[2].trim();
      if (v) { try { v = JSON.parse(v as string); } catch { /* keep text */ } }
      meta[m[1]] = v;
    }
  }
  return { meta, steps, body: t.slice(t.indexOf('\n', end + 1) + 1) };
}

/** Markdown with a tidy summary of a YAML header (plan files get named facts + a step list). */
export function docHtml(text: unknown): string {
  const fm = splitFrontMatter(text);
  if (!fm) return md(text);
  const { meta, steps } = fm;
  const planKeys: [string, unknown][] = [['Plan', meta.plan], ['Status', meta.status], ['Date', meta.date], ['Session', meta.session]];
  const facts = (meta.plan != null ? planKeys : Object.entries(meta)).filter(([, v]) => v != null && v !== '' && typeof v !== 'object');
  if (!facts.length && !steps.length) return md(fm.body);
  const stepRows = steps.map(s => {
    const after = s.after as unknown, skills = s.skills as unknown;
    const skillText = Array.isArray(skills) && skills.length ? `skills ${skills.join(', ')}` : s.skill ? `skill ${s.skill}` : '';
    const extra = [s.status ? STEP_LABEL[String(s.status)] || String(s.status) : '', skillText,
      Array.isArray(after) && after.length ? `after step ${after.join(', ')}` : ''].filter(Boolean).join(' · ');
    return `<li><span class="n">${esc(s.n ?? '•')}</span><span>${esc(s.title ?? '')}${extra ? ` <span class="mut">· ${esc(extra)}</span>` : ''}</span></li>`;
  }).join('');
  return `<div class="docmeta">${facts.map(([k, v]) => `<span><b>${esc(k)}</b> ${esc(v)}</span>`).join('')}</div>${stepRows ? `<ol class="steps docsteps">${stepRows}</ol>` : ''}${md(fm.body)}`;
}

function mdTable(rows: string[]): string {
  const cells = (r: string) => r.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
  const isSep = (r: string) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(r);
  let head: string[] | null = null;
  if (rows.length > 1 && isSep(rows[1])) { head = cells(rows[0]); rows = rows.slice(2); }
  const body = rows.filter(r => !isSep(r)).map(cells);
  return `<table>${head ? `<thead><tr>${head.map(c => `<th>${inline(c)}</th>`).join('')}</tr></thead>` : ''}<tbody>${body.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

interface ListState { tag: 'ul' | 'ol'; items: { html: string; sub: boolean }[]; start: number }

/** The safe markdown subset (escape first). */
export function md(text: unknown): string {
  const L = String(text ?? '').replace(/\r\n?/g, '\n').split('\n');
  let out = '', para: string[] = [], list: ListState | null = null, i = 0, m: RegExpMatchArray | null;
  const flushP = () => { if (para.length) { out += `<p>${para.map(inline).join('<br>')}</p>`; para = []; } };
  const flushL = () => { if (list) { const l: ListState = list; out += `<${l.tag}${l.start > 1 ? ` start="${l.start}"` : ''}>${l.items.map(x => `<li${x.sub ? ' class="sub"' : ''}>${x.html}</li>`).join('')}</${l.tag}>`; list = null; } };
  const flush = () => { flushP(); flushL(); };
  while (i < L.length) {
    const line = L[i];
    if (/^\s*```/.test(line)) {
      flush(); const code: string[] = []; i++;
      while (i < L.length && !/^\s*```/.test(L[i])) code.push(L[i++]);
      i++; out += `<pre><code>${esc(code.join('\n'))}</code></pre>`; continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line)) { flush(); const rows: string[] = []; while (i < L.length && /^\s*\|.*\|\s*$/.test(L[i])) rows.push(L[i++]); out += mdTable(rows); continue; }
    if ((m = line.match(/^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/))) { flush(); const lv = m[1].length; out += `<h${Math.min(lv + 2, 6)} class="mh h${Math.min(lv, 3)}">${inline(m[2])}</h${Math.min(lv + 2, 6)}>`; i++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); out += '<hr>'; i++; continue; }
    if (/^\s*>/.test(line)) { flush(); const q: string[] = []; while (i < L.length && (m = L[i].match(/^\s*>\s?(.*)$/))) { q.push(m[1]); i++; } out += `<blockquote>${q.map(inline).join('<br>')}</blockquote>`; continue; }
    if ((m = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
      flushP();
      const tag = /\d/.test(m[2]) ? 'ol' : 'ul', sub = m[1].length >= 2;
      if (!list || ((list as ListState).tag !== tag && !sub)) { flushL(); list = { tag, items: [], start: tag === 'ol' ? parseInt(m[2], 10) || 1 : 1 }; }
      const task = m[3].match(/^\[( |x|X)\]\s+(.*)$/);
      (list as ListState).items.push({ html: task ? `${task[1] === ' ' ? '☐' : '☑'} ${inline(task[2])}` : inline(m[3]), sub });
      i++; continue;
    }
    if (!line.trim()) { flush(); i++; continue; }
    if (list && /^\s{2,}\S/.test(line)) { const l = list as ListState; l.items[l.items.length - 1].html += '<br>' + inline(line.trim()); i++; continue; }
    flushL(); para.push(line.trim()); i++;
  }
  flush(); return out;
}
