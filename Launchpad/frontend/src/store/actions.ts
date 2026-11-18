/* UI actions: everything a screen does that changes state and/or sends a message. Views call these (or plain
   send() for messages with no local state change); they never write the store themselves.
   Ported from the vanilla click handlers; the same messages go out. */
import type { AgentFields, ChatMode, Id, McpConfig, McpKind, ReviewAnswerOut, RoundAnswer, WorkflowDraft } from '../contract';
import { getState, later, run, send, toast, type Ctx } from './core';
import type { ChatSide, QueueItem, View } from './types';
import type { GitOp, UiMessage } from '../contract';
import {
  addBubble, addSys, answerQ, chatBubble, closeEditor, curChatOf, dropItem, fxBoot, fxLoad, fxSelect, noteVisPick, openVis,
  requestCrew, sendChat, setChatMode, setCurrent, submitIfDone,
} from './mutations';
import { agentFormProblems, canApprove, crewDir, curSess, dirsList, draftLaunched, fxKey, gitTicked, isBuiltin, problemField, sLabel, sName } from './selectors';
import { initialCrewForm, initialEditor } from './initial';
import { newReview, reviewOf } from './roles';
import type { RoleDecision } from '../contract';
import { MODES, WRITE_TOOLS } from '../lib/labels';
import { REDUCED } from '../lib/format';
import { LS_EDITOR_VIEW, lsSet } from '../lib/storage';

/* Repos panel: ask for the repo list (also when the Files tab opens); a lost answer must not leave the panel waiting */
function gitScan(c: Ctx): void {
  if (!send({ type: 'git_scan' })) return;
  c.st.git.scanning = true;
  later(c, 90_000, () => run(c2 => { c2.st.git.scanning = false; }), 'gitScan');
}
/** One operation on one repo: busy until its git_result (or 3 minutes, a push may be slow). */
function gitOp(c: Ctx, id: string, op: GitOp, msg: UiMessage): void {
  const g = c.st.git;
  if (g.busy[id] || !send(msg)) return;
  g.busy[id] = op; delete g.error[id]; delete g.note[id];
  later(c, 180_000, () => run(c2 => { delete c2.st.git.busy[id]; }), `git:${id}`);
}

/* folder menu callback (functions are kept out of the store) */
let dirMenuCb: ((dirId: string) => void) | null = null;

export const actions = {
  /* ---------- shell ---------- */
  /** Switch tab. Files asks for settings and loads the tree; Crew asks for the crew list. */
  setView(v: View) {
    run(c => {
      c.st.ui.view = v;
      if (v === 'files') { if (!c.st.settings) send({ type: 'get_settings' }); fxBoot(c); gitScan(c); }
      if (v === 'crew') { requestCrew(c); if (!c.st.settings) send({ type: 'get_settings' }); send({ type: 'get_mcp' }); }
      if (v === 'workflows') send({ type: 'workflows_get' });
      if (v === 'settings') { send({ type: 'get_settings' }); send({ type: 'get_mcp' }); c.st.ui.settingsMsg = null; }
      if (v === 'plan' && c.st.ui.chatSide === 'code' && !c.st.crewDefs && !c.st.crewLoading) requestCrew(c);
    });
  },
  /** The chat screen's Planner / CLI switch (shows the chat screen too). Both conversations stay as they are. */
  setChatSide(side: ChatSide) {
    run(c => {
      c.st.ui.view = 'plan';
      c.st.ui.chatSide = side;
      if (side === 'code' && !c.st.crewDefs && !c.st.crewLoading) requestCrew(c);
    });
  },
  toast(text: string) { run(c => toast(c, text)); },
  setConn(text: string, color: string) { run(c => { c.st.ui.conn = { text, color }; }); },
  setDemo(on: boolean) { run(c => { c.st.ui.demo = on; }); },
  /** Demo only: no toasts while it seeds its runs. */
  setQuiet(on: boolean) { run(c => { c.st.quiet = on; }); },

  /* ---------- Plan: planner chat ---------- */
  /** Send a message to the current session's planner and show it in the chat. */
  sendPlannerMessage(text: string): boolean {
    const t = String(text || '').trim(); if (!t) return false;
    return run(c => { if (!send({ type: 'user_message', text: t })) return false; addBubble(c, 'me', t); return true; });
  },
  /** Demo only: a user bubble with no message sent. */
  addLocalPlannerBubble(who: 'me' | 'bot', text: string) { run(c => addBubble(c, who, text)); },
  /** "+ New plan" after the folder was chosen (see chooseDir). */
  newPlan(dirId: string | null) {
    run(c => {
      if (!send(dirId ? { type: 'new_session', dir_id: dirId } : { type: 'new_session' })) return;
      c.st.ui.newPlanBusy = true; c.st.ui.view = 'plan'; c.st.ui.chatSide = 'planner';
      later(c, 8000, () => run(c2 => { c2.st.ui.newPlanBusy = false; }), 'newPlan');
    });
  },
  /** Show another session's planner chat (Missions "Planning chat" opens a read-only copy instead: openArchive). */
  setCurrentSession(sid: Id) { run(c => setCurrent(c, sid)); },

  /* question rounds */
  answerQuestion(roundId: string, qid: string, ans: RoundAnswer) {
    run(c => { const r = c.st.rounds[roundId]; if (r && !r.answers[qid]) answerQ(c, r, qid, ans); });
  },
  acceptAllPicks(roundId: string) {
    run(c => {
      const r = c.st.rounds[roundId]; if (!r) return;
      for (const q of r.questions) if (!r.answers[q.id] && (q.rec || c.st.ui.demo)) answerQ(c, r, q.id, { accepted: true }, true);
      submitIfDone(c, r);
    });
  },
  skipRound(roundId: string) {
    run(c => {
      const r = c.st.rounds[roundId]; if (!r) return;
      r.actionsHidden = true;
      addSys(c, 'Round skipped. Open questions stay open and come back later.', r.sessionId);
      send({ type: 'round_answer', roundId: r.id, answers: JSON.parse(JSON.stringify(r.answers)), skipped: true });
      submitIfDone(c, r);
    });
  },

  /* plan approval */
  approve(sid: Id) {
    run(c => {
      const s = c.st.sessions[sid]; if (!s) return;
      if (!canApprove(s)) { if (s.status === 'running') toast(c, `Run ${s.letter} is still going. Approve the new plan once it has finished or been stopped.`); return; }
      if (!send({ type: 'plan_approve', session_id: sid })) return;
      const v = s.draftV;
      s.approving = true; toast(c, `Launching ${sName(s)}…`);
      later(c, 20000, () => run(c2 => {
        const s2 = c2.st.sessions[sid];
        if (s2 && s2.approving && s2.draftV === v && !draftLaunched(s2)) { s2.approving = false; toast(c2, `${sLabel(s2)} has not launched yet. You can approve again.`); }
      }));
    });
  },
  /** "Send plan to CLI" on a plan draft card: the server opens a CLI chat in the folder in Plan mode
      with the plan as its first message (chat_from_plan -> chat_started); the switch flips to the CLI side. */
  sendPlanToCode(sid: Id) {
    run(c => {
      const s = c.st.sessions[sid]; if (!s || !s.draft || s.codeSending) return;
      if (!send({ type: 'chat_from_plan', session_id: sid })) return;
      s.codeSending = true;
      c.st.chatFromPlan = sid;
      c.st.ui.newChatBusy = true;
      c.st.ui.view = 'plan'; c.st.ui.chatSide = 'code';
      later(c, 20000, () => run(c2 => {
        const s2 = c2.st.sessions[sid];
        if (s2 && s2.codeSending) { s2.codeSending = false; toast(c2, 'The CLI chat has not started yet. You can send the plan again.'); }
        if (c2.st.chatFromPlan === sid) { c2.st.chatFromPlan = null; c2.st.ui.newChatBusy = false; }
      }));
    });
  },
  /** The planner picker: one harness-and-model option (planner_choose). The server decides what it means: an unstarted
      session takes it at once, the session's top model is promotion by hand, anything else is for the next new plan.
      Picking what the session already runs, with nothing pending, sends nothing. */
  choosePlanner(optionId: string) {
    run(c => {
      const pc = c.st.plannerChoice, o = pc ? pc.options.find(x => x.id === optionId) : null;
      if (!o || !o.available || c.st.ui.pickerChoosing) return;
      const s = curSess(c.st);
      if (s && s.plannerOption === optionId && pc && pc.choice.option_id === optionId) return;
      if (!send(s ? { type: 'planner_choose', option_id: optionId, session_id: s.id } : { type: 'planner_choose', option_id: optionId })) return;
      c.st.ui.pickerChoosing = optionId;
      if (s && s.plannerStarted && s.switchableTo.includes(optionId)) s.promoting = true;
      const sid = s ? s.id : null;
      later(c, 15000, () => run(c2 => {
        c2.st.ui.pickerChoosing = null;
        const s2 = sid ? c2.st.sessions[sid] : null; if (s2 && s2.promoting) s2.promoting = false;
      }), 'pickerChoosing');
    });
  },
  /** The CLI chat's picker: one CLI-and-model option (cli_choose). The server remembers it for new chats and reloads
      every chat nobody has written to yet; a chat in progress keeps its own. Picking what the open chat already runs,
      with nothing pending, sends nothing. Independent of the planner's choice. */
  chooseCli(optionId: string) {
    run(c => {
      const cc = c.st.cliChoice, o = cc ? cc.options.find(x => x.id === optionId) : null;
      if (!cc || !o || !o.available || c.st.ui.cliChoosing) return;
      const ch = curChatOf(c);
      if ((ch ? ch.optionId === optionId : true) && cc.choice.option_id === optionId) return;
      if (!send({ type: 'cli_choose', option_id: optionId })) return;
      c.st.ui.cliChoosing = optionId;
      later(c, 15000, () => run(c2 => { c2.st.ui.cliChoosing = null; }), 'cliChoosing');
    });
  },
  /** The picker's "Auto-promote" toggle: a per-user setting (planner_auto_promote). Off applies at once (the planner
      never promotes itself); on applies to plans nobody has written to yet. */
  setAutoPromote(on: boolean) {
    run(c => {
      if (!send({ type: 'set_settings', patch: { planner_auto_promote: on } })) return;
      if (c.st.plannerChoice) c.st.plannerChoice.auto_promote = on;
    });
  },
  /** Autopilot switch: turning on takes a second click within 4 s; turning off is immediate. */
  toggleAutopilot(sid: Id) {
    run(c => {
      const s = c.st.sessions[sid]; if (!s) return;
      if (!s.autopilot && c.st.ui.apConfirm !== sid) {
        c.st.ui.apConfirm = sid;
        later(c, 4000, () => run(c2 => { c2.st.ui.apConfirm = null; }), 'apConfirm');
        return;
      }
      c.st.ui.apConfirm = null;
      const on = !s.autopilot;
      if (!send({ type: 'set_autopilot', session_id: sid, on })) return;
      s.autopilot = on;
      toast(c, on ? `Autopilot ON for ${sLabel(s)}: every permission request is approved without asking` : `Autopilot off for ${sLabel(s)}: permission requests come to Incoming again`);
    });
  },

  /** Auto answers switch (per session, separate from Autopilot): both ways take one click; the server's auto_answers event is authoritative. */
  toggleAutoAnswers(sid: Id) {
    run(c => {
      const s = c.st.sessions[sid]; if (!s) return;
      const on = !s.autoAnswers;
      if (!send({ type: 'set_auto_answers', session_id: sid, on })) return;
      s.autoAnswers = on;
      toast(c, on ? `Auto answers ON for ${sLabel(s)}: builders' questions are answered with the builder's own recommendation; planner and CLI questions still wait for you` : `Auto answers off for ${sLabel(s)}: builders' questions wait for you again`);
    });
  },

  /* ---------- Incoming ---------- */
  setQueueFilter(f: 'all' | 'permission' | 'question') { run(c => { c.st.ui.queueFilter = f; }); },
  /** Answer a question card (an option, the recommendation or free text). */
  answerItem(id: Id, value: string) {
    run(c => {
      const i = c.st.queue.find(x => x.id === id);
      if (!i || i.ui !== 'open' || value == null || value === '') return;
      if (!send({ type: 'queue_response', id, answer: value })) return;
      i.ui = 'sent'; i.answer = value;
      toast(c, `Sent to ${i.agent || 'the agent'}`);
    });
  },
  /** Permission card: allow | deny | always. */
  decide(id: Id, d: 'allow' | 'deny' | 'always') {
    run(c => {
      const i = c.st.queue.find(x => x.id === id);
      if (!i || i.ui !== 'open') return;
      if (!send({ type: 'queue_response', id, decision: d })) return;
      i.ui = 'sent'; i.answer = ({ allow: 'Allow', deny: 'Deny', always: 'Always allow' } as const)[d];
      toast(c, `${d === 'deny' ? 'Denied' : 'Allowed'} · ${i.agent || 'agent'}`);
    });
  },
  /** Dismiss is local only (info, report, auto-answered cards). */
  dismissItem(id: Id) { run(c => dropItem(c, id, REDUCED)); },
  /** Send a finished run's report to its planner; the Plan chat follows that session. */
  sendReport(sid: Id): boolean {
    return run(c => {
      const s = c.st.sessions[sid]; if (!s || s.reportSent) return false;
      if (!send({ type: 'report_to_planner', session_id: sid })) return false;
      s.reportSent = true;
      if (c.st.current !== sid) setCurrent(c, sid);
      toast(c, `Run ${s.letter} report sent to its planner. The Plan chat now shows ${sLabel(s)}.`);
      return true;
    });
  },

  /* ---------- activity feed, highlight, run focus ---------- */
  setFeedRun(v: string) { run(c => { c.st.ui.feedRun = v; c.st.ui.feedAgent = ''; }); },
  setFeedAgent(v: string) { run(c => { c.st.ui.feedAgent = v; }); },
  /** Hovered agent (ship, star, feed row): highlighted everywhere. */
  setHover(id: Id | null) { if (getState().ui.hov !== id) run(c => { c.st.ui.hov = id; }); },
  /** Click an agent to pin it (click again to unpin). */
  selectAgent(id: Id) {
    run(c => {
      c.st.ui.sel = c.st.ui.sel === id ? null : id;
      const a = c.st.agents[id];
      if (c.st.ui.sel && a) toast(c, `Pinned ${a.name || id}. Click it again to unpin.`);
    });
  },
  clearSelection() { run(c => { c.st.ui.sel = null; }); },
  /** Run row in the side panel: open Missions scrolled to that run. */
  focusRun(sid: Id) { run(c => { c.st.ui.focus = sid; c.st.ui.focusScroll = true; c.st.ui.view = 'missions'; }); },
  consumeFocusScroll() { if (getState().ui.focusScroll) run(c => { c.st.ui.focusScroll = false; }); },

  /* ---------- Missions ---------- */
  /** Stop a run: first click arms (4 s), second sends run_stop. */
  stopRun(sid: Id) {
    run(c => {
      const s = c.st.sessions[sid]; if (!s || s.status !== 'running' || s.stopping) return;
      if (c.st.ui.stopConfirm !== sid) {
        c.st.ui.stopConfirm = sid;
        later(c, 4000, () => run(c2 => { c2.st.ui.stopConfirm = null; }), 'stopConfirm');
        return;
      }
      c.st.ui.stopConfirm = null;
      if (!send({ type: 'run_stop', session_id: sid })) return;
      s.stopping = true; toast(c, `Stopping run ${s.letter}…`);
    });
  },
  /** "Move to Landed". */
  clearSystem(sid: Id) { run(c => { const s = c.st.sessions[sid]; if (s) s.cleared = true; }); },

  /* ---------- CLI chats (the switch's CLI side) ---------- */
  /** Send in the open chat; with no chat open, starts one and sends the text once chat_started arrives. */
  sendChat(text: string): boolean { const t = String(text || '').trim(); if (!t) return false; return run(c => sendChat(c, t)); },
  setChatMode(mode: ChatMode) { run(c => setChatMode(c, mode)); },
  /** Shift+Tab / mode pill: default -> accept_edits -> plan -> default. */
  cycleMode() {
    run(c => {
      const ch = curChatOf(c), cur = ch ? ch.mode : c.st.codeModePref || 'default';
      setChatMode(c, MODES[(MODES.indexOf(cur) + 1) % MODES.length]);
    });
  },
  stopChat() { run(c => { const ch = curChatOf(c); if (ch && ch.busy) send({ type: 'chat_stop', chat_id: ch.id }); }); },
  /** "+ New chat" after the folder was chosen. */
  newChat(dirId: string | null) {
    run(c => {
      if (!send(dirId ? { type: 'chat_new', dir_id: dirId } : { type: 'chat_new' })) return;
      c.st.ui.newChatBusy = true; c.st.ui.view = 'plan'; c.st.ui.chatSide = 'code';
      later(c, 8000, () => run(c2 => { c2.st.ui.newChatBusy = false; }), 'newChat');
    });
  },
  /** Answer an inline CLI card. `fields` = {decision, remember?, mode?, message?} or {answer}; label = settled text. */
  chatRespond(itemId: Id, fields: { decision: 'allow' | 'deny' | 'always'; remember?: 'session' | 'project_local'; mode?: 'default' | 'accept_edits'; message?: string } | { answer: string }, label: string) {
    run(c => {
      const i = c.st.chatItems[itemId]; if (!i || i.ui !== 'open') return;
      if (!send({ type: 'queue_response', id: itemId, ...fields } as Parameters<typeof send>[0])) return;
      i.ui = 'sent'; i.result = label;
    });
  },
  /** Demo only: a user bubble in a chat with no message sent. */
  addLocalChatBubble(chatId: Id, text: string) { run(c => chatBubble(c, chatId, 'me', text)); },

  /* ---------- Visuals ---------- */
  openVis(on: boolean) { run(c => openVis(c, on)); },
  toggleVisWide() { run(c => { c.st.ui.vis.wide = !c.st.ui.vis.wide; }); },
  /** Drag the panel's left edge (px); leaves Wide mode. */
  setVisWidth(px: number) { run(c => { c.st.ui.vis.wide = false; c.st.ui.vis.width = Math.round(px); }); },
  visPrev() { run(c => { const s = curSess(c.st); if (s && (s.visSel ?? 0) > 0) s.visSel = (s.visSel ?? 0) - 1; }); },
  visNext() { run(c => { const s = curSess(c.st); if (s && (s.visSel ?? 0) < s.visualSets.length - 1) s.visSel = (s.visSel ?? 0) + 1; }); },
  /** The "Show" button on a visuals note in the chat. */
  visShowSet(sid: Id, setId: string) {
    run(c => { const s = c.st.sessions[sid]; if (!s) return; const k = s.visualSets.findIndex(x => x.set_id === setId); if (k >= 0) s.visSel = k; openVis(c, true); });
  },
  /** Pick an option (null clears the pick). */
  visPick(sid: Id, setId: string, optionId: string | null) {
    run(c => {
      const s = c.st.sessions[sid], set = s && s.visualSets.find(x => x.set_id === setId); if (!s || !set) return;
      if (!send({ type: 'visual_pick', session_id: sid, set_id: setId, option_id: optionId })) return;
      set.picked_id = optionId;
      noteVisPick(c, sid, set);
    });
  },
  visTweak(sid: Id, setId: string, optionId: string, text: string): boolean {
    return run(c => {
      const s = c.st.sessions[sid], set = s && s.visualSets.find(x => x.set_id === setId); if (!s || !set) return false;
      if (!send({ type: 'visual_tweak', session_id: sid, set_id: setId, option_id: optionId, text })) return false;
      set.pending[optionId] = 'tweak';
      return true;
    });
  },
  visRetry(sid: Id, setId: string, optionId: string) {
    run(c => {
      const s = c.st.sessions[sid], set = s && s.visualSets.find(x => x.set_id === setId); if (!s || !set) return;
      if (!send({ type: 'visual_retry', session_id: sid, set_id: setId, option_id: optionId })) return;
      set.pending[optionId] = 'retry';
    });
  },

  /* ---------- Crew ---------- */
  requestCrew() { run(c => { requestCrew(c); send({ type: 'roles_get' }); }); },
  /** Show the agents of another connected folder (get_crew {dir_id}); new agents are then saved there. */
  crewPickDir(dirId: Id) { run(c => { c.st.crewDirPick = dirId; requestCrew(c); }); },
  /** Open the "Add an agent" form (what was typed before stays until it is saved). */
  crewOpenForm() { run(c => { const f = c.st.crewForm; f.open = true; f.error = null; f.draftError = null; if (!c.st.settings) send({ type: 'get_settings' }); }); },
  crewCloseForm() { run(c => { const f = c.st.crewForm; f.open = false; f.drafting = false; f.saving = false; }); },
  /** Start the form again from empty. */
  crewResetForm() { run(c => { c.st.crewForm = { ...initialCrewForm(), open: c.st.crewForm.open, role: c.st.crewForm.role }; }); },
  /** Change form fields; the server's problems for those fields go (they no longer apply). */
  crewSetFields(patch: Partial<AgentFields>) {
    run(c => {
      const f = c.st.crewForm;
      f.fields = { ...f.fields, ...patch };
      /* exploring / reviewing agents are read-only: the server refuses them with write, edit or shell tools */
      if (f.fields.purpose === 'exploring' || f.fields.purpose === 'reviewing') f.fields.tools = f.fields.tools.filter(t => !WRITE_TOOLS.includes(t));
      const keys = Object.keys(patch);
      f.problems = f.problems.filter(p => { const k = problemField(p); return !k || !keys.includes(k); });
    });
  },
  crewSetDraftText(text: string) { run(c => { c.st.crewForm.draftText = text; }); },
  /** "Draft for me": a cheap one-shot agent fills the form from a sentence or two (agent_draft -> agent_drafted). */
  crewDraft() {
    run(c => {
      const f = c.st.crewForm, text = f.draftText.trim(), dir = crewDir(c.st);
      if ((!text && !f.role) || f.drafting) return;
      if (!dir) { f.draftError = 'Connect a folder in Settings first: added agents are saved in a project folder.'; return; }
      if (!send({ type: 'agent_draft', dir_id: dir, text, ...(f.role ? { role: f.role } : {}) })) { f.draftError = 'Not connected to Launchpad.'; return; }
      f.drafting = true; f.draftError = null; f.drafted = false;
      later(c, 90000, () => run(c2 => { const f2 = c2.st.crewForm; if (f2.drafting) { f2.drafting = false; f2.draftError = 'No draft came back. Try again, or fill the form in yourself.'; } }), 'crewDraft');
    });
  },
  /** Save the form as a new agent in the connected folder (agent_create -> agent_saved + a fresh crew_list).
      Returns false (and sends nothing) when the page's own checks fail; the view shows those inline. */
  crewCreate(): boolean {
    return run(c => {
      const f = c.st.crewForm, dir = crewDir(c.st);
      if (f.saving) return false;
      if (agentFormProblems(c.st, f.fields).length) return false;
      if (!dir) { f.error = 'Connect a folder in Settings first: added agents are saved in a project folder.'; return false; }
      const fields: AgentFields = {
        name: f.fields.name.trim(), description: f.fields.description.trim(), purpose: f.fields.purpose, model: f.fields.model,
        tools: [...f.fields.tools], instructions: f.fields.instructions.trim(),
      };
      if (!send({ type: 'agent_create', dir_id: dir, fields, ...(f.role ? { role: f.role } : {}) })) { f.error = 'Not connected to Launchpad.'; return false; }
      f.saving = true; f.error = null; f.problems = [];
      later(c, 30000, () => run(c2 => { const f2 = c2.st.crewForm; if (f2.saving) { f2.saving = false; f2.error = 'No answer from Launchpad. Try saving again.'; } }), 'crewSave');
      return true;
    });
  },
  /** Remove a folder agent (the view asks for a confirm first; the server keeps a backup copy). */
  crewRemove(name: string) {
    run(c => {
      const a = (c.st.crewDefs || []).find(x => x.name === name);
      if (!a || isBuiltin(a) || c.st.crewRemoving) return;
      const dir = (a.root && a.root !== 'app' ? a.root : null) ?? crewDir(c.st);
      if (!dir) return;
      if (!send({ type: 'agent_remove', dir_id: dir, name })) return;
      c.st.crewRemoving = name; c.st.crewError = null;
      later(c, 20000, () => run(c2 => { if (c2.st.crewRemoving === name) { c2.st.crewRemoving = null; c2.st.crewError = `No answer from Launchpad about removing ${name}.`; } }), 'crewRemove');
    });
  },
  clearCrewError() { if (getState().crewError) run(c => { c.st.crewError = null; }); },
  /** One agent's skills: "all" or a list of names (set_agent_skills -> a fresh crew_list). Shown at once. */
  setAgentSkills(name: string, skills: 'all' | string[]) {
    run(c => {
      const a = (c.st.crewDefs || []).find(x => x.name === name);
      if (!a || a.skill_setting === 'cli') return;
      const dir = crewDir(c.st);
      if (!send({ type: 'set_agent_skills', name, skills: skills === 'all' ? 'all' : [...skills], ...(dir ? { dir_id: dir } : {}) })) return;
      a.skill_setting = skills === 'all' ? 'all' : [...skills];
    });
  },

  /* ---------- Crew: undefined roles ("Used but not defined") and their reviews ---------- */
  /** Show a role's review screen in the Crew tab (from the list, or from an Incoming card). Starts nothing. */
  openRole(role: string) { run(c => { c.st.ui.view = 'crew'; c.st.roleOpen = role; if (!c.st.crewDefs && !c.st.crewLoading) requestCrew(c); }); },
  closeRole() { run(c => { c.st.roleOpen = null; }); },
  /** Review: open the screen and have the reviewer read the history. A case still waiting for the user's decision is just shown. */
  roleReview(role: string) {
    run(c => {
      c.st.ui.view = 'crew'; c.st.roleOpen = role;
      const r = c.st.reviews[role];
      if (r && (r.status === 'running' || r.status === 'starting' || (r.status === 'case' && r.case && !r.decided && !r.case.decision))) return;
      if (!send({ type: 'review_start', role })) { const n = reviewOf(c, role); n.status = 'failed'; n.error = 'Not connected to Launchpad.'; return; }
      c.st.reviews[role] = newReview(role);
    });
  },
  /** The user's decision on a case. Define also asks for the draft (agent_draft with the role) and opens the filled form when it arrives. */
  roleDecide(role: string, decision: RoleDecision) {
    run(c => {
      const r = reviewOf(c, role);
      if (r.deciding || !send({ type: 'review_decide', role, decision })) return;
      r.deciding = decision;
      if (decision === 'define') {
        const f = c.st.crewForm;
        if (f.role !== role) c.st.crewForm = { ...initialCrewForm(), role };
        actions.roleDraft(role);
      }
    });
  },
  /** Ask the drafter for the agent (agent_draft {role}); the form opens filled when agent_drafted arrives. */
  roleDraft(role: string) {
    run(c => {
      const dir = crewDir(c.st);
      if (c.st.crewForm.role !== role) c.st.crewForm = { ...initialCrewForm(), role };
      const f = c.st.crewForm;
      if (f.drafting) return;
      if (!dir) { f.draftError = 'Connect a folder in Settings first: the agent is saved in a project folder.'; return; }
      if (!send({ type: 'agent_draft', dir_id: dir, text: '', role })) { f.draftError = 'Not connected to Launchpad.'; return; }
      f.drafting = true; f.draftError = null; f.drafted = false;
      later(c, 90000, () => run(c2 => { const f2 = c2.st.crewForm; if (f2.drafting) { f2.drafting = false; f2.draftError = 'No draft came back. Try again, or fill the form in yourself.'; } }), 'crewDraft');
    });
  },
  /** Open the form for the role's agent without a draft (empty, or as far as it was drafted). */
  roleOpenForm(role: string) {
    run(c => {
      if (c.st.crewForm.role !== role) c.st.crewForm = { ...initialCrewForm(), role };
      c.st.crewForm.open = true; c.st.crewForm.error = null; c.st.crewForm.draftError = null;
      if (!c.st.settings) send({ type: 'get_settings' });
    });
  },
  roleDismiss(role: string) { send({ type: 'role_dismiss', role }); },
  roleMerge(role: string, into: string) { if (role && into && role !== into) send({ type: 'role_merge', role, into }); },

  /* ---------- File Explorer ---------- */
  fxToggle(root: string, path: string) {
    run(c => {
      const k = fxKey(root, path), fx = c.st.fx;
      if (fx.open.includes(k)) fx.open = fx.open.filter(x => x !== k); else { fx.open.push(k); fxLoad(c, root, path); }
    });
  },
  /** Expand every folder down to `path` (the "Sessions" shortcut opens ".launchpad"). */
  fxOpenPath(root: string, path: string) {
    run(c => {
      const fx = c.st.fx, add = (k: string) => { if (!fx.open.includes(k)) fx.open.push(k); };
      add(fxKey(root, '')); fxLoad(c, root, '');
      let acc = '';
      for (const p of String(path || '').split('/').filter(Boolean)) { acc = acc ? acc + '/' + p : p; add(fxKey(root, acc)); fxLoad(c, root, acc); }
    });
  },
  fxSelect(root: string, path: string) { run(c => fxSelect(c, root, path)); },
  /** Refresh: reload every open folder and the selected file. */
  fxRefresh() {
    run(c => {
      const fx = c.st.fx, keys = [...fx.open];
      fx.cache = {}; fx.err = {};
      for (const k of keys) { const i = k.indexOf('|'); fxLoad(c, k.slice(0, i), k.slice(i + 1), true); }
      if (fx.sel) fxSelect(c, fx.sel.root, fx.sel.path);
    });
  },
  setFxRaw(raw: boolean) { run(c => { c.st.fx.raw = raw; }); },
  toggleFxCollapsed() { run(c => { c.st.fx.collapsed = !c.st.fx.collapsed; }); },
  setFxWidth(px: number) { run(c => { c.st.fx.width = Math.round(px); }); },

  /* ---------- Repos panel ---------- */
  gitScan() { run(c => gitScan(c)); },
  gitRefresh(id: string) { run(c => gitOp(c, id, 'refresh', { type: 'git_refresh', repo_id: id })); },
  gitFetch(id: string) { run(c => gitOp(c, id, 'fetch', { type: 'git_fetch', repo_id: id })); },
  gitPush(id: string) { run(c => gitOp(c, id, 'push', { type: 'git_push', repo_id: id })); },
  /** Commit the ticked files with the typed message; push = "Commit and push". Needs a message and one ticked file. */
  gitCommit(id: string, push: boolean) {
    run(c => {
      const repo = c.st.git.repos.find(r => r.repo_id === id), message = (c.st.git.message[id] || '').trim();
      if (!repo || !message) return;
      const paths = gitTicked(c.st, repo);
      if (!paths.length) return;
      gitOp(c, id, 'commit', { type: 'git_commit', repo_id: id, message, paths, push });
    });
  },
  gitSetMessage(id: string, text: string) { run(c => { c.st.git.message[id] = text; }); },
  gitToggleFile(id: string, path: string) {
    run(c => {
      const off = c.st.git.unticked[id] || (c.st.git.unticked[id] = []), i = off.indexOf(path);
      if (i >= 0) off.splice(i, 1); else off.push(path);
    });
  },
  /** Tick all / untick all. */
  gitTickAll(id: string, on: boolean) {
    run(c => {
      const repo = c.st.git.repos.find(r => r.repo_id === id);
      c.st.git.unticked[id] = on || !repo ? [] : repo.files.map(f => f.path);
    });
  },
  gitToggleOpen(id: string, open: boolean) { run(c => { c.st.git.open[id] = open; }); },
  /** A changed file opens in the Files view (its folders expand, the file is selected). Deleted files have nothing to open. */
  gitOpenFile(id: string, path: string) {
    run(c => {
      const repo = c.st.git.repos.find(r => r.repo_id === id); if (!repo) return;
      const full = repo.rel && repo.rel !== '.' ? repo.rel + '/' + path : path, dir = full.split('/').slice(0, -1).join('/');
      const fx = c.st.fx, add = (k: string) => { if (!fx.open.includes(k)) fx.open.push(k); };
      add(fxKey(repo.dir_id, '')); fxLoad(c, repo.dir_id, '');
      let acc = '';
      for (const p of dir.split('/').filter(Boolean)) { acc = acc ? acc + '/' + p : p; add(fxKey(repo.dir_id, acc)); fxLoad(c, repo.dir_id, acc); }
      fxSelect(c, repo.dir_id, full);
    });
  },

  /* ---------- pen editor (any editable markdown file) ---------- */
  openEditor(root: string | null | undefined, path: string | null | undefined, title?: string) {
    run(c => {
      if (root == null || root === '' || !path) { toast(c, 'This file has no known location to edit'); return; }
      c.st.editor = { ...initialEditor(c.st.editor.pane), open: true, root, path, title: title || path.split('/').pop() || path, waiting: true, status: 'Loading…' };
      send({ type: 'read_file', root, path });
    });
  },
  editorSetText(text: string) {
    run(c => { const ed = c.st.editor; ed.text = text; ed.dirty = text !== ed.text0; ed.status = ed.dirty ? 'Unsaved changes' : ''; });
  },
  /** Save (Ctrl+S). `base` = the version to overwrite (after a conflict). Saving unchanged text just closes. */
  editorSave(base?: string | number) {
    run(c => {
      const ed = c.st.editor;
      if (!ed.editable || ed.saving) return;
      if (!ed.dirty && base == null) { closeEditor(c, true); return; }
      if (!send({ type: 'save_file', root: ed.root, path: ed.path, text: ed.text, base_version: base ?? ed.version })) return;
      ed.saving = true; ed.status = 'Saving…'; ed.banner = null;
    });
  },
  /** Cancel / Esc / backdrop: with unsaved changes the first call arms "Discard changes?" (4 s). */
  editorClose(force = false) { run(c => closeEditor(c, force)); },
  editorSetPane(pane: 'side' | 'edit' | 'preview') { lsSet(LS_EDITOR_VIEW, pane); run(c => { c.st.editor.pane = pane; }); },
  /** Conflict: load the version on disk (drops mine). */
  editorLoadTheirs() {
    run(c => {
      const ed = c.st.editor; if (!ed.conflict) return;
      ed.text = ed.conflict.text || ''; ed.text0 = ed.text; ed.version = ed.conflict.version; ed.dirty = false; ed.conflict = null; ed.banner = null; ed.status = 'Loaded the version on disk';
    });
  },
  /** Conflict: overwrite the version on disk with mine. */
  editorOverwrite() {
    const conflict = getState().editor.conflict; if (!conflict) return;
    run(c => { c.st.editor.conflict = null; });
    actions.editorSave(conflict.version);
  },
  editorToggleBackups() {
    run(c => {
      const ed = c.st.editor;
      if (ed.backupsShown) { ed.backupsShown = false; return; }
      ed.backupsShown = true; ed.backups = null;
      send({ type: 'list_backups', root: ed.root, path: ed.path });
    });
  },
  /** Restore a previous version (the view asks once more first when there are unsaved changes). */
  editorRestore(backupId: string) {
    run(c => {
      const ed = c.st.editor;
      if (send({ type: 'restore_backup', root: ed.root, path: ed.path, backup_id: backupId })) { ed.restoring = true; ed.dirty = false; ed.status = 'Restoring…'; ed.backupsShown = false; }
    });
  },

  /* ---------- Settings ---------- */
  /** Settings is a view (the header button): same as setView('settings'). */
  openSettings() { actions.setView('settings'); },

  /* ---------- Connections and the MCP library ---------- */
  testConnection(id: string) { run(c => { if (send({ type: 'test_connection', id })) c.st.connTests[id] = { status: 'testing' }; }); },
  /** Save a server (add, or edit with the name it had). The page waits for the next mcp_library. */
  saveMcpServer(server: { name: string; kind: McpKind; config: McpConfig }, originalName?: string) {
    run(c => { c.st.mcp.error = null; send(originalName ? { type: 'save_mcp_server', server, original_name: originalName } : { type: 'save_mcp_server', server }); });
  },
  removeMcpServer(name: string) { send({ type: 'remove_mcp_server', name }); },
  testMcpServer(name: string) { run(c => { if (send({ type: 'test_mcp_server', name })) { const s = c.st.mcp.servers.find(x => x.name === name); if (s) { s.status = 'testing'; s.detail = null; } } }); },
  listMcpImports(source: string) { run(c => { if (send({ type: 'list_mcp_imports', source })) c.st.mcpImports[source] = { loading: true }; }); },
  closeMcpImports(source: string) { run(c => { delete c.st.mcpImports[source]; }); },
  importMcpServers(source: string, names: string[]) { if (names.length) send({ type: 'import_mcp_servers', source, names }); },
  /* ---------- workflows ---------- */
  workflowsGet() { send({ type: 'workflows_get' }); },
  /** From an Incoming review card: show the Workflows tab with that run's review open. */
  openWorkflowReview(runId: string) { run(c => { c.st.ui.view = 'workflows'; c.st.wf.openReview = runId; send({ type: 'workflows_get' }); }); },
  clearOpenReview() { run(c => { c.st.wf.openReview = null; }); },
  /** Browse for an output folder: the picked path only fills the form's field (never connected as a working directory). */
  pickOutputFolder() { run(c => { if (send({ type: 'pick_directory' })) { c.st.ui.picking = true; c.st.ui.pickFor = 'output'; toast(c, 'Choose a folder in the picker window…'); } }); },
  clearPickedOutput() { run(c => { c.st.ui.pickedOutput = null; }); },
  /** Save (add, or edit with the id it had). The server answers workflows_list (error on a refusal). */
  saveWorkflow(folder: string, workflow: WorkflowDraft, originalId?: string) {
    run(c => { c.st.wf.error = null; send(originalId ? { type: 'workflow_save', folder, workflow, original_id: originalId } : { type: 'workflow_save', folder, workflow }); });
  },
  removeWorkflow(id: string) { send({ type: 'workflow_remove', id }); },
  runWorkflow(id: string, inputs: Record<string, string>, test: boolean, unattended: boolean) {
    run(c => { c.st.wf.error = null; const w = c.st.wf.list.find(x => x.id === id); if (w) delete c.st.wf.runErrors[w.id]; send({ type: 'workflow_run', id, inputs, test, unattended }); });
  },
  stopWorkflow(runId: string) { send({ type: 'workflow_stop', run_id: runId }); },
  /** Approve or send back one review stage (the server remembers the name: workflows_list reviewer_name). */
  reviewWorkflow(o: { runId: string; stage: number; answers: ReviewAnswerOut[]; name: string; note: string; decision: 'approve' | 'send_back'; backTo?: number }) {
    send({ type: 'workflow_review', run_id: o.runId, stage: o.stage, answers: o.answers, name: o.name.trim(), note: o.note.trim(), decision: o.decision, ...(o.backTo != null ? { back_to: o.backTo } : {}) });
  },
  setAgentMcp(agent: string, servers: string[]) {
    run(c => { if (send({ type: 'set_agent_mcp', agent, servers })) c.st.mcp.assignments[agent] = servers; });
  },
  setSettingsAddPath(path: string) { run(c => { c.st.ui.settingsAddPath = path; }); },
  addDirectory(path: string) {
    const p = String(path || '').trim(); if (!p) return;
    run(c => { if (send({ type: 'add_directory', path: p })) { c.st.ui.settingsAdding = p; toast(c, 'Adding the folder…'); } });
  },
  pickDirectory() { run(c => { if (send({ type: 'pick_directory' })) { c.st.ui.picking = true; c.st.ui.pickFor = null; toast(c, 'Choose a folder in the picker window…'); } }); },
  /** One setting changed (the view checks numbers first). */
  setSetting(key: string, value: unknown) { run(c => { if (send({ type: 'set_settings', patch: { [key]: value } })) toast(c, 'Setting sent'); }); },
  makeDefaultDir(dirId: Id) { send({ type: 'set_settings', patch: { default_dir_id: dirId } }); },
  /** Tick / untick a folder as additional (sends the whole list; a session leaves out its own primary itself). */
  setAdditionalDir(dirId: Id, on: boolean) {
    run(c => {
      const dirs = c.st.settings ? c.st.settings.directories : [];
      const ids = dirs.filter(d => (d.dir_id === dirId ? on : !!d.is_additional)).map(d => d.dir_id);
      if (!send({ type: 'set_settings', patch: { additional_dir_ids: ids } })) return;
      for (const d of dirs) if (d.dir_id === dirId) d.is_additional = on;
    });
  },

  removeDirectory(dirId: Id) { send({ type: 'remove_directory', dir_id: dirId }); },

  /* ---------- "Run it in which folder?" menu (New plan, New chat) ---------- */
  /** With 0-1 folders calls cb at once; otherwise opens the menu under `anchor` and calls cb with the picked dir_id. */
  chooseDir(anchor: Element | null, cb: (dirId: string | null) => void) {
    const dirs = dirsList(getState());
    if (dirs.length <= 1) { cb(dirs[0] ? dirs[0].dir_id : null); return; }
    const r = anchor ? anchor.getBoundingClientRect() : { top: 80, left: 80, right: 80, bottom: 80 };
    dirMenuCb = cb;
    run(c => { c.st.ui.dirMenu = { top: r.top, left: r.left, right: r.right, bottom: r.bottom }; });
  },
  pickDirFromMenu(dirId: string) { const cb = dirMenuCb; actions.closeDirMenu(); if (cb) cb(dirId); },
  closeDirMenu() { dirMenuCb = null; if (getState().ui.dirMenu) run(c => { c.st.ui.dirMenu = null; }); },
};

export type Actions = typeof actions;
export type { QueueItem };
