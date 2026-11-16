/* Derived values, ported from the vanilla page. Pure functions of the state: call them with the state you got from
   useLaunchpad() (or getState()). They also work on immer drafts inside the reducer. */
import type { AppState, Agent, ChatItem, PlannerEntry, QueueItem, Session, VisualSet } from './types';
import type { AgentFields, AgentProblem, CrewAgentDef, Purpose } from '../contract';
import { baseName, cleanName, modelName, tok, tparts, tsum, type TokParts } from '../lib/format';
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

/** One definition everywhere: session total = Orchestrator + step agents + Explorers + Visualizer. The planner is separate.
    (Role ids stay as they were: astronaut = Explorer, visual = Visualizer, pilot = Claude Code.) */
const RUN_ROLES = ['orchestrator', 'builder', 'astronaut', 'visual'];
export const crewOf = (st: S, sid: string): Agent[] => agentsOf(st, sid).filter(a => RUN_ROLES.includes(a.role));
export function sessionTotal(st: S, sid: string): number {
  const ag = crewOf(st, sid), s = st.sessions[sid];
  if (!ag.length && s && typeof s.snapTotal === 'number') return s.snapTotal;
  if (!ag.length && s && s.report && typeof s.report.total === 'number') return s.report.total;
  return ag.reduce((t, a) => t + (+a.cost_usd || 0), 0);
}
export function plannerCostOf(st: S, sid: string): number {
  const ps = agentsOf(st, sid).filter(a => a.role === 'planner');
  if (ps.length) return ps.reduce((t, a) => t + (+a.cost_usd || 0), 0);
  const s = st.sessions[sid]; return s && typeof s.plannerCost === 'number' ? s.plannerCost : 0;
}
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
/** Whole app: sum of agent_usage when any arrived; else the server's usage event. */
export function appTotals(st: S): { cost: number; parts: TokParts; from: 'agents' | 'usage' } {
  const all = Object.values(st.agents);
  if (all.length) return { cost: all.reduce((t, a) => t + (+a.cost_usd || 0), 0), parts: tsum(all), from: 'agents' };
  const u = st.usageEv || {};
  const parts = u.input_tokens != null ? tparts(u) : { i: +st.tokens || 0, o: 0, cr: 0, cw: 0 };
  return { cost: st.cost, parts, from: 'usage' };
}

/* ---------- Claude Code chats ---------- */
export const curChat = (st: S) => (st.currentChat != null && st.chats[st.currentChat]) || null;
export function chatUsage(st: S) {
  const c = curChat(st); if (!c) return null;
  const ag = Object.values(st.agents).filter(a => a.chat_id === c.id || c.agentIds.includes(a.agent_id));
  return ag.reduce((t, a) => ({ cost: t.cost + (+a.cost_usd || 0), tok: t.tok + tok(a), tools: t.tools + (+a.tool_calls || 0), n: t.n + 1,
    in: t.in + (+(a.input_tokens ?? 0) || 0), out: t.out + (+(a.output_tokens ?? 0) || 0), cr: t.cr + (+(a.cache_read_tokens ?? 0) || 0), cw: t.cw + (+(a.cache_write_tokens ?? 0) || 0) }),
    { cost: 0, tok: 0, tools: 0, n: 0, in: 0, out: 0, cr: 0, cw: 0 });
}
export function codeAgentName(st: S): string {
  const d = (st.crewDefs || []).find(a => a.role === 'pilot');
  if (d) return d.display_name || d.name;
  const p = Object.values(st.agents).find(a => a.role === 'pilot');
  return (p && cleanName(p.name)) || 'Claude Code';
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
/** Claude Code side: open permission / plan / question cards in any chat. */
export const codeWaiting = (st: S): number => openChatItems(st).length;
export const plannerBusy = (st: S): boolean => { const s = curSess(st); return s ? s.typing : st.preTyping; };
export const codeBusy = (st: S): boolean => Object.values(st.chats).some(c => c.busy);

/* ---------- Crew ---------- */
const PURPOSE_SET = new Set<string>(PURPOSES);
const ROLE_PURPOSE: Record<string, Purpose> = { planner: 'planning', visual: 'planning', astronaut: 'exploring', orchestrator: 'building', builder: 'building', pilot: 'building' };
/** An agent's purpose: its own field when valid, else by role for built-ins; a folder agent with none counts as building. */
export function purposeOf(a: CrewAgentDef | null | undefined): Purpose {
  if (!a) return 'building';
  if (a.purpose && PURPOSE_SET.has(a.purpose)) return a.purpose as Purpose;
  return (a.builtin !== false && ROLE_PURPOSE[String(a.role || '')]) || 'building';
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

/* ---------- planner model ---------- */
const promoConf = (st: S) => ((st.crewDefs || []).find(a => a.role === 'planner') || {} as { promotion?: undefined }).promotion || null;
/** Plan header model chip + Promote button (hidden once promoted or when start = target). */
export function plannerModelView(st: S) {
  const s = curSess(st);
  if (!s || !s.plannerModel) return null;
  const conf = promoConf(st), target = (conf && conf.target_model) || 'opus';
  const hide = s.promoted || (!!conf && modelName(conf.start_model) === modelName(conf.target_model)) || modelName(s.plannerModel) === modelName(target);
  const confirm = st.ui.pmConfirm === s.id;
  return {
    session: s,
    chip: `${modelName(s.plannerModel)}${s.promoted ? ' · promoted' : ''}`,
    chipTitle: s.promoted ? `Promoted ${s.promoBy === 'user' ? 'by you' : 'by its criteria'}${s.promoReason ? ': ' + s.promoReason : ''}` : "The model this session's planner is using",
    showPromote: !hide,
    confirm,
    promoteLabel: s.promoting ? 'Promoting…' : confirm ? `Confirm: switch to ${modelName(target)} (costs more)` : `Promote to ${modelName(target)}`,
    promoteTitle: `Move this session's planner to ${modelName(target)} for the rest of the session. It costs more per turn.`,
    target,
  };
}

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
    if (id.startsWith('chat:')) return { value: id, label: 'Claude Code chat' };
    const s = st.sessions[id];
    return { value: id, label: s ? `${sLabel(s)} · ${sName(s)}` : id };
  });
}
export function feedAgentOptions(st: S): { value: string; label: string }[] {
  const agents = new Map<string, (typeof st.acts)[number]>();
  st.acts.forEach(a => { if (!st.ui.feedRun || runKey(a) === st.ui.feedRun) agents.set(a.agent_id, a); });
  return [...agents.values()].map(a => {
    const s = a.session_id != null ? st.sessions[a.session_id] : null;
    return { value: a.agent_id, label: `${cleanName(a.name) || a.agent_id}${a.chat_id != null ? ' · Claude Code' : s ? ' · ' + s.letter : ''}${a.step != null && a.role === 'builder' ? ' · step ' + a.step : ''}` };
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
  return [...dirsList(st).map(d => ({ root: d.dir_id, name: d.name || baseName(d.path), full: d.path, exists: d.exists !== false, isDefault: !!d.is_default, app: false })),
    { root: 'app', name: 'Launchpad app files', full: 'agent definitions, promotion criteria', exists: true, isDefault: false, app: true }];
}
