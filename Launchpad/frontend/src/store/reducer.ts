/* Server -> UI events. `dispatch(ev)` applies one event to the store; handleEvent has a case for EVERY event in
   the contract (src/contract.ts), ported one-for-one from the vanilla page's handle() and its on*() functions.
   Views never handle server events themselves: they read the state this produces. */
import type {
  ActivityEvent, AgentDraftedEvent, AgentFields, AgentRemovedEvent, AgentSavedEvent, AgentUsageEvent, AutoAnswerEvent, ChatHistoryItem,
  ChatModelFields, ChatStartedEvent, FileErrorEvent, FileSavedEvent, GitReposEvent, GitResultEvent, Id, PlanDraftEvent, PlannerHistoryItem, PlannerModelEvent, QueueItemEvent,
  QueueResolvedEvent, QuestionRoundEvent, RunFinishedEvent, RunStartedEvent, ServerEvent, SessionStartedEvent, SettingsEvent,
  SnapshotEvent, StepUpdateEvent, SystemEvent, UsageEvent, VisualSetEvent,
} from '../contract';
import { run, type Ctx } from './core';
import type { Activity, Chat, ChatItem, Session, VisualSet } from './types';
import {
  addBubble, addSys, addVisNote, answerQ, chatAppend, chatBubble, chatOf, chatSys, dropItem, edError, edFill, endStream,
  fxBoot, fxLoad, fxSelect, later, logFor, nextId, noteVisPick, openVis, promoLine, removeQ, requestCrew, send, sendChat,
  sess, sessOf, setChatMode, setCurrent, setTyping, showChat, syncPlanCard, toast,
} from './mutations';
import { fxKey, isFinished, problemText, qOpen, sLabel, sName } from './selectors';
import { initialCrewForm } from './initial';
import { onConnectionTest, onMcpImports, onMcpLibrary } from './mcp';
import { onWorkflowRunState, onWorkflowsList } from './workflows';
import { onReviewCase, onReviewDecided, onReviewFailed, onReviewProgress, onReviewRefused, onReviewStarted, onRolesList, reviewOf } from './roles';
import { REDUCED, baseName, modelName } from '../lib/format';
import { ADDABLE_PURPOSES, S_LABEL, WRITE_TOOLS } from '../lib/labels';
import { splitFrontMatter } from '../lib/markdown';

/** Apply one server event to the store. */
export function dispatch(ev: ServerEvent | Record<string, unknown>): void {
  if (!ev || typeof ev !== 'object') return;
  run(c => handleEvent(c, ev as ServerEvent));
}

function handleEvent(c: Ctx, ev: ServerEvent): void {
  if (!ev || typeof ev !== 'object') return;
  switch (ev.type) {
    case 'planner_message': setTyping(c, false, ev.session_id); addBubble(c, 'bot', ev.text, ev.session_id); break;
    case 'user_message': addBubble(c, 'me', ev.text, ev.session_id); break;          // only in history replays
    case 'typing': setTyping(c, !!ev.on, ev.session_id); break;
    case 'system': if (ev.chat_id != null) chatSys(c, ev.chat_id, ev.text); else onSystem(c, ev); break;
    case 'question_round': setTyping(c, false, ev.session_id); onRound(c, ev); break;
    case 'snapshot': onSnapshot(c, ev); break;
    case 'chat_started': onChatStarted(c, ev); break;
    case 'chat_typing': { const ch = chatOf(c, ev.chat_id); if (ch) ch.typing = !!ev.on; break; }
    case 'chat_delta': {
      const ch = chatOf(c, ev.chat_id); if (!ch) break;
      ch.busy = true;
      let b = ch.streamId ? ch.log.find(e => e.id === ch.streamId) : undefined;
      if (!b || b.kind !== 'bubble') { const id = nextId(c); chatAppend(ch, { kind: 'bubble', id, who: 'bot', text: '', streaming: true }); ch.streamId = id; b = ch.log[ch.log.length - 1]; }
      if (b.kind === 'bubble') b.text += String(ev.text ?? '');
      break;
    }
    case 'chat_message': {
      const ch = chatOf(c, ev.chat_id); if (!ch) break;
      const text = ev.markdown ?? ev.text ?? '';
      if (ev.role === 'user') {
        /* the plan sent from the Planner: one collapsed plan entry */
        if (ch.awaitPlan) { const from = ch.awaitPlan; ch.awaitPlan = null; chatAppend(ch, { kind: 'bubble', id: nextId(c), who: 'me', text, plan: from }); break; }
        /* the page already shows what it sent; a server echo of the same text is not shown twice */
        const lastMe = [...ch.log].reverse().find(e => e.kind === 'bubble' && e.who === 'me');
        if (!(lastMe && lastMe.kind === 'bubble' && lastMe.text === text && ch.log[ch.log.length - 1] === lastMe)) chatBubble(c, ch.id, 'me', text);
        break;
      }
      const b = ch.streamId ? ch.log.find(e => e.id === ch.streamId) : undefined;
      if (b && b.kind === 'bubble') { b.streaming = false; b.text = text; } else chatBubble(c, ch.id, 'bot', text);
      endStream(ch);
      break;
    }
    case 'chat_mode': { const ch = chatOf(c, ev.chat_id); if (ch && ['default', 'accept_edits', 'plan'].includes(ev.mode)) ch.mode = ev.mode; break; }
    case 'chat_done': {
      const ch = chatOf(c, ev.chat_id); if (!ch) break;
      ch.busy = false; ch.typing = false;
      const b = ch.streamId ? ch.log.find(e => e.id === ch.streamId) : undefined;
      if (b && b.kind === 'bubble') b.streaming = false;
      endStream(ch);
      if (ev.status === 'stopped') chatSys(c, ch.id, 'Interrupted. Say what to do instead, or carry on.');
      else if (ev.status === 'failed') chatSys(c, ch.id, `The turn failed${ev.error ? ': ' + ev.error : '.'}`, 'err');
      break;
    }
    case 'plan_meta': {
      const s = sessOf(c, ev.session_id);
      if (!s) { if (ev.name) c.st.preName = ev.name; break; }       // no session yet: only the header text (vanilla)
      if (ev.session_id == null && (s.meta || c.st.replaying)) break;   // an unscoped plan_meta never overrides a session's own header
      s.meta = { ...(s.meta || {}) };
      for (const k of ['name', 'mode', 'status'] as const) if (ev[k]) s.meta[k] = ev[k];
      if (ev.name && !/^(new session|new plan|launchpad)$/i.test(ev.name)) s.planTitle = ev.name;
      break;
    }
    case 'crew':
      for (const a of Array.isArray(ev.agents) ? ev.agents : []) {
        if (!(a.role === 'planner' || (!a.role && /planner|navigator/i.test(a.name || '')))) continue;
        const s = sessOf(c, a.session_id);
        if (s && a.status) s.plannerStatus = a.status;
      }
      break;
    case 'usage': onUsage(c, ev); endReplay(c); break;
    case 'session_started': onSessionStarted(c, ev); break;
    case 'plan_draft': onPlanDraft(c, ev); break;
    case 'run_started': onRunStarted(c, ev); break;
    case 'step_update': onStepUpdate(c, ev); break;
    case 'run_finished': onRunFinished(c, ev); break;
    case 'agent_usage': onAgentUsage(c, ev); break;
    case 'queue_item': onQueueItem(c, ev); break;
    case 'queue_resolved': onQueueResolved(c, ev); break;
    case 'crew_list': {
      c.st.crewDefs = Array.isArray(ev.agents) ? ev.agents : [];
      c.st.crewLoading = false;
      if (ev.dir_id !== undefined) c.st.crewDirId = ev.dir_id ?? null;
      if (Array.isArray(ev.tool_choices)) c.st.toolChoices = ev.tool_choices.map(String);
      c.st.crewSkills = Array.isArray(ev.skills) ? ev.skills : [];
      for (const a of c.st.crewDefs) if (typeof a.uses === 'number') c.st.crewUses[a.name] = a.uses;
      break;
    }
    case 'agent_uses': if (ev.name != null && typeof ev.uses === 'number') c.st.crewUses[ev.name] = ev.uses; break;
    case 'agent_drafted': onAgentDrafted(c, ev); break;
    case 'agent_saved': onAgentSaved(c, ev); break;
    case 'agent_removed': onAgentRemoved(c, ev); break;
    case 'roles_list': onRolesList(c, ev); break;
    case 'connection_test': onConnectionTest(c, ev); break;
    case 'mcp_library': onMcpLibrary(c, ev); break;
    case 'mcp_imports': onMcpImports(c, ev); break;
    case 'workflows_list': onWorkflowsList(c, ev); break;
    case 'workflow_run_state': onWorkflowRunState(c, ev); break;
    case 'review_started': onReviewStarted(c, ev); break;
    case 'review_progress': onReviewProgress(c, ev); break;
    case 'review_case': onReviewCase(c, ev); break;
    case 'review_failed': onReviewFailed(c, ev); break;
    case 'review_refused': onReviewRefused(c, ev); break;
    case 'review_decided': onReviewDecided(c, ev); break;
    case 'git_repos': onGitRepos(c, ev); break;
    case 'git_result': onGitResult(c, ev); break;
    case 'activity': onActivity(c, ev); break;
    case 'visual_set': onVisualSet(c, ev); break;
    case 'autopilot': { const s = sess(c, ev.session_id); if (s) s.autopilot = !!ev.on; break; }
    case 'auto_answers': { const s = sess(c, ev.session_id); if (s) s.autoAnswers = !!ev.on; break; }
    case 'auto_answer': onAutoAnswer(c, ev); break;
    case 'planner_model': onPlannerModel(c, ev); break;
    case 'planner_choice': { const { type: _t, ...data } = ev; c.st.plannerChoice = data; c.st.ui.pickerChoosing = null; break; }
    case 'cli_choice': { const { type: _t, ...data } = ev; c.st.cliChoice = data; c.st.ui.cliChoosing = null; break; }
    case 'chat_model': {
      const ch = c.st.chats[ev.chat_id]; if (!ch) break;
      const was = ch.label;
      applyChatModel(ch, ev);
      /* an unstarted chat reloaded on another CLI / model: say so under its "New chat" line */
      if (!c.st.replaying && !ev.started && ch.label && was && was !== ch.label) chatSys(c, ch.id, `This chat now runs on ${ch.label}.`);
      break;
    }
    case 'settings': onSettings(c, ev); break;
    case 'directory_picked': {
      c.st.ui.picking = false;
      if (c.st.ui.pickFor === 'output') {          // the workflow form: only fill its field, never add_directory
        c.st.ui.pickFor = null;
        if (!ev.path) toast(c, 'No folder was picked'); else c.st.ui.pickedOutput = ev.path;
        break;
      }
      if (!ev.path) { toast(c, 'No folder was picked'); break; }
      c.st.ui.settingsAddPath = ev.path;
      if (send({ type: 'add_directory', path: ev.path })) { c.st.ui.settingsAdding = ev.path; toast(c, 'Adding the folder…'); }
      break;
    }
    case 'dir_listing': {
      const k = fxKey(ev.root, ev.path || '');
      delete c.st.fx.loading[k]; delete c.st.fx.err[k];
      c.st.fx.cache[k] = (Array.isArray(ev.entries) ? ev.entries : []).slice()
        .sort((a, b) => (a.type === 'dir' ? 0 : 1) - (b.type === 'dir' ? 0 : 1) || String(a.name).localeCompare(String(b.name)));
      break;
    }
    case 'file_content': {
      const { type: _t, ...data } = ev;
      const k = fxKey(ev.root, ev.path);
      c.st.files[k] = data;
      const ed = c.st.editor;
      if (ed.open && fxKey(ed.root, ed.path) === k && ed.waiting) edFill(c, data);
      break;
    }
    case 'file_saved': onFileSaved(c, ev); break;
    case 'file_error': onFileError(c, ev); break;
    case 'backups': {
      const ed = c.st.editor;
      if (!ed.open || fxKey(ev.root, ev.path) !== fxKey(ed.root, ed.path)) break;
      ed.backups = Array.isArray(ev.items) ? ev.items : [];
      break;
    }
  }
}

/* ---------------- Repos panel ---------------- */
function onGitRepos(c: Ctx, ev: GitReposEvent): void {
  const g = c.st.git, ids = new Set(ev.repos.map(r => r.repo_id));
  g.available = !!ev.available; g.loaded = true; g.scanning = false; g.repos = Array.isArray(ev.repos) ? ev.repos : [];
  g.busy = {};
  for (const m of [g.error, g.note, g.unticked, g.message, g.open] as Record<string, unknown>[]) for (const k of Object.keys(m)) if (!ids.has(k)) delete m[k];
}
function onGitResult(c: Ctx, ev: GitResultEvent): void {
  const g = c.st.git, id = ev.repo_id;
  delete g.busy[id];
  const i = g.repos.findIndex(r => r.repo_id === id);
  if (ev.repo && i >= 0) g.repos[i] = ev.repo;
  if (i < 0) { toast(c, ev.message || 'That repo is not in the list any more.'); return; }
  if (ev.ok) { g.note[id] = ev.message; delete g.error[id]; } else { g.error[id] = ev.message || 'git failed.'; delete g.note[id]; }
  if (ev.committed) { g.message[id] = ''; delete g.unticked[id]; }
}

/* ---------------- sessions ---------------- */
function onSessionStarted(c: Ctx, ev: SessionStartedEvent): void {
  const known = !!c.st.sessions[ev.session_id];
  const s = sess(c, ev.session_id); if (!s) return;
  if (ev.folder) s.folder = ev.folder;
  if (ev.dir_id != null) s.dirId = ev.dir_id;
  if (ev.cwd) s.cwd = ev.cwd;
  if (!known) addSys(c, `New plan started${s.folder ? ' · ' + s.folder : ''}`, s.id);
  if (ev.report_sent != null) s.reportSent = !!ev.report_sent;
  if (Array.isArray(ev.chat)) replayHistory(c, s.id, ev.chat);
  if (c.st.current !== s.id) setCurrent(c, s.id); else c.st.ui.newPlanBusy = false;
}

/** Snapshot history replaces that session's chat log. */
function replayHistory(c: Ctx, sid: Id, items: PlannerHistoryItem[]): void {
  const s = sess(c, sid); if (!s) return;
  s.log = []; s.typing = false;
  for (const it of items || []) {
    if (!it || typeof it !== 'object') continue;
    if (it.type) { handleEvent(c, { ...it, session_id: sid } as ServerEvent); continue; }
    if (it.role === 'round') { if (it.round) onRound(c, { ...it.round, type: 'question_round', session_id: sid }); continue; }
    if (it.role === 'answers') { replayAnswers(c, it.roundId, it.answers, !!it.skipped, sid); continue; }
    const text = it.text ?? it.markdown ?? '';
    if (it.role === 'user') addBubble(c, 'me', text, sid);
    else if (it.role === 'assistant' || it.role === 'planner') addBubble(c, 'bot', text, sid);
    else if (text) addSys(c, text, sid);
  }
  if (!s.log.some(e => e.kind === 'plancard') && s.draft) {
    s.log.push({ kind: 'plancard', id: nextId(c), draft: { ...s.draft }, draftV: s.draftV, rev: s.draftRev ?? s.draftV, state: 'open' });
    syncPlanCard(s);
  }
}

function replayAnswers(c: Ctx, roundId: string, answers: Record<string, { accepted: boolean; option?: string; text?: string }>, skipped: boolean, sid: Id): void {
  const r = c.st.rounds[roundId]; if (!r) return;
  for (const q of r.questions) { const a = (answers || {})[q.id]; if (a && !r.answers[q.id]) answerQ(c, r, q.id, { ...a, text: a.text || a.option || '' }, true); }
  r.sent = true; r.actionsHidden = true;
  if (skipped) addSys(c, 'Round skipped. Open questions stay open and come back later.', sid);
}

function onSnapshot(c: Ctx, ev: SnapshotEvent): void {
  c.st.replaying = true; c.st.quiet = true;              // the replayed events that follow are history, not news
  later(c, 3000, () => run(c2 => endReplay(c2)), 'snapshot');
  for (const x of Array.isArray(ev.sessions) ? ev.sessions : []) {
    const sid = x.session_id ?? x.id, s = sess(c, sid); if (!s) continue;
    if (x.folder) s.folder = x.folder;
    if (x.dir_id != null) s.dirId = x.dir_id;
    if (x.cwd) s.cwd = x.cwd;
    if (x.report_sent != null) { s.reportSent = !!x.report_sent; s.snapReportSent = !!x.report_sent; }
    if (typeof x.planner_cost_usd === 'number') s.plannerCost = x.planner_cost_usd;
    if (typeof x.total_cost_usd === 'number') s.total = x.total_cost_usd;
    if (x.autopilot != null) s.autopilot = !!x.autopilot;
    if (x.auto_answers != null) s.autoAnswers = !!x.auto_answers;
    {
      const pm = x.planner_model && typeof x.planner_model === 'object' ? x.planner_model : x;    // same fields as planner_model
      const model = typeof x.planner_model === 'string' ? x.planner_model : pm.model;
      if (model) onPlannerModel(c, { type: 'planner_model', session_id: s.id, model, promoted: !!pm.promoted, reason: pm.reason ?? null, by: pm.by ?? null,
        harness: x.harness, start_model: x.start_model, top_model: x.top_model, label: x.label, option_id: x.option_id, auto_promote: x.auto_promote,
        started: x.started, switchable_to: x.switchable_to });
    }
    const h = x.chat ?? x.history; if (Array.isArray(h)) replayHistory(c, s.id, h);
    if (Array.isArray(x.visual_sets)) for (const v of x.visual_sets) onVisualSet(c, { ...v, type: 'visual_set', session_id: s.id });
  }
  for (const ch of Array.isArray(ev.chats) ? ev.chats : []) {
    const id = ch.chat_id ?? ch.id; if (id == null) continue;
    onChatStarted(c, { ...ch, type: 'chat_started', chat_id: id });
  }
  if (ev.current_session_id != null) setCurrent(c, ev.current_session_id);
}

function endReplay(c: Ctx): void {
  if (!c.st.replaying) return;
  c.st.replaying = false; c.st.quiet = false;
}

/** A system line goes into its session's chat; when that chat is not on screen, or it answers an Approve the page is
    waiting on, it is also a toast. While Settings is open, an unscoped one is the answer to a settings request. */
function onSystem(c: Ctx, ev: SystemEvent): void {
  if (c.st.ui.view === 'settings' && ev.session_id == null && !c.st.replaying) {
    c.st.ui.settingsMsg = ev.text;
    later(c, 9000, () => run(c2 => { c2.st.ui.settingsMsg = null; }), 'settingsMsg');
    c.st.ui.settingsAdding = null; c.st.ui.picking = false;
    return;
  }
  addSys(c, ev.text, ev.session_id);
  if (c.st.replaying) return;
  const s = ev.session_id != null ? c.st.sessions[ev.session_id] || null : null;
  const waiting = !!s && s.approving && /draft|approve|already going|no run|cannot|can't/i.test(String(ev.text || ''));
  if (waiting && s) s.approving = false;
  /* "Send plan to CLI" refused (no draft, no folder ...): the answer is this system line */
  const codeRefused = !!s && s.codeSending;
  if (codeRefused && s) { s.codeSending = false; if (c.st.chatFromPlan === s.id) { c.st.chatFromPlan = null; c.st.ui.newChatBusy = false; } }
  if (waiting || codeRefused || (s && (s.id !== c.st.current || c.st.ui.view !== 'plan' || c.st.ui.chatSide !== 'planner'))) toast(c, `${s ? sLabel(s) + ': ' : ''}${ev.text}`);
}

/* ---------------- question rounds ---------------- */
function onRound(c: Ctx, ev: QuestionRoundEvent): void {
  const rs = sessOf(c, ev.session_id);
  if (rs) rs.roundTag = `Round ${ev.round}`; else c.st.preRoundTag = `Round ${ev.round}`;
  c.st.rounds[ev.id] = { id: ev.id, sessionId: rs ? rs.id : null, round: ev.round, questions: ev.questions || [], answers: {}, sent: false, actionsHidden: false };
  logFor(c, ev.session_id).push({ kind: 'round', id: nextId(c), roundId: ev.id });
}

/** A builder's question decided under Auto answers: a settled, marked line in Incoming (a card that was waiting is settled in place). */
function onAutoAnswer(c: Ctx, ev: AutoAnswerEvent): void {
  const ex = c.st.queue.find(i => i.id === ev.id);
  if (ex) { ex.ui = 'decided'; ex.answer = ev.answer; return; }
  if (ev.session_id != null) sess(c, ev.session_id);
  c.st.queue.push({ id: ev.id, kind: 'question', session_id: ev.session_id, agent: ev.agent || 'Builder', step: ev.step ?? null, title: ev.title,
    rec: ev.answer, at: Date.now(), ui: 'decided', answer: ev.answer });
}

/* ---------------- plan drafts ---------------- */
function onPlanDraft(c: Ctx, ev: PlanDraftEvent): void {
  const s = sess(c, ev.session_id); if (!s) return;
  const h = String(ev.markdown || '').match(/^\s*#\s+(.+)$/m), fm = splitFrontMatter(ev.markdown);
  s.draft = { path: ev.path || '', markdown: ev.markdown || '', steps: Array.isArray(ev.steps) ? ev.steps : [], title: h ? h[1].trim() : '',
              status: fm && typeof fm.meta.status === 'string' ? fm.meta.status : '' };
  s.draftV = (s.draftV || 0) + 1;
  if (typeof ev.revision === 'number') s.draftRev = ev.revision;
  /* the server only saves a draft when no run is going: if this page still thinks a run is in flight, it ended */
  if (s.status === 'running' && !c.st.replaying && ((ev.previous_runs ?? 0) > 0 || s.run)) {
    s.status = (s.run && s.run.steps.some(x => x.status === 'blocked' || x.status === 'failed')) ? 'blocked' : 'done';
    for (const i of c.st.queue) if (i.session_id === s.id && qOpen(i)) i.ui = 'ended';
  }
  if (s.draft.status === 'approved' && s.run) s.runDraftV = s.draftV;      // a replay of the plan the current run launched
  s.approving = false;
  for (const e of s.log) if (e.kind === 'plancard' && e.state === 'open') e.state = 'superseded';
  s.typing = false;
  s.log.push({ kind: 'plancard', id: nextId(c), draft: { ...s.draft, steps: [...s.draft.steps] }, draftV: s.draftV, rev: s.draftRev ?? s.draftV, state: 'open' });
  syncPlanCard(s);
  needCrewFor(c, s.draft.steps);
  if (s.id !== c.st.current) toast(c, `Plan draft for ${sLabel(s)} is ready in Missions`);
}

/** Steps that name an agent need the crew list for its purpose colour: ask for it once. */
function needCrewFor(c: Ctx, steps: { agent?: string | null }[]): void {
  if (!c.st.crewDefs && !c.st.crewLoading && steps.some(x => x.agent)) requestCrew(c);
}

/* ---------------- runs ---------------- */
function onRunStarted(c: Ctx, ev: RunStartedEvent): void {
  const s = sess(c, ev.session_id); if (!s) return;
  const again = !!s.run;
  /* the run launched the current draft (on a replay, a newer unapproved draft that arrived first stays approvable) */
  if (!(c.st.replaying && s.draft && s.draft.status === 'draft')) s.runDraftV = s.draftV || 0;
  if (typeof ev.revision === 'number') s.runRev = ev.revision;
  if (ev.autopilot != null) s.autopilot = !!ev.autopilot;
  if (ev.auto_answers != null) s.autoAnswers = !!ev.auto_answers;
  if (ev.workflow) s.wf = ev.workflow;
  s.run = { name: ev.name || sName(s), started: Date.now(),
            steps: (Array.isArray(ev.steps) ? ev.steps : []).map(st => ({ n: st.n, title: st.title || `Step ${st.n}`, status: st.status || 'todo', built: [], report_path: '',
              agent: st.agent ?? null, agent_display: st.agent_display ?? null, agent_fallback: !!st.agent_fallback, agent_purpose: st.agent_purpose ?? null,
              skills: st.skills || [], skills_unknown: st.skills_unknown || [], ...(st.role ? { role: st.role } : {}), ...(st.waiting_for ? { waiting_for: st.waiting_for } : {}) })) };
  /* a new run in the same session: fresh steps, back in flight; earlier agents and their costs stay in the session */
  Object.assign(s, { status: 'running', approving: false, report: null, reportSent: false, snapReportSent: false, cleared: false, stopping: false, flash: 0 });
  if (again) removeQ(c, 'report:' + s.id);
  syncPlanCard(s);
  needCrewFor(c, s.run.steps);
  if (!c.st.replaying && !s.wf) addSys(c, again ? `Run ${s.letter} launched again: ${s.run.name}` : `Run ${s.letter} launched: ${s.run.name}`, s.id);
  toast(c, s.wf ? `${s.wf.test ? 'Test run' : 'Workflow'} started · ${s.wf.name}` : `Run ${s.letter} launched · ${s.run.name}`);
}

function onStepUpdate(c: Ctx, ev: StepUpdateEvent): void {
  const s = sess(c, ev.session_id); if (!s) return;
  if (!s.run) { s.run = { name: sName(s), steps: [], started: Date.now() }; if (!isFinished(s)) s.status = 'running'; }
  let st = s.run.steps.find(x => String(x.n) === String(ev.n));
  if (!st) { s.run.steps.push({ n: ev.n, title: `Step ${ev.n}`, status: 'todo', built: [], report_path: '' }); s.run.steps.sort((a, b) => a.n - b.n); st = s.run.steps.find(x => String(x.n) === String(ev.n))!; }
  if (ev.status) { if (ev.status === 'done' && st.status !== 'done') { s.flash = Date.now(); s.flashN = st.n; } st.status = ev.status; if (ev.status !== 'blocked') delete st.waiting_for; }
  if (ev.waiting_for) st.waiting_for = ev.waiting_for;
  if (Array.isArray(ev.built)) for (const b of ev.built) if (!st.built.includes(b)) st.built.push(b);
  if (ev.report_path) st.report_path = ev.report_path;
  if (ev.agent !== undefined) st.agent = ev.agent;
  if (ev.agent_display !== undefined) st.agent_display = ev.agent_display;
  if (ev.agent !== undefined || ev.agent_display !== undefined || ev.agent_fallback !== undefined) st.agent_fallback = !!ev.agent_fallback;
  if (ev.agent_purpose !== undefined) st.agent_purpose = ev.agent_purpose;
  if (ev.skills !== undefined) { st.skills = ev.skills || []; st.skills_unknown = ev.skills_unknown || []; }
  if (ev.role !== undefined) st.role = ev.role || undefined;
}


function onRunFinished(c: Ctx, ev: RunFinishedEvent): void {
  const s = sess(c, ev.session_id); if (!s) return;
  if (ev.workflow) s.wf = ev.workflow;
  s.status = (['done', 'stopped', 'failed', 'blocked'] as const).includes(ev.status) ? ev.status : ev.status ? 'failed' : 'done';
  s.stopping = false;
  s.reportSent = ev.report_sent != null ? !!ev.report_sent : !!s.snapReportSent;   // the snapshot knows if it was sent
  s.snapReportSent = false;
  if (typeof ev.planner_cost_usd === 'number') s.plannerCost = ev.planner_cost_usd;
  if (typeof ev.total_cost_usd === 'number') s.total = ev.total_cost_usd;
  s.report = { path: ev.report_path || '', markdown: ev.markdown || '', total: typeof ev.total_cost_usd === 'number' ? ev.total_cost_usd : null };
  if (!s.run) s.run = { name: sName(s), steps: [], started: Date.now() };
  s.run.finished = Date.now();
  for (const i of c.st.queue) if (i.session_id === s.id && qOpen(i)) i.ui = 'ended';
  const rid = 'report:' + s.id;
  removeQ(c, rid);
  c.st.queue.push({ id: rid, kind: 'report', session_id: s.id, agent: s.wf ? '' : 'Orchestrator', step: null, title: '', at: Date.now(), ui: 'open' });
  if (!c.st.replaying && !s.wf) addSys(c, `Run ${s.letter} (${sName(s)}) finished: ${S_LABEL[s.status].toLowerCase()}. The report is in Incoming.`, s.id);
  toast(c, s.wf ? `${s.wf.name}${s.wf.test ? ' (test run)' : ''} finished · ${S_LABEL[s.status]}` : `Run ${s.letter} finished · ${S_LABEL[s.status]}`);
}

/** The server's totals (app / session / chat), stored as sent: the page adds no costs up itself. */
function onUsage(c: Ctx, ev: UsageEvent): void {
  const n = (v: unknown): number => +(v as number) || 0;
  if (ev.scope === 'session') {
    const s = sess(c, ev.session_id); if (!s) return;
    s.total = n(ev.cost); s.plannerCost = n(ev.planner_cost); s.crewAgents = n(ev.agents);
    s.crewTok = { i: n(ev.input_tokens), o: n(ev.output_tokens), cr: n(ev.cache_read_tokens), cw: n(ev.cache_write_tokens) };
    s.stepTotals = {};
    for (const [k, v] of Object.entries(ev.steps || {})) s.stepTotals[k] = { cost: n(v.cost), tools: n(v.tool_calls), n: n(v.agents), i: n(v.input_tokens), o: n(v.output_tokens), cr: n(v.cache_read_tokens), cw: n(v.cache_write_tokens) };
  } else if (ev.scope === 'chat') {
    c.st.chatTotals[ev.chat_id] = { cost: n(ev.cost), tools: n(ev.tool_calls), n: n(ev.agents), i: n(ev.input_tokens), o: n(ev.output_tokens), cr: n(ev.cache_read_tokens), cw: n(ev.cache_write_tokens) };
  } else {
    c.st.tokens = n(ev.tokens); c.st.cost = n(ev.cost); c.st.usageEv = { ...ev }; c.st.byRole = { ...(ev.by_role || {}) };
  }
}

function onAgentUsage(c: Ctx, ev: AgentUsageEvent): void {
  if (ev.agent_id == null) return;
  const prev = c.st.agents[ev.agent_id];
  const { type: _t, ...data } = ev;
  const a = { ...(prev || {}), ...data };
  c.st.agents[ev.agent_id] = a;
  if (a.session_id != null) sess(c, a.session_id);
  if (a.role === 'planner') {
    const s = sessOf(c, a.session_id);
    if (s) { s.plannerId = a.agent_id; if (!prev || prev.status !== a.status) s.plannerStatus = a.status || 'idle'; }
  }
  if (a.chat_id != null) { const ch = c.st.chats[a.chat_id]; if (ch && !ch.agentIds.includes(a.agent_id)) ch.agentIds.push(a.agent_id); }
}

/* ---------------- planner model ---------------- */
function onPlannerModel(c: Ctx, ev: PlannerModelEvent): void {
  const s = sessOf(c, ev.session_id); if (!s) return;
  const was = !!s.promoted;
  s.plannerModel = ev.model || s.plannerModel; s.promoted = !!ev.promoted; s.promoReason = ev.reason || null; s.promoBy = ev.by || null; s.promoting = false;
  if (ev.harness !== undefined) s.plannerHarness = ev.harness || null;
  if (ev.start_model !== undefined) s.plannerStart = ev.start_model || null;
  if (ev.top_model !== undefined) s.plannerTop = ev.top_model || null;
  if (ev.label !== undefined) s.plannerLabel = ev.label || null;
  if (ev.option_id !== undefined) s.plannerOption = ev.option_id || null;
  if (ev.started !== undefined) s.plannerStarted = !!ev.started;
  if (ev.auto_promote !== undefined) s.plannerAuto = !!ev.auto_promote;
  if (Array.isArray(ev.switchable_to)) s.switchableTo = ev.switchable_to.map(String);
  if (s.id === c.st.current) c.st.ui.pickerChoosing = null;
  /* one line per promotion: live, or restored on reload (the server's chat history does not carry it) */
  if (s.promoted && (!was || c.st.replaying) && !s.log.some(e => e.kind === 'sys' && e.cls === 'promo')) {
    const line = { kind: 'sys' as const, id: nextId(c), text: promoLine(s), cls: 'promo' as const };
    const firstMe = c.st.replaying ? s.log.findIndex(e => e.kind === 'bubble' && e.who === 'me') : -1;   // restored: just after the first message
    if (firstMe >= 0) s.log.splice(firstMe + 1, 0, line); else s.log.push(line);
    if (!c.st.replaying && s.id !== c.st.current) toast(c, `${sLabel(s)}: planner moved to ${modelName(s.plannerModel)}`);
  }
  if (!c.st.crewDefs && !c.st.crewLoading && !c.st.ui.demo) requestCrew(c);
}

/* ---------------- Incoming ---------------- */
function onQueueItem(c: Ctx, ev: QueueItemEvent): void {
  if (ev.id == null) return;
  const { type: _t, ...item } = ev;
  if (item.chat_id != null) { onChatItem(c, item); return; }          // CLI chats: shown inline in that chat
  if (item.session_id != null) sess(c, item.session_id);
  const ex = c.st.queue.find(i => i.id === item.id);
  if (ex) Object.assign(ex, item);
  else {
    c.st.queue.push({ ...item, at: Date.now(), ui: 'open' });
    if (c.st.ui.vis.open && item.blocking && !c.st.replaying) toast(c, 'A card in Incoming is blocking a run. Use the Incoming button on the Visuals panel.');
  }
}

function onQueueResolved(c: Ctx, ev: QueueResolvedEvent): void {
  if (c.st.chatItems[ev.id]) { onChatItemResolved(c, ev); return; }
  const i = c.st.queue.find(x => x.id === ev.id); if (!i) return;
  if (ev.by === 'auto') { if (i.ui !== 'decided') { i.ui = 'decided'; i.answer = ev.answer ?? i.rec ?? ''; } return; }
  if (ev.by === 'timer' && i.kind === 'permission') { i.ui = 'timedout'; i.answer = ev.answer ?? 'deny'; return; }
  if (ev.by === 'autopilot') { i.ui = 'autopilot'; i.answer = ev.answer ?? 'allow'; return; }
  if (ev.by === 'timer') { i.ui = 'auto'; i.answer = ev.answer ?? i.rec ?? ''; return; }
  dropItem(c, i.id, REDUCED);
}

/* ---------------- activity ---------------- */
function onActivity(c: Ctx, ev: ActivityEvent): void {
  if (ev.id == null) return;
  const { type: _t, ...data } = ev;
  let a = c.st.acts.find(x => x.id === ev.id);
  const isNew = !a;
  if (a) Object.assign(a, data);
  else {
    c.st.acts.push(data);
    if (c.st.acts.length > 600) c.st.acts.shift();
    a = c.st.acts[c.st.acts.length - 1];
  }
  if (a.session_id != null) sess(c, a.session_id);
  c.st.lastAct[a.agent_id] = a.id;
  const snap: Activity = JSON.parse(JSON.stringify(a));
  if (a.chat_id != null) chatActivity(c, snap);
  if (isNew || a.status === 'denied' || a.status === 'failed') c.fx.pings.push({ a: snap, isNew });
}

/* ---------------- CLI chats ---------------- */
/** A chat's CLI and model from chat_started / chat_model / the snapshot (only the fields the server sent). */
function applyChatModel(ch: Chat, ev: ChatModelFields): void {
  if (ev.model) ch.model = ev.model;
  if (ev.harness !== undefined) ch.harness = ev.harness || null;
  if (ev.label !== undefined) ch.label = ev.label || null;
  if (ev.option_id !== undefined) ch.optionId = ev.option_id || null;
  if (ev.started) ch.written = true;
}

function onChatStarted(c: Ctx, ev: ChatStartedEvent): void {
  const ch = chatOf(c, ev.chat_id); if (!ch) return;
  if (ev.mode) ch.mode = ev.mode;
  applyChatModel(ch, ev);
  if (ev.cwd) ch.cwd = ev.cwd;
  if (ev.dir_id != null) ch.dirId = ev.dir_id;
  if (ev.busy != null) ch.busy = !!ev.busy;
  const fresh = !ch.started; ch.started = true;
  /* the answer to "Send plan to CLI": the server opened this chat in Plan mode and sent the plan as its first message */
  const fromId = ev.from_session_id ?? (fresh && !c.st.replaying ? c.st.chatFromPlan : null);
  const fromPlan = fresh && !c.st.replaying && fromId != null ? c.st.sessions[fromId] || null : null;
  if (fromPlan || (fresh && !c.st.replaying && !ev.from_session_id)) c.st.chatFromPlan = null;
  if (Array.isArray(ev.history)) {
    ch.log = []; ch.typing = false; endStream(ch);
    for (const h of ev.history) replayChatItem(c, ch.id, h);
  } else if (fresh) chatSys(c, ch.id, `New chat${ch.label ? ' · ' + ch.label : ch.model ? ' · ' + modelName(ch.model) : ''}${ch.cwd ? ' · ' + ch.cwd : ''}`);
  showChat(c, ch.id);
  c.st.ui.newChatBusy = false;
  if (fromPlan) {
    fromPlan.codeSending = false; fromPlan.codeSentV = fromPlan.draftV;
    ch.awaitPlan = `Plan from ${sLabel(fromPlan)} · ${sName(fromPlan)}`;
    chatSys(c, ch.id, 'The CLI starts in Plan mode: nothing changes until you approve its plan.');
    if (ev.busy == null) { ch.busy = true; ch.typing = true; }
    c.st.ui.chatSide = 'code';
    return;                                          // keeps the server's mode (plan) and sends nothing else
  }
  if (c.st.codeModePref && c.st.codeModePref !== ch.mode) setChatMode(c, c.st.codeModePref);
  if (c.st.chatPending != null) { const t = c.st.chatPending; c.st.chatPending = null; sendChat(c, t); }
}

function replayChatItem(c: Ctx, cid: Id, h: ChatHistoryItem): void {
  if (!h || typeof h !== 'object') return;
  if (h.type) { handleEvent(c, { ...h, chat_id: cid } as ServerEvent); return; }
  if (h.tool) {
    const act: Activity = { id: h.id || nextId(c, 'h'), session_id: null, chat_id: cid, agent_id: h.agent_id || '', role: h.role || 'pilot', name: h.name || '',
      step: h.step ?? null, tool: h.tool, summary: h.summary || '', status: h.status || 'done', ts: h.ts || '' };
    chatActivity(c, act);
    return;
  }
  const plain = h as { role?: string; markdown?: string; text?: string };
  const text = plain.markdown ?? plain.text ?? '';
  if (plain.role === 'user') chatBubble(c, cid, 'me', text);
  else if (plain.role === 'assistant') chatBubble(c, cid, 'bot', text);
  else chatSys(c, cid, text);
}

/** Tool calls as compact inline rows; a row arriving mid-reply ends the current bubble. */
function chatActivity(c: Ctx, a: Activity): void {
  const ch = chatOf(c, a.chat_id); if (!ch) return;
  const row = ch.log.find(e => e.kind === 'tool' && e.act.id === a.id);
  if (row && row.kind === 'tool') row.act = a;
  else { endStream(ch); chatAppend(ch, { kind: 'tool', id: nextId(c), act: a }); }
  if (!a.status || a.status === 'started') ch.busy = true;
}

function onChatItem(c: Ctx, item: Omit<QueueItemEvent, 'type'>): void {
  const ch = chatOf(c, item.chat_id); if (!ch) return;
  const ex = c.st.chatItems[item.id];
  const kind = (['permission', 'plan', 'question', 'info'].includes(item.kind) ? item.kind : 'info') as ChatItem['kind'];
  const next: ChatItem = { ...(ex || {}), ...item, chat_id: ch.id, kind, ui: ex ? ex.ui : 'open' } as ChatItem;
  c.st.chatItems[item.id] = next;
  if (!ex || !ch.log.some(e => e.kind === 'card' && e.itemId === item.id)) { endStream(ch); chatAppend(ch, { kind: 'card', id: nextId(c), itemId: item.id }); }
}

function onChatItemResolved(c: Ctx, ev: QueueResolvedEvent): void {
  const i = c.st.chatItems[ev.id]; if (!i) return;
  if (i.ui === 'open') i.result = ev.answer == null ? 'Closed (the turn ended)' : ({ allow: 'Allowed', deny: 'Denied', always: 'Always allowed' } as Record<string, string>)[ev.answer] || `Answered: ${ev.answer}`;
  i.ui = 'done';
}

/* ---------------- visuals ---------------- */
function onVisualSet(c: Ctx, ev: VisualSetEvent): void {
  const s = sessOf(c, ev.session_id); if (!s || ev.set_id == null) return;
  const sets = s.visualSets;
  const prev = sets.find(x => x.set_id === ev.set_id);
  const before = new Map(((prev && prev.options) || []).map(o => [o.id, o.html] as const));
  const data = { set_id: ev.set_id, brief: String(ev.brief || ''), options: Array.isArray(ev.options) ? ev.options : [], picked_id: ev.picked_id ?? null,
    library: ev.library ?? null, drawn_with: String(ev.drawn_with || 'echarts'), libraries: Array.isArray(ev.libraries) ? ev.libraries.map(String) : [],
    library_note: ev.library_note ? String(ev.library_note) : null };
  let cur: VisualSet;
  if (prev) { Object.assign(prev, data); cur = prev; }
  else { sets.push({ ...data, pending: {}, notedPick: null }); cur = sets[sets.length - 1]; }
  for (const o of cur.options) { if (cur.pending[o.id] && (o.status !== 'ready' || !before.has(o.id) || before.get(o.id) !== o.html)) delete cur.pending[o.id]; }
  if (!prev) {
    cur.notedPick = cur.picked_id;
    if (c.st.replaying) s.visSeen = sets.length;          // restored sets are not "new"
    else {
      addVisNote(c, `Visuals: ${cur.brief || 'design options'} · ${cur.options.length} option${cur.options.length === 1 ? '' : 's'} to compare.`, s.id, cur.set_id);
      if (s.id === c.st.current) { s.visSel = sets.length - 1; if (c.st.ui.view === 'plan') openVis(c, true); }
    }
  } else if (cur.picked_id !== cur.notedPick) {
    noteVisPick(c, s.id, cur);
  }
  if (s.visSel == null) s.visSel = sets.length - 1;
}

/* ---------------- Crew: draft / create / remove an agent ---------------- */
function onAgentDrafted(c: Ctx, ev: AgentDraftedEvent): void {
  const f = c.st.crewForm;
  if (!f.drafting) return;                           // the form was closed (or never asked)
  f.drafting = false;
  if (ev.usage) f.cost = ev.usage;
  if (!ev.ok || !ev.fields) { f.draftError = ev.error || 'The drafter could not fill the form. Try saying it another way, or fill it in yourself.'; return; }
  const d = ev.fields, cur = f.fields;
  const purpose = String(d.purpose || '');
  f.fields = {
    name: d.name != null ? String(d.name) : cur.name,
    description: d.description != null ? String(d.description) : cur.description,
    /* planning agents cannot be added in this version: leave the choice to the user */
    purpose: (ADDABLE_PURPOSES as readonly string[]).includes(purpose) ? purpose as AgentFields['purpose'] : cur.purpose,
    model: d.model ? String(d.model) : cur.model,
    tools: Array.isArray(d.tools) ? d.tools.map(String) : cur.tools,
    instructions: d.instructions != null ? String(d.instructions) : cur.instructions,
  };
  if (f.fields.purpose === 'exploring' || f.fields.purpose === 'reviewing') f.fields.tools = f.fields.tools.filter(t => !WRITE_TOOLS.includes(t));
  f.draftError = null; f.drafted = true; f.problems = []; f.error = null;
  if (f.role) f.open = true;                          // the define path: the filled form opens for editing
}

function onAgentSaved(c: Ctx, ev: AgentSavedEvent): void {
  const f = c.st.crewForm;
  f.saving = false;
  if (ev.ok) {
    const name = ev.name || f.fields.name;
    const role = ev.role || f.role;
    if (role) reviewOf(c, role).saved = { agent: name, casePath: ev.case_path ?? null };
    c.st.crewForm = { ...initialCrewForm() };
    c.st.crewFlash = name;
    later(c, 3000, () => run(c2 => { if (c2.st.crewFlash === name) c2.st.crewFlash = null; }), 'crewFlash');
    toast(c, `Agent ${name} saved. The planner can name it in new plans.`);
    return;
  }
  f.problems = (Array.isArray(ev.problems) ? ev.problems : []).map(problemText).filter(Boolean);
  f.error = ev.error || (f.problems.length ? 'Not saved: fix the marked fields.' : 'Not saved.');
}

function onAgentRemoved(c: Ctx, ev: AgentRemovedEvent): void {
  const name = ev.name || c.st.crewRemoving || '';
  c.st.crewRemoving = null;
  if (ev.ok) { c.st.crewError = null; toast(c, `Agent ${name} removed. A backup copy was kept.`); return; }
  c.st.crewError = ev.error || `Could not remove ${name}.`;
  toast(c, c.st.crewError);
}

/* ---------------- settings and files ---------------- */
/** The folder set as the server last reported it (ids, primary, additional); a change makes the skills list stale. */
let folderSig: string | null = null;
function onSettings(c: Ctx, ev: SettingsEvent): void {
  c.st.settings = { directories: Array.isArray(ev.directories) ? ev.directories : [], values: ev.values && typeof ev.values === 'object' ? ev.values : {}, can_pick: !!ev.can_pick_directory };
  const sig = c.st.settings.directories.map(d => `${d.dir_id}:${d.is_default ? 'p' : ''}${d.is_additional ? 'a' : ''}`).join('|');
  if (folderSig !== null && sig !== folderSig && c.st.crewDefs && !c.st.crewLoading) requestCrew(c);
  folderSig = sig;
  const adding = c.st.ui.settingsAdding;
  if (adding && c.st.settings.directories.some(d => d.path === adding)) { c.st.ui.settingsAddPath = ''; c.st.ui.settingsAdding = null; }
  if (c.st.ui.view === 'files') fxBoot(c);
}

function onFileSaved(c: Ctx, ev: FileSavedEvent): void {
  const k = fxKey(ev.root, ev.path), ed = c.st.editor;
  if (ed.open && fxKey(ed.root, ed.path) === k && !ed.saving && !ed.restoring) {
    /* saved somewhere else (another window): never adopt its version silently */
    if (!ed.dirty) { ed.waiting = true; send({ type: 'read_file', root: ev.root, path: ev.path }); ed.status = 'Updated: this file was just saved elsewhere'; }
    else ed.banner = { kind: 'notice', code: 'elsewhere', message: 'This file was just saved somewhere else. Your changes are kept; saving will ask whether to load that version or overwrite it.' };
  } else if (ed.open && fxKey(ed.root, ed.path) === k) {
    ed.version = ev.version; ed.saving = false;
    if (ed.restoring) { ed.restoring = false; ed.waiting = true; ed.status = 'Restored. Loading it…'; send({ type: 'read_file', root: ev.root, path: ev.path }); toast(c, 'Previous version restored'); }
    else {
      const ap = ev.applies || ed.applies;
      ed.text0 = ed.text; ed.dirty = false;
      toast(c, `Saved ${baseName(ev.path)}${ap === 'new_sessions' ? ' (applies to new sessions)' : ap === 'now' ? ' (applies now)' : ''}`);
      ed.open = false; ed.discardArm = false;
    }
  }
  if (c.st.fx.sel && fxKey(c.st.fx.sel.root, c.st.fx.sel.path) === k) fxSelect(c, c.st.fx.sel.root, c.st.fx.sel.path);
  /* a saved agent definition or promotion criteria: refresh the Crew tab */
  const crewHit = (c.st.crewDefs || []).some(a => (a.root === ev.root && a.path === ev.path) || (a.promotion && a.promotion.root === ev.root && (a.promotion.path || a.promotion.criteria_path) === ev.path));
  if (crewHit || /\.claude\/agents\//.test(ev.path)) requestCrew(c);
  const parent = String(ev.path).split('/').slice(0, -1).join('/');
  if (c.st.fx.cache[fxKey(ev.root, parent)]) fxLoad(c, ev.root, parent, true);
}

function onFileError(c: Ctx, ev: FileErrorEvent): void {
  const k = fxKey(ev.root, ev.path), ed = c.st.editor, fx = c.st.fx;
  if (ed.open && fxKey(ed.root, ed.path) === k && (ed.saving || ed.waiting || ed.restoring)) { edError(c, ev); return; }
  if (fx.loading[k] || (fx.open.includes(k) && !fx.cache[k])) { delete fx.loading[k]; fx.err[k] = ev.message || ev.code; return; }
  if (fx.sel && fxKey(fx.sel.root, fx.sel.path) === k) { c.st.files[k] = { error: `${ev.message || ev.code}` }; return; }
  toast(c, ev.message || `File error: ${ev.code}`);
}

export type { Session };
