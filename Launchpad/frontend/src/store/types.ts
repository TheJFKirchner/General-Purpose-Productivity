/* The whole app state. Everything the vanilla page kept in `state`, its per-session/per-chat objects, `FX` (File
   Explorer), `Ed` (pen editor) and `Vis` (visuals panel flags) lives here as plain data.
   Not here (view-local animation only): orbit body positions, solar-system ships/trails/pings, frame elements.
   All records are keyed objects (not Map/Set) so the state stays plain JSON-like data. */
import type {
  ActivityEvent, AgentFields, AgentUsageEvent, BackupItem, ChatMode, CrewAgentDef, DirEntry, Directory, FileContentEvent,
  FileErrorCode, Id, PermissionSuggestion, PlanStep, Question, RoundAnswer, SettingValue, StepStatus, VisualOption,
} from '../contract';

/** Header tabs. The chat screen ('plan') holds both conversations behind the Planner / Claude Code switch. */
export type View = 'plan' | 'missions' | 'crew' | 'files';
/** Which side of the chat screen's switch is showing. */
export type ChatSide = 'planner' | 'code';
export type SessionStatus = 'planning' | 'running' | 'done' | 'stopped' | 'failed' | 'blocked';

/* ---------- planner chat log (per session) ---------- */
export type PlanCardState = 'open' | 'approved' | 'superseded';
export interface Draft { path: string; markdown: string; steps: PlanStep[]; title: string; status: string }
export type PlannerEntry =
  | { kind: 'bubble'; id: string; who: 'me' | 'bot'; text: string }
  | { kind: 'sys'; id: string; text: string; cls?: 'promo' | 'err' }
  | { kind: 'visnote'; id: string; text: string; setId: string }
  | { kind: 'round'; id: string; roundId: string }
  /** a plan draft card; `draft` is the draft as it was when the card was made; state open = live (see selectors.planCardView) */
  | { kind: 'plancard'; id: string; draft: Draft; draftV: number; rev: number; state: PlanCardState };

export interface Round {
  id: string;
  sessionId: Id | null;
  round: number;
  questions: Question[];
  answers: Record<string, RoundAnswer>;
  /** round_answer sent (all answered, or Accept all) */
  sent: boolean;
  /** the "Accept all / Skip" row is gone (sent or skipped) */
  actionsHidden: boolean;
}

/** agent / agent_display: the agent assigned to the step (null = the Builder). */
export interface RunStep { n: number; title: string; status: StepStatus; built: string[]; report_path: string; agent?: string | null; agent_display?: string | null; agent_fallback?: boolean; agent_purpose?: string | null }
export interface Run { name: string; started: number; finished?: number; steps: RunStep[] }
export interface Report { path: string; markdown: string; total: number | null }

export interface VisualSet {
  set_id: string;
  brief: string;
  options: VisualOption[];
  picked_id: string | null;
  /** library asked for (null = not asked), used (drawn_with), available for the folder, fallback label */
  library: string | null;
  drawn_with: string;
  libraries: string[];
  library_note: string | null;
  /** option id -> 'tweak' | 'retry' while a revision the user asked for is on its way */
  pending: Record<string, 'tweak' | 'retry'>;
  /** the pick the chat already has a note for */
  notedPick: string | null;
}

export interface Session {
  id: Id;
  letter: string;
  folder: string;
  dirId: Id | null;
  cwd: string;
  planTitle: string;
  status: SessionStatus;
  meta: { name?: string; mode?: string; status?: string } | null;
  roundTag: string;
  /* drafts and runs */
  draft: Draft | null;
  draftV: number;            // page-side draft count
  draftRev: number | null;   // plan_draft.revision
  runDraftV: number | null;  // draftV the latest run launched
  runRev: number | null;     // run_started.revision
  run: Run | null;
  report: Report | null;
  approving: boolean;
  stopping: boolean;
  reportSent: boolean;
  snapReportSent: boolean;
  snapTotal: number | null;
  plannerCost: number | null;
  cleared: boolean;          // "Move to Landed" in Missions
  flash: number;             // time of the last step that turned done (orbit / system burst)
  flashN: number | null;
  created: number;
  autopilot: boolean;
  /* planner */
  plannerId: Id | null;
  plannerStatus: string;
  plannerModel: string | null;
  promoted: boolean;
  promoReason: string | null;
  promoBy: 'criteria' | 'user' | null;
  promoting: boolean;
  /* "Send plan to Claude Code" (chat_from_plan): waiting for its chat_started; draftV of the plan last sent */
  codeSending: boolean;
  codeSentV: number | null;
  /* visuals */
  visualSets: VisualSet[];
  visSel: number | null;
  visSeen: number;
  /* chat */
  log: PlannerEntry[];
  typing: boolean;
}

/* ---------- Incoming queue ---------- */
export type QueueUi = 'open' | 'sent' | 'timedout' | 'autopilot' | 'auto' | 'ended';
export interface QueueItem {
  id: Id;
  kind: 'question' | 'permission' | 'info' | 'report' | 'plan';
  session_id: Id | null;
  agent?: string;
  agent_id?: Id | null;
  step?: number | null;
  title?: string;
  body?: string;
  rec?: string | null;
  options?: string[];
  blocking?: boolean;
  timeout_s?: number | null;
  expires_at?: string | null;
  tool?: string;
  command?: string;
  at: number;
  ui: QueueUi;
  answer?: string;
  /** fading out before removal */
  leaving?: boolean;
}

/* ---------- agents + activity ---------- */
export type Agent = Omit<AgentUsageEvent, 'type'>;
export type Activity = Omit<ActivityEvent, 'type'>;

/* ---------- Claude Code chats (the chat screen's Claude Code side) ---------- */
export type FlightEntry =
  /** plan = the plan sent from the Planner (chat_from_plan), with its label: shown collapsed, not as a plain bubble */
  | { kind: 'bubble'; id: string; who: 'me' | 'bot'; text: string; streaming?: boolean; plan?: string }
  | { kind: 'sys'; id: string; text: string; cls?: 'err' }
  | { kind: 'tool'; id: string; act: Activity }
  | { kind: 'card'; id: string; itemId: Id };

export interface ChatItem {
  id: Id;
  chat_id: Id;
  kind: 'permission' | 'plan' | 'question' | 'info';
  tool?: string;
  title?: string;
  body?: string;
  markdown?: string;
  options?: string[];
  suggestions?: PermissionSuggestion[];
  agent?: string;
  agent_id?: Id | null;
  /** open | sent (answer on its way) | done (queue_resolved) */
  ui: 'open' | 'sent' | 'done';
  result?: string;
}

export interface Chat {
  id: Id;
  mode: ChatMode;
  model: string;
  cwd: string;
  dirId: Id | null;
  busy: boolean;
  started: boolean;
  log: FlightEntry[];
  /** id of the bubble being streamed (chat_delta), null between replies */
  streamId: string | null;
  typing: boolean;
  agentIds: Id[];
  /** opened by "Send plan to Claude Code": the next user message is that plan (this is its label) */
  awaitPlan?: string | null;
}

/* ---------- Crew: the "Add an agent" form ---------- */
export interface CrewForm {
  open: boolean;
  fields: AgentFields;
  /** the server's problems for the last agent_create (inline under their fields) */
  problems: string[];
  /** a whole-form error (agent_saved.error, or "not connected") */
  error: string | null;
  saving: boolean;
  /** "Draft for me": the sentence typed, waiting for agent_drafted, its error, and a note once a draft filled the form */
  draftText: string;
  drafting: boolean;
  draftError: string | null;
  drafted: boolean;
}

/* ---------- settings, files, editor ---------- */
export interface SettingsState { directories: Directory[]; values: Record<string, SettingValue>; can_pick: boolean }

export interface FxState {
  cache: Record<string, DirEntry[]>;     // "root|path" -> sorted entries
  loading: Record<string, true>;
  err: Record<string, string>;
  open: string[];                        // expanded folders ("root|path")
  sel: { root: string; path: string } | null;
  raw: boolean;
  collapsed: boolean;
  width: number;
  booted: boolean;
}
export type FileView = Omit<FileContentEvent, 'type'> | { error: string };

export type EditorPane = 'side' | 'edit' | 'preview';
export interface EditorBanner {
  kind: 'conflict' | 'invalid' | 'notice';
  /** conflict / invalid / not_allowed ...; 'elsewhere' = saved by someone else while dirty; 'viewonly' = cannot edit */
  code: FileErrorCode | 'elsewhere' | 'viewonly';
  message: string;
  /** for viewonly: the file kind when it is not markdown */
  fileKind?: string;
}
export interface EditorState {
  open: boolean;
  root: string;
  path: string;
  title: string;
  version: string | number | null;
  text: string;
  text0: string;
  dirty: boolean;
  waiting: boolean;
  saving: boolean;
  restoring: boolean;
  editable: boolean;
  applies: 'now' | 'new_sessions' | null;
  validates: 'agent' | 'plan' | null;
  discardArm: boolean;
  conflict: { text: string; version: string | number } | null;
  banner: EditorBanner | null;
  status: string;
  pane: EditorPane;
  backupsShown: boolean;
  backups: BackupItem[] | null;           // null = loading
}

/* ---------- UI flags shared by several screens ---------- */
export interface Toast { id: number; text: string }
export interface UiState {
  view: View;
  /** the chat screen's Planner / Claude Code switch */
  chatSide: ChatSide;
  conn: { text: string; color: string };
  demo: boolean;
  queueFilter: 'all' | 'permission' | 'question';
  feedRun: string;
  feedAgent: string;
  hov: Id | null;                         // agent hovered in Missions / feed
  sel: Id | null;                         // agent pinned
  focus: Id | null;                       // run focused in Missions
  focusScroll: boolean;
  stopConfirm: Id | null;                 // two-click confirms (4 s)
  apConfirm: Id | null;
  pmConfirm: Id | null;
  newPlanBusy: boolean;
  newChatBusy: boolean;
  vis: { open: boolean; wide: boolean; width: number };
  settingsOpen: boolean;
  settingsMsg: string | null;
  settingsAdding: string | null;
  settingsAddPath: string;
  picking: boolean;
  dirMenu: { top: number; left: number; right: number; bottom: number } | null;
  toasts: Toast[];
}

export interface AppState {
  seq: number;                            // id counter for log entries / toasts
  ui: UiState;
  replaying: boolean;                     // a snapshot's replay is running (history, not news)
  quiet: boolean;                         // no toasts
  /* planner sessions */
  sessions: Record<Id, Session>;
  order: Id[];                            // first-seen order (= letters)
  current: Id | null;
  preLog: PlannerEntry[];                 // chat lines before any session exists
  preTyping: boolean;
  preName: string;                        // plan_meta name before any session (header text, as the vanilla page)
  preRoundTag: string;                    // "Round N" from a question round before any session
  rounds: Record<string, Round>;
  /* agents, usage, activity */
  agents: Record<Id, Agent>;
  tokens: number;
  cost: number;
  usageEv: { input_tokens?: number; output_tokens?: number; cache_read_tokens?: number; cache_write_tokens?: number; tokens?: number } | null;
  usageFromServer: boolean;
  acts: Activity[];                       // oldest first, last 600
  lastAct: Record<Id, Id>;                // agent_id -> activity id
  /* Incoming */
  queue: QueueItem[];                     // arrival order
  /* Claude Code chats */
  chats: Record<Id, Chat>;
  chatOrder: Id[];
  currentChat: Id | null;
  chatPending: string | null;             // first message, sent once chat_started arrives
  codeModePref: ChatMode | null;          // the mode picked before a chat exists (applied to the next chat)
  chatFromPlan: Id | null;                // session whose plan was sent to Claude Code; its chat_started keeps mode plan
  chatItems: Record<Id, ChatItem>;
  /* Crew */
  crewDefs: CrewAgentDef[] | null;
  crewLoading: boolean;
  crewDirId: Id | null;                   // crew_list.dir_id: whose folder agents are listed (and where new ones go)
  crewDirPick: Id | null;                 // the folder picked in Crew (get_crew {dir_id}); null = the server's default
  toolChoices: string[];                  // crew_list.tool_choices
  crewUses: Record<string, number>;       // agent name -> use count (crew_list, then live agent_uses)
  crewForm: CrewForm;
  crewRemoving: string | null;            // agent_remove sent, waiting for agent_removed
  crewError: string | null;               // the last agent_removed failure
  crewFlash: string | null;               // a card just added (highlighted for a moment)
  /* settings, files, editor */
  settings: SettingsState | null;
  fx: FxState;
  files: Record<string, FileView>;        // "root|path" -> file_content (or an error)
  editor: EditorState;
}
