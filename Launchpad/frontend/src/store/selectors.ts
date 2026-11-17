/* Derived values, ported from the vanilla page. Pure functions of the state: call them with the state you got from
   useLaunchpad() (or getState()). They also work on immer drafts inside the reducer. */
import type { AppState, Agent, ChatItem, PlannerEntry, QueueItem, Session, VisualSet } from './types';
import type { AgentFields, AgentProblem, CrewAgentDef, GitRepo, McpServer, Purpose, RoleDecision, RoleEntry } from '../contract';
import { baseName, cleanName, modelName, tparts, type TokParts } from '../lib/format';
import { PURPOSES, WRITE_TOOLS } from '../lib/labels';

type S = AppState;

/* ---------- sessions ---------- */
export const allSessions = (st: S): Session[] => st.order.map(id => st.sessions[id]).filter(Boolean);
export const curSess = (st: S): Session | null => (st.current != null && st.sessions[st.current]) || null;
/** Display name of a session (a newer draft's title wins while its run shows the older plan). */
export const sName = (s: Session): string =>
  (s.run && s.draft && s.draft.title && s.runDraftV !== s.draftV ? s.draft.title : '') || (s.run && s.run.name) || (s.draft && s.draft.title) || s.planTitle || 'New plan';
export const sLabel = (s: Session): string => (s.run ? 'Run ' : 'Session ') + s.letter;
export const isFinished = (s: Session): boolean => ['done', 'stopped', 'failed', 'blocked'].includes(s.status);
export const inFlight = (st: S): Session[] => allSessions(st).filter(s => s.status === 'running');
export const agentsOf = (st: S, sid: string | null | undefined): Agent[] => Object.values(st.agents).filter(a => a.session_id === sid);
export const sStatus = (st: S, s: Session): string => s.status === 'running' && waitingCount(st, s.id) ? 'waiting' : s.status;
export const hasChat = (s: Session): boolean => s.log.some(e => e.kind === 'bubble');
export const currentStep = (s: Session) => {
  const st = (s.run && s.run.steps) || [];
  return st.find(x => x.status === 'in_progress' || x.status === 'blocked') || st.find(x => x.status === 'todo') || st[st.length - 1] || null;
};
export const stepsDone = (s: Session): number => ((s.run && s.run.steps) || []).filter(x => x.status === 'done').length;

/** Session totals are the server's (usage scope session; which roles count is decided there, app/costs.py): shown, never summed here.
    Session total = Orchestrator + step agents + Explorers + Visualizer; the planner's share is separate. */
export const sessionTotal = (st: S, sid: string): number => st.sessions[sid]?.total ?? 0;
export const plannerCostOf = (st: S, sid: string): number => st.sessions[sid]?.plannerCost ?? 0;
/** How many agents the session total covers, and their token parts (the server's). */
export const crewCountOf = (st: S, sid: string): number => st.sessions[sid]?.crewAgents ?? 0;
export const crewTokensOf = (st: S, sid: string): TokParts => st.sessions[sid]?.crewTok ?? { i: 0, o: 0, cr: 0, cw: 0 };
/** One step's builders' totals (the server's); null = no builder on that step yet. */
export const stepTotalsOf = (st: S, sid: string, n: number | string) => st.sessions[sid]?.stepTotals?.[String(n)] ?? null;
export const curPlanner = (st: S): Agent | null => { const s = curSess(st); return s && s.plannerId ? st.agents[s.plannerId] || null : null; };
export const curPlannerStatus = (st: S): string => (curSess(st) || { plannerStatus: 'idle' }).plannerStatus || 'idle';

/* ---------- drafts ---------- */
/** The current draft already ran (by revision when the server sends them, else by the page's own count). */
export const draftLaunched = (s: Session): boolean =>
  !!s.draft && (s.draftRev != null && s.runRev != null ? s.runRev >= s.draftRev : s.runDraftV === s.draftV);
export const canApprove = (s: Session): boolean => !!s.draft && !draftLaunched(s) && s.status !== 'running' && !s.approving;

/** How to show one plan card entry: open (live), approved or superseded, plus the live button/status text. */
export function planCardView(s: Session, e: Extract<PlannerEntry, { kind: 'plancard' }>) {
  const live = e.state === 'open' && e.draftV === s.draftV;
  const approved = e.state === 'approved' || (live && draftLaunched(s));
  const superseded = !approved && (e.state === 'superseded' || e.draftV !== s.draftV);
  const running = s.status === 'running';
  let status = '';
  if (approved) status = `Approved. Run ${s.letter} launched.`;
  else if (superseded) status = 'Superseded by a newer draft.';
  else if (running) status = `Run ${s.letter} is still going; this plan can be launched when it ends.`;
  else if (s.run) status = `Approving starts a new run in ${sLabel(s)}. The earlier run's results and costs stay.`;
  return {
    approved, superseded, live: !approved && !superseded,
    approveDisabled: s.approving || running,
    approveLabel: s.approving ? 'Launching…' : running ? 'Run in progress' : 'Approve and launch',
    status,
    /** autopilot switch shows before launch; after launch only a tag when it is on */
    showApSwitch: !approved && !superseded,
    apTag: approved && s.autopilot,
  };
}

/* ---------- Incoming ---------- */
export const qOpen = (i: QueueItem): boolean => i.ui === 'open' && (i.kind === 'question' || i.kind === 'permission');
export const waitingCount = (st: S, sid: string): number => st.queue.filter(i => qOpen(i) && i.session_id === sid).length;
export const openCount = (st: S): number => st.queue.filter(qOpen).length;
export const anyBlocking = (st: S): boolean => st.queue.some(i => qOpen(i) && !!i.blocking);
/** Is this agent waiting on the user? Matched by queue_item.agent_id; name only as a fallback. */
export const agentWaiting = (st: S, a: Agent | null | undefined): boolean => !!a && st.queue.some(i => qOpen(i) && i.session_id === a.session_id &&
  (i.agent_id != null ? i.agent_id === a.agent_id : cleanName(i.agent) === cleanName(a.name)));
/** Incoming order: open cards that need the user (blocking first), then other open cards, then settled ones. */
const qRank = (i: QueueItem): number => i.ui !== 'open' ? 3 : qOpen(i) ? (i.blocking ? 0 : 1) : 2;
export const orderedQueue = (st: S): QueueItem[] => st.queue.map((i, k) => [i, k] as const).sort((x, y) => qRank(x[0]) - qRank(y[0]) || x[1] - y[1]).map(x => x[0]);
export const hasTimer = (i: QueueItem): boolean => ((i.kind === 'question' && !i.blocking) || i.kind === 'permission') && !!(i.expires_at || i.timeout_s);
export function deadline(i: QueueItem): number { const t = Date.parse(i.expires_at || ''); return isNaN(t) ? (i.timeout_s ? i.at + i.timeout_s * 1000 : NaN) : t; }
export const queueVisible = (st: S, i: QueueItem): boolean => st.ui.queueFilter === 'all' || i.kind === st.ui.queueFilter;

/* ---------- orbit / missions ---------- */
export const moonsOf = (st: S, sid: string): Agent[] => agentsOf(st, sid).filter(a => (a.role === 'builder' || a.role === 'astronaut') && a.status !== 'done');
/** Satellites of the sun: working visual agents, and astronauts not on a running run. */
export const sunSats = (st: S): Agent[] => Object.values(st.agents).filter(a => a.status === 'working' && (a.role === 'visual' ||
  (a.role === 'astronaut' && !(a.session_id != null && st.sessions[a.session_id]?.status === 'running'))));
export const workingCount = (st: S): number => Object.values(st.agents).filter(a => a.status === 'working').length;
/** Missions systems: runs in flight first, then finished runs not moved to Landed. */
export function visibleSystems(st: S): Session[] {
  return allSessions(st).filter(s => s.run && (s.status === 'running' || (isFinished(s) && !s.cleared)))
    .sort((a, b) => (a.status === 'running' ? 0 : 1) - (b.status === 'running' ? 0 : 1) || st.order.indexOf(a.id) - st.order.indexOf(b.id));
}
export const onThePad = (st: S): Session[] => allSessions(st).filter(s => s.status === 'planning' || (isFinished(s) && s.cleared && !!s.draft && !draftLaunched(s)));
export const landed = (st: S): Session[] => allSessions(st).filter(s => isFinished(s) && s.cleared);
export function nowLine(st: S, s: Session): string {
  const steps = s.run ? s.run.steps : [];
  if (isFinished(s)) return `${({ done: 'Done', stopped: 'Stopped', failed: 'Failed', blocked: 'Ended blocked' } as Record<string, string>)[s.status]} · ${stepsDone(s)} of ${steps.length} steps done`;
  const cur = currentStep(s), wait = waitingCount(st, s.id);
  const w = agentsOf(st, s.id).filter(a => a.status === 'working' && (a.role === 'builder' || a.role === 'astronaut')).map(a => a.name);
  return [wait ? `Needs you (${wait} in Incoming)` : '', cur ? `Step ${cur.n}/${steps.length} · ${cur.title}` : 'Starting', w.join(', ')].filter(Boolean).join(' · ');
}
export const orchestratorOf = (st: S, sid: string): Agent | null => {
  const orchs = agentsOf(st, sid).filter(a => a.role === 'orchestrator');
  return orchs.find(a => a.status !== 'done') || orchs[orchs.length - 1] || null;
};

/* ---------- usage ---------- */
/** Whole app, as the server's usage event (scope app) sent it. */
export function appTotals(st: S): { cost: number; parts: TokParts } {
  const u = st.usageEv || {};
  const parts = u.input_tokens != null ? tparts(u) : { i: +st.tokens || 0, o: 0, cr: 0, cw: 0 };
  return { cost: st.cost, parts };
}

/* ---------- CLI chats ---------- */
export const curChat = (st: S) => (st.currentChat != null && st.chats[st.currentChat]) || null;
/** The current CLI chat's totals, as the server's usage event (scope chat) sent them. */
export function chatUsage(st: S) {
  const c = curChat(st); if (!c) return null;
  const t = st.chatTotals[c.id];
  return { cost: t?.cost ?? 0, tok: t ? t.i + t.o + t.cr + t.cw : 0, tools: t?.tools ?? 0, n: t?.n ?? 0, in: t?.i ?? 0, out: t?.o ?? 0, cr: t?.cr ?? 0, cw: t?.cw ?? 0 };
}
export function codeAgentName(st: S): string {
  const d = (st.crewDefs || []).find(a => a.role === 'pilot');
  if (d) return d.display_name || d.name;
  const p = Object.values(st.agents).find(a => a.role === 'pilot');
  return (p && cleanName(p.name)) || 'CLI';
}
const openChatItems = (st: S): ChatItem[] => Object.values(st.chatItems).filter(i => i.ui === 'open');

/* ---------- chat screen switch: what each side has waiting on the user ---------- */
/** Planner side: open question rounds in the current session (or before any) plus a plan draft ready to approve. */
export function plannerWaiting(st: S): number {
  const s = curSess(st), log = s ? s.log : st.preLog;
  let n = 0;
  for (const e of log) if (e.kind === 'round') { const r = st.rounds[e.roundId]; if (r && !r.sent && !r.actionsHidden) n++; }
  if (s && canApprove(s) && s.status !== 'running') n++;
  return n;
}
/** CLI side: open permission / plan / question cards in any chat. */
export const codeWaiting = (st: S): number => openChatItems(st).length;
export const plannerBusy = (st: S): boolean => { const s = curSess(st); return s ? s.typing : st.preTyping; };
export const codeBusy = (st: S): boolean => Object.values(st.chats).some(c => c.busy);

/* ---------- Crew ---------- */
/** The model line of a crew card: the CLI chat's card shows the CLI and model actually chosen (cli_choice, e.g. "Claude · Sonnet"),
    every other agent its own file's model. */
export function crewModel(st: S, a: CrewAgentDef): string {
  if (a.role === 'pilot') {
    const c = curChat(st);
    if (c && c.started && c.label) return `This chat: ${c.label}`;            // the running chat's own choice
    if (st.cliChoice?.choice?.label) return `New chats: ${st.cliChoice.choice.label}`;   // saved choice, not a running chat's
  }
  return modelName(a.model);
}
const PURPOSE_SET = new Set<string>(PURPOSES);
const ROLE_PURPOSE: Record<string, Purpose> = { planner: 'planning', visual: 'planning', astronaut: 'exploring', orchestrator: 'building', builder: 'building', pilot: 'building' };
/** An agent's purpose: its own field when valid, else by role for built-ins; a folder agent with a missing or unknown one is Other. */
export function purposeOf(a: CrewAgentDef | null | undefined): Purpose {
  if (!a) return 'building';
  if (a.purpose && PURPOSE_SET.has(a.purpose)) return a.purpose as Purpose;
  return (a.builtin !== false && ROLE_PURPOSE[String(a.role || '')]) || 'other';
}
/** Built-in = one of Launchpad's own agents (crew_list.builtin; older servers: everything listed was built in). */
export const isBuiltin = (a: CrewAgentDef): boolean => a.builtin !== false;
export const usesOf = (st: S, a: CrewAgentDef): number => st.crewUses[a.name] ?? (typeof a.uses === 'number' ? a.uses : 0);
/** The folder new agents go into: crew_list.dir_id, else the default connected folder. */
export const crewDir = (st: S): string | null => st.crewDirId ?? defaultDirId(st);
/** The agent shown on a plan step when it is not the Builder (null = the Builder). */
export interface StepAgentView { name: string; label: string; purpose: Purpose; fallback: boolean }
/** agent_fallback: the named agent is missing / broken / not a step worker here, so the Builder runs the step. */
/** The step's own agent_purpose decides the colour; without it, `defs` (pass sel.defsForSession: only the crew list of
    the session's own folder) is the fallback; unknown = building. */
export function stepAgent(defs: CrewAgentDef[] | null, step: { agent?: string | null; agent_display?: string | null; agent_fallback?: boolean; agent_purpose?: string | null }): StepAgentView | null {
  const name = String(step.agent || '').trim();
  if (step.agent_fallback) return { name, label: step.agent_display || 'Builder', purpose: 'building', fallback: true };
  if (!name || name === 'launchpad-builder') return null;
  const d = (defs || []).find(a => a.name === name) || null;
  if (d && d.role === 'builder' && isBuiltin(d)) return null;
  const own = step.agent_purpose && PURPOSE_SET.has(step.agent_purpose) ? step.agent_purpose as Purpose : null;
  return { name, label: step.agent_display || (d && (d.display_name || d.name)) || name, purpose: own || (d ? purposeOf(d) : 'building'), fallback: false };
}
/** The crew list only when it lists the session's own folder (Crew may be showing another folder). */
export const defsForSession = (st: S, s: Session | null | undefined): CrewAgentDef[] | null =>
  s && st.crewDefs && (st.crewDirId == null || s.dirId == null || st.crewDirId === s.dirId) ? st.crewDefs : null;
const FORM_FIELDS = ['name', 'description', 'purpose', 'model', 'tools', 'instructions'] as const;
export type FormField = (typeof FORM_FIELDS)[number];
/** Which form field a server problem is about ("name: ...", "front matter: 'description' missing", {field}), or null. */
export function problemField(p: string): FormField | null {
  const t = p.toLowerCase();
  const lead = t.match(/^\s*(name|description|purpose|model|tools?|instructions|prompt|body)\s*:/);
  const word = lead ? lead[1] : (t.match(/'(name|description|purpose|model|tools)'/) || [])[1];
  if (!word) return null;
  if (word === 'tool') return 'tools';
  if (word === 'prompt' || word === 'body') return 'instructions';
  return word as FormField;
}
/** The page's own checks on the Add an agent form (the server runs the agent-file check on top). */
export function agentFormProblems(st: S, f: AgentFields): { field: FormField; message: string }[] {
  const out: { field: FormField; message: string }[] = [];
  const name = f.name.trim();
  if (!name) out.push({ field: 'name', message: 'Give the agent a name.' });
  else if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) out.push({ field: 'name', message: 'Use lowercase letters, digits and dashes only (for example sql-reviewer).' });
  else if (name.length > 64) out.push({ field: 'name', message: 'Keep the name under 64 characters.' });
  else if ((st.crewDefs || []).some(a => a.name === name)) out.push({ field: 'name', message: `An agent called ${name} already exists. Pick another name.` });
  if (!f.description.trim()) out.push({ field: 'description', message: 'Say in a sentence what it does; the planner reads this to pick it for a step.' });
  if (!f.purpose) out.push({ field: 'purpose', message: 'Pick what it is for.' });
  else if ((f.purpose === 'exploring' || f.purpose === 'reviewing') && f.tools.some(t => WRITE_TOOLS.includes(t))) out.push({ field: 'tools', message: 'Read-only agents cannot have write, edit or shell tools.' });
  if (!f.instructions.trim()) out.push({ field: 'instructions', message: 'Write how it should work: this becomes its prompt.' });
  return out;
}
/** A problem as one line of text (objects from the server become "field: message"). */
export function problemText(p: AgentProblem): string {
  if (typeof p === 'string') return p;
  if (!p || typeof p !== 'object') return String(p ?? '');
  const msg = p.message ?? p.text ?? '';
  return p.field ? `${p.field}: ${msg}` : msg;
}

/* ---------- model pickers (under the planner's and the CLI chat's boxes; components/ModelPicker.tsx) ---------- */
export interface PickerItem {
  id: string;
  /** the model's own name in the list ("Sonnet"); full = "Claude · Sonnet" */
  label: string; full: string; harness: string; model: string; available: boolean;
  /** what the current plan / chat runs on now */
  current: boolean;
  /** what the next new plan / chat starts on, when that differs from what this one started on */
  next: boolean;
  /** one short line under the label ("not available yet", "promote this plan · costs more", "from your next new plan") */
  hint: string;
  disabled: boolean;
}
/** One entry of the "CLI" dropdown (a harness). Unavailable ones are listed with the server's note and cannot be picked. */
export interface PickerHarness { harness: string; label: string; available: boolean; note: string; disabled: boolean; first: string | null }
/** The server's flat options grouped by harness, in the server's order; first = the id of that CLI's first model. */
export function pickerHarnesses(options: { id: string; harness: string; harness_label: string; available: boolean; note: string | null }[], locked = false): PickerHarness[] {
  const out: PickerHarness[] = [];
  for (const o of options) {
    let h = out.find(x => x.harness === o.harness);
    if (!h) out.push(h = { harness: o.harness, label: o.harness_label || o.harness, available: false, note: '', disabled: true, first: o.id });
    if (o.available) h.available = true;
    else if (!h.note) h.note = o.note || 'not available yet';
  }
  for (const h of out) { if (h.available) h.note = ''; h.disabled = !h.available || locked; }
  return out;
}
/** The picker from planner_choice + the current session's planner_model. Everything it says comes from the server:
    the options and their availability, what the session can switch to now (switchable_to), what the next plan starts on. */
export function plannerPickerView(st: S) {
  const pc = st.plannerChoice; if (!pc) return null;
  const s = curSess(st);
  const started = !!(s && s.plannerStarted);
  const current = (s && s.plannerOption) || pc.choice.option_id;
  const startOpt = s && s.plannerHarness && s.plannerStart ? `${s.plannerHarness}:${s.plannerStart}` : null;
  /* a choice the running plan could not take: remembered for the next new plan */
  const pending = started && startOpt != null && pc.choice.option_id !== startOpt ? pc.choice : null;
  const label = (s && s.plannerLabel) || pc.choice.label;
  const items: PickerItem[] = pc.options.map(o => {
    const isCurrent = o.id === current;
    const nowOk = !started || (!!s && s.switchableTo.includes(o.id));
    let hint = '';
    if (!o.available) hint = o.note || 'not available yet';
    else if (isCurrent) hint = s && s.promoted ? 'promoted' : '';
    else if (started && nowOk) hint = 'promote this plan · costs more';
    else if (started) hint = 'from your next new plan';
    const next = !!pending && pending.option_id === o.id && !isCurrent;
    if (next) hint = 'your next new plan starts here';
    return { id: o.id, label: o.model_label || modelName(o.model), full: o.label, harness: o.harness, model: o.model, available: o.available, current: isCurrent,
      next, hint, disabled: !o.available || !!pc.pinned };
  });
  const note = pc.pinned ? `The planner model is pinned to ${modelName(pc.pinned)} for this launch.`
    : pending ? `${pending.label} applies to your next new plan; this plan keeps ${label}.` : '';
  const curItem = items.find(i => i.current);
  return {
    label, items, note, pending, started,
    harnesses: pickerHarnesses(pc.options, !!pc.pinned),
    /** the CLI the dropdown shows when the menu opens: the one the current plan runs on */
    harness: curItem ? curItem.harness : (s && s.plannerHarness) || pc.choice.harness,
    nextLabel: 'next plan',
    promoted: !!(s && s.promoted),
    choosing: st.ui.pickerChoosing,
    auto: pc.auto_promote,
    topLabel: pc.top_label || modelName(pc.top_model),
    /** start = top for new plans: nothing to promote to */
    promotionOff: pc.promotion_off,
    rules: pc.rules,
    title: s && s.promoted ? `Promoted ${s.promoBy === 'user' ? 'by you' : 'by its criteria'}${s.promoReason ? ': ' + s.promoReason : ''}` : 'CLI and model for the planner',
  };
}

/** The CLI chat's picker from cli_choice + the open chat (chat_started / chat_model). A chat nobody has written to takes
    a choice at once; a chat in progress keeps its CLI and model, and a choice is for the next new chat (noted). With no
    chat open, the choice is what the next chat starts on. */
export function cliPickerView(st: S) {
  const cc = st.cliChoice; if (!cc) return null;
  const c = curChat(st);
  const written = !!(c && (c.written || c.log.some(e => e.kind === 'bubble' && e.who === 'me')));
  const own = c ? c.optionId || (c.harness && c.model ? `${c.harness}:${c.model}` : null) : null;
  const current = own || cc.choice.option_id;
  const pending = written && own != null && cc.choice.option_id !== own ? cc.choice : null;
  const label = (c && c.label) || cc.choice.label;
  const items: PickerItem[] = cc.options.map(o => {
    const isCurrent = o.id === current;
    let hint = '';
    if (!o.available) hint = o.note || 'not available yet';
    else if (written && !isCurrent) hint = 'from your next new chat';
    const next = !!pending && pending.option_id === o.id && !isCurrent;
    if (next) hint = 'your next new chat starts here';
    return { id: o.id, label: o.model_label || modelName(o.model), full: o.label, harness: o.harness, model: o.model, available: o.available,
      current: isCurrent, next, hint, disabled: !o.available };
  });
  const curItem = items.find(i => i.current);
  return {
    label, items, pending, started: written,
    note: pending ? `${pending.label} applies to your next new chat; this chat keeps ${label}.` : '',
    harnesses: pickerHarnesses(cc.options),
    harness: curItem ? curItem.harness : (c && c.harness) || cc.choice.harness,
    nextLabel: 'next chat',
    choosing: st.ui.cliChoosing,
    title: written ? 'CLI and model of this chat (fixed after its first message)' : 'CLI and model for the CLI chat',
  };
}
/** What both pickers have in common (the props of components/ModelPicker.tsx). */
export type ModelPickerView = Pick<NonNullable<ReturnType<typeof cliPickerView>>, 'label' | 'items' | 'note' | 'harnesses' | 'harness' | 'nextLabel' | 'choosing' | 'title'>;

/* ---------- visuals ---------- */
export function curVisSet(st: S): VisualSet | null {
  const s = curSess(st); if (!s || !s.visualSets.length) return null;
  return s.visualSets[Math.min(s.visSel ?? 0, s.visualSets.length - 1)];
}
/** The panel shows on the chat screen's Planner side when opened and the current session has a set. */
export const visShown = (st: S): boolean => st.ui.vis.open && !!curVisSet(st) && st.ui.view === 'plan' && st.ui.chatSide === 'planner';

/* ---------- activity feed ---------- */
const runKey = (a: { chat_id?: string | null; session_id?: string | null }): string => a.chat_id != null ? 'chat:' + a.chat_id : a.session_id ?? '_none';
export const feedVisible = (st: S, a: { chat_id?: string | null; session_id?: string | null; agent_id: string }): boolean =>
  (!st.ui.feedRun || runKey(a) === st.ui.feedRun) && (!st.ui.feedAgent || a.agent_id === st.ui.feedAgent);
export function feedRunOptions(st: S): { value: string; label: string }[] {
  const runs = [...new Set(st.acts.map(runKey))];
  return runs.map(id => {
    if (id === '_none') return { value: id, label: 'No run' };
    if (id.startsWith('chat:')) return { value: id, label: 'CLI chat' };
    const s = st.sessions[id];
    return { value: id, label: s ? `${sLabel(s)} · ${sName(s)}` : id };
  });
}
export function feedAgentOptions(st: S): { value: string; label: string }[] {
  const agents = new Map<string, (typeof st.acts)[number]>();
  st.acts.forEach(a => { if (!st.ui.feedRun || runKey(a) === st.ui.feedRun) agents.set(a.agent_id, a); });
  return [...agents.values()].map(a => {
    const s = a.session_id != null ? st.sessions[a.session_id] : null;
    return { value: a.agent_id, label: `${cleanName(a.name) || a.agent_id}${a.chat_id != null ? ' · CLI' : s ? ' · ' + s.letter : ''}${a.step != null && a.role === 'builder' ? ' · step ' + a.step : ''}` };
  });
}
/** Newest first. */
export const feedRows = (st: S) => st.acts.slice().reverse();
export const lastActOf = (st: S, agentId: string) => { const id = st.lastAct[agentId]; return id ? st.acts.find(a => a.id === id) || null : null; };

/* ---------- folders, files ---------- */
export const dirsList = (st: S) => (st.settings && st.settings.directories) || [];
export const dirById = (st: S, id: string | null | undefined) => dirsList(st).find(d => d.dir_id === id) || null;
export const defaultDirId = (st: S): string | null => { const d = dirsList(st).find(x => x.is_default) || dirsList(st)[0]; return d ? d.dir_id : null; };
export const rootLabel = (st: S, root: string): string => root === 'app' ? 'Launchpad app files' : (dirById(st, root) ? dirById(st, root)!.name || baseName(dirById(st, root)!.path) : String(root));
export function dirLabelOf(st: S, dirId: string | null | undefined, cwd?: string): string { const d = dirById(st, dirId); return d ? (d.name || baseName(d.path)) : cwd ? baseName(cwd) : ''; }
export const fxKey = (root: string, path: string | null | undefined): string => `${root}|${path || ''}`;
export function fxRoots(st: S) {
  return [...dirsList(st).map(d => ({ root: d.dir_id, name: d.name || baseName(d.path), full: d.path, exists: d.exists !== false, isDefault: !!d.is_default, isAdditional: !!d.is_additional, app: false })),
    { root: 'app', name: 'Launchpad app files', full: 'agent definitions, promotion criteria', exists: true, isDefault: false, isAdditional: false, app: true }];
}

/* ---------- Repos panel ---------- */
export interface GitGroup { dirId: string; name: string; repos: GitRepo[] }
/** Repos grouped under their connected folder, in the server's order. */
export function gitGroups(st: S): GitGroup[] {
  const out: GitGroup[] = [];
  for (const r of st.git.repos) {
    let g = out.find(x => x.dirId === r.dir_id);
    if (!g) { g = { dirId: r.dir_id, name: r.folder_name, repos: [] }; out.push(g); }
    g.repos.push(r);
  }
  return out;
}
/** Paths of the repo's changed files that are ticked (all, unless the user unticked some). */
export function gitTicked(st: S, repo: GitRepo): string[] {
  const off = st.git.unticked[repo.repo_id] || [];
  return repo.files.filter(f => !off.includes(f.path)).map(f => f.path);
}
/** A card is open when the user opened it, or by default while it has changes or something to report (error, note, busy). */
export const gitIsOpen = (st: S, repo: GitRepo): boolean =>
  st.git.open[repo.repo_id] ?? (!repo.clean || !!repo.error || !!st.git.error[repo.repo_id] || !!st.git.note[repo.repo_id] || !!st.git.busy[repo.repo_id]);
/** Status chips for a repo header: "Not linked", "2 ahead", "3 behind", "Changes", "Up to date". */
export function gitChips(repo: GitRepo): { text: string; tone: 'ok' | 'warn' | 'info' | 'err' }[] {
  if (repo.error) return [{ text: 'Error', tone: 'err' }];
  const out: { text: string; tone: 'ok' | 'warn' | 'info' | 'err' }[] = [];
  if (!repo.linked) out.push({ text: 'Not linked', tone: 'warn' });
  else {
    if (repo.ahead) out.push({ text: `${repo.ahead} ahead`, tone: 'info' });
    if (repo.behind) out.push({ text: `${repo.behind} behind`, tone: 'warn' });
  }
  if (!repo.clean) out.push({ text: 'Changes', tone: 'info' });
  else if (repo.linked && !repo.ahead && !repo.behind) out.push({ text: 'Up to date', tone: 'ok' });
  return out;
}

/* ---------- undefined roles ---------- */
/** The roles the server lists under "Used but not defined" (visible), in its order (most recently used first). */
export const visibleRoles = (st: S): RoleEntry[] => st.roles.entries.filter(e => e.visible);
/** Counts of the listed uses that failed, were blocked or were sent back (small markers on a role). */
export const roleMarkers = (e: RoleEntry): { failed: number; blocked: number; sentBack: number } => ({
  failed: e.uses.filter(u => u.outcome === 'failed').length,
  blocked: e.uses.filter(u => u.outcome === 'blocked').length,
  sentBack: e.uses.filter(u => u.sent_back).length,
});
/** The Role Reviewer's question cards for a role (open and settled), in arrival order. */
export const reviewQueue = (st: S, role: string): QueueItem[] => st.queue.filter(i => i.review_id != null && i.role === role);
/** One line on when a role that rested after a decision comes back (the number is the server's resurface_uses). */
export const roleRestNote = (decision: RoleDecision, resurface: number): string =>
  decision === 'define' ? '' : `${decision === 'keep' ? 'Kept as a skill plus the Builder' : 'Not yet'}: this role leaves the list and keeps being counted. It comes back after ${resurface} more uses, or sooner if a step under it fails, is blocked or is sent back.`;
/** A path shown relative: an absolute one (a machine path) is cut to its last three parts. */
export function relPath(p: string): string {
  const raw = String(p || ''), parts = raw.replace(/\\/g, '/').split('/').filter(Boolean);
  return /^([a-z]:|[\\/])/i.test(raw) ? '…/' + parts.slice(-3).join('/') : parts.join('/');
}


/* ---------- MCP library ---------- */
/** Servers whose last test passed: the only ones the Crew picker offers. */
export const mcpConnected = (st: S): McpServer[] => st.mcp.servers.filter(x => x.status === 'connected');
/** One agent's assigned servers, each with its library entry (null = no longer in the library). */
export function mcpAssigned(st: S, agent: string): { name: string; server: McpServer | null; ok: boolean }[] {
  return (st.mcp.assignments[agent] || []).map(name => {
    const server = st.mcp.servers.find(x => x.name === name) || null;
    return { name, server, ok: !!server && server.status === 'connected' };
  });
}
/** The assigned servers of an agent that are not connected (failed, untested, testing or gone): the card warning. */
export const mcpProblems = (st: S, agent: string) => mcpAssigned(st, agent).filter(x => !x.ok && x.server?.status !== 'testing');
