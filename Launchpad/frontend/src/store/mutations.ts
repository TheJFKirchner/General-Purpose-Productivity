/* State changes shared by the server-event reducer (reducer.ts) and the UI actions (actions.ts).
   Each takes the change context `c` (immer draft + effects) from run(). Ported from the vanilla handlers. */
import type { ChatMode, FileContentEvent, FileErrorEvent, Id, RoundAnswer } from '../contract';
import { later, run, send, toast, type Ctx } from './core';
import type { Chat, FlightEntry, PlannerEntry, Round, Session, VisualSet } from './types';
import { curVisSet, draftLaunched, fxKey, queueVisible, sLabel } from './selectors';
import { letterFor, modelName } from '../lib/format';

export const nextId = (c: Ctx, prefix = 'e'): string => `${prefix}${++c.st.seq}`;

/* ---------- sessions and the planner chat ---------- */
export function sess(c: Ctx, id: Id | null | undefined): Session | null {
  if (id == null || id === '') return null;
  let s = c.st.sessions[id];
  if (!s) {
    s = {
      id, letter: letterFor(c.st.order.length), folder: '', dirId: null, cwd: '', planTitle: '', status: 'planning', meta: null, roundTag: '',
      draft: null, draftV: 0, draftRev: null, runDraftV: null, runRev: null, run: null, report: null, approving: false, stopping: false,
      reportSent: false, snapReportSent: false, snapTotal: null, plannerCost: null, cleared: false, flash: 0, flashN: null, created: Date.now(),
      autopilot: false, plannerId: null, plannerStatus: 'idle', plannerModel: null, promoted: false, promoReason: null, promoBy: null,
      promoting: false, codeSending: false, codeSentV: null, visualSets: [], visSel: null, visSeen: 0, log: [], typing: false,
    };
    c.st.sessions[id] = s; c.st.order.push(id);
    s = c.st.sessions[id];
  }
  return s;
}
/** Events with a session_id go to that session; without one, to the current session (or null before any). */
export const sessOf = (c: Ctx, sid: Id | null | undefined): Session | null =>
  sid != null && sid !== '' ? sess(c, sid) : (c.st.current != null ? c.st.sessions[c.st.current] || null : null);
export function logFor(c: Ctx, sid: Id | null | undefined): PlannerEntry[] { const s = sessOf(c, sid); return s ? s.log : c.st.preLog; }
export function addBubble(c: Ctx, who: 'me' | 'bot', text: string, sid?: Id | null): void { logFor(c, sid).push({ kind: 'bubble', id: nextId(c), who, text: String(text ?? '') }); }
export function addSys(c: Ctx, text: string, sid?: Id | null, cls?: 'promo' | 'err'): void { logFor(c, sid).push({ kind: 'sys', id: nextId(c), text: String(text ?? ''), ...(cls ? { cls } : {}) }); }
export function setTyping(c: Ctx, on: boolean, sid?: Id | null): void { const s = sessOf(c, sid); if (s) s.typing = on; else c.st.preTyping = on; }

export function setCurrent(c: Ctx, sid: Id): void {
  const s = sess(c, sid); if (!s) return;
  const first = c.st.current == null;
  c.st.current = s.id;
  if (first && c.st.preLog.length) { s.log.unshift(...c.st.preLog); c.st.preLog = []; }
  if (first && c.st.preTyping) { s.typing = true; c.st.preTyping = false; }
  /* the round lines moved into this session above, so its header keeps their round tag */
  if (first && c.st.preRoundTag && !s.roundTag) s.roundTag = c.st.preRoundTag;
  if (first) { c.st.preName = ''; c.st.preRoundTag = ''; }
  c.st.ui.newPlanBusy = false;
}

/** A launched draft's card turns "approved" for good (a later draft does not supersede it). */
export function syncPlanCard(s: Session): void {
  if (!draftLaunched(s)) return;
  for (const e of s.log) if (e.kind === 'plancard' && e.draftV === s.draftV && e.state === 'open') e.state = 'approved';
}

/* ---------- question rounds ---------- */
export function answerQ(c: Ctx, r: Round, qid: string, ans: RoundAnswer, batch = false): void {
  r.answers[qid] = ans;
  if (!batch) submitIfDone(c, r);
}
export function submitIfDone(c: Ctx, r: Round): void {
  if (r.sent || Object.keys(r.answers).length < r.questions.length) return;
  r.sent = true; r.actionsHidden = true;
  send({ type: 'round_answer', roundId: r.id, answers: JSON.parse(JSON.stringify(r.answers)) });
}

/* ---------- planner model ---------- */
/** get_crew; with the folder the user picked in Crew (else the server uses the current session's folder). */
export function requestCrew(c: Ctx): void {
  const dir = c.st.crewDirPick;
  if (!send(dir ? { type: 'get_crew', dir_id: dir } : { type: 'get_crew' })) return;
  c.st.crewLoading = true;
  later(c, 8000, () => run(c2 => { if (c2.st.crewLoading) c2.st.crewLoading = false; }), 'crew');
}

export function promoLine(s: Session): string {
  return `Planner moved to the stronger model (${modelName(s.plannerModel)}) ${s.promoBy === 'user' ? 'at your request' : s.promoBy === 'criteria' ? 'by its promotion criteria' : ''}${s.promoReason ? ': ' + s.promoReason : '.'}`.replace(' .', '.').replace(' :', ':');
}

/* ---------- Incoming ---------- */
export function removeQ(c: Ctx, id: Id): void { c.st.queue = c.st.queue.filter(x => x.id !== id); }
/** Remove a card with its fade-out (at once with reduced motion, or when a filter hides the card anyway). */
export function dropItem(c: Ctx, id: Id, reduced = false): void {
  const i = c.st.queue.find(x => x.id === id); if (!i) return;
  if (reduced || !queueVisible(c.st, i)) { removeQ(c, id); return; }
  i.leaving = true;
  later(c, 250, () => run(c2 => removeQ(c2, id)));
}

/* ---------- visuals ---------- */
export function addVisNote(c: Ctx, text: string, sid: Id, setId: string): void { logFor(c, sid).push({ kind: 'visnote', id: nextId(c), text, setId }); }
export function noteVisPick(c: Ctx, sid: Id, set: VisualSet): void {
  set.notedPick = set.picked_id;
  if (c.st.replaying) return;
  const o = set.options.find(x => x.id === set.picked_id);
  addVisNote(c, o ? `Picked “${o.label}” for ${set.brief || 'the visual'}. The planner gets it with your next message.` : `Pick cleared for ${set.brief || 'the visual'}.`, sid, set.set_id);
}
export function openVis(c: Ctx, on: boolean): void {
  c.st.ui.vis.open = !!on && !!curVisSet(c.st);
  if (c.st.ui.vis.open) { const s = c.st.current != null ? c.st.sessions[c.st.current] : null; if (s) s.visSeen = s.visualSets.length; }
}

/* ---------- Claude Code chats ---------- */
export function chatOf(c: Ctx, id: Id | null | undefined): Chat | null {
  if (id == null || id === '') return null;
  let ch = c.st.chats[id];
  if (!ch) {
    c.st.chats[id] = { id, mode: 'default', model: '', cwd: '', dirId: null, busy: false, started: false, log: [], streamId: null, typing: false, agentIds: [] };
    c.st.chatOrder.push(id);
    ch = c.st.chats[id];
  }
  return ch;
}
export const curChatOf = (c: Ctx): Chat | null => (c.st.currentChat != null && c.st.chats[c.st.currentChat]) || null;
export function chatAppend(ch: Chat, e: FlightEntry): void { ch.log.push(e); }
export function endStream(ch: Chat): void { ch.streamId = null; }
export function chatSys(c: Ctx, cid: Id, text: string, cls?: 'err'): void { const ch = chatOf(c, cid); if (ch) chatAppend(ch, { kind: 'sys', id: nextId(c), text: String(text ?? ''), ...(cls ? { cls } : {}) }); }
export function chatBubble(c: Ctx, cid: Id, who: 'me' | 'bot', text: string): void { const ch = chatOf(c, cid); if (ch) chatAppend(ch, { kind: 'bubble', id: nextId(c), who, text: String(text ?? '') }); }
export function showChat(c: Ctx, id: Id | null): void { c.st.currentChat = id; }

export function setChatMode(c: Ctx, mode: ChatMode): void {
  const ch = curChatOf(c);
  c.st.codeModePref = mode;
  if (ch) { if (!send({ type: 'chat_set_mode', chat_id: ch.id, mode })) return; ch.mode = mode; }
}
export function sendChat(c: Ctx, text: string): boolean {
  const ch = curChatOf(c);
  if (!ch) {
    if (c.st.chatPending != null) return false;
    if (!send({ type: 'chat_new' })) return false;
    c.st.chatPending = text;
    return true;
  }
  if (!send({ type: 'chat_message', chat_id: ch.id, text })) return false;
  chatBubble(c, ch.id, 'me', text); ch.busy = true; ch.typing = true;
  return true;
}

/* ---------- File Explorer ---------- */
export function fxLoad(c: Ctx, root: string, path: string, force = false): void {
  const k = fxKey(root, path);
  if (!force && (c.st.fx.cache[k] || c.st.fx.loading[k])) return;
  if (send({ type: 'list_dir', root, path: path || '' })) c.st.fx.loading[k] = true;
}
export function fxBoot(c: Ctx): void {
  const fx = c.st.fx;
  if (fx.booted || !c.st.settings) return;
  fx.booted = true;
  for (const k of fx.open) { const i = k.indexOf('|'); fxLoad(c, k.slice(0, i), k.slice(i + 1)); }
  if (fx.sel) send({ type: 'read_file', root: fx.sel.root, path: fx.sel.path });
}
export function fxSelect(c: Ctx, root: string, path: string): void {
  c.st.fx.sel = { root, path };
  delete c.st.files[fxKey(root, path)];
  send({ type: 'read_file', root, path });
}

/* ---------- pen editor ---------- */
export function edFill(c: Ctx, ev: Omit<FileContentEvent, 'type'>): void {
  const ed = c.st.editor;
  ed.waiting = false;
  if (ev.kind !== 'markdown' || ev.text == null) {
    ed.banner = { kind: 'notice', code: 'viewonly', message: '', fileKind: ev.kind && ev.kind !== 'markdown' ? ev.kind : undefined };
    ed.text = ev.text || ''; ed.editable = false;
  } else {
    ed.text = ev.text; ed.editable = !!ev.editable;
    if (!ev.editable) ed.banner = { kind: 'notice', code: 'viewonly', message: 'The server does not allow editing this file.' };
  }
  ed.text0 = ed.text; ed.version = ev.version; ed.applies = ev.applies || null; ed.validates = ev.validates_as || null; ed.dirty = false;
  ed.status = '';
}
export function edError(c: Ctx, ev: Omit<FileErrorEvent, 'type'>): void {
  const ed = c.st.editor;
  ed.saving = false; ed.waiting = false; ed.restoring = false; ed.status = '';
  if (ev.code === 'conflict') { ed.conflict = ev.current || null; ed.banner = { kind: 'conflict', code: 'conflict', message: ev.message || '' }; }
  else ed.banner = { kind: 'invalid', code: ev.code, message: ev.message || '' };
}
export function closeEditor(c: Ctx, force: boolean): void {
  const ed = c.st.editor;
  if (!ed.open) return;
  if (ed.dirty && !force) {
    if (!ed.discardArm) {
      ed.discardArm = true;
      later(c, 4000, () => run(c2 => { if (c2.st.editor.open) c2.st.editor.discardArm = false; }), 'edDiscard');
      return;
    }
  }
  ed.open = false; ed.dirty = false; ed.discardArm = false;
}

export { toast, later, send, sLabel };
