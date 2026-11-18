/* The whole app state. Everything the vanilla page kept in `state`, its per-session/per-chat objects, `FX` (File
   Explorer), `Ed` (pen editor) and `Vis` (visuals panel flags) lives here as plain data.
   Not here (view-local animation only): orbit body positions, solar-system ships/trails/pings, frame elements.
   All records are keyed objects (not Map/Set) so the state stays plain JSON-like data. */
import type {
  ActivityEvent, AgentFields, AgentUsageEvent, BackupItem, ChatMode, CliChoiceEvent, CrewAgentDef, DirEntry, Directory, FileContentEvent,
  FileErrorCode, GitOp, GitRepo, Id, PermissionSuggestion, PlannerChoiceEvent, PlanStep, Question, RoleCase, RoleDecision, RoleEntry, RoundAnswer, RunUsage,
  ReviewTest, ConnectionTestEvent, McpImportCandidate, McpServer, Workflow, WorkflowRun, WorkflowsListEvent, UsageDataEvent, UsageRequest, NamedItem, SettingValue, SkillInfo, StepStatus, VisualOption,
} from '../contract';

/** Header tabs. The chat screen ('plan') holds both conversations behind the Planner / CLI switch. */
export type View = 'plan' | 'missions' | 'crew' | 'files' | 'workflows' | 'usage' | 'settings';
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
export interface RunStep { n: number; title: string; status: StepStatus; waiting_for?: 'review'; built: string[]; report_path: string; agent?: string | null; agent_display?: string | null; agent_fallback?: boolean; agent_purpose?: string | null; skills?: string[]; skills_unknown?: string[]; role?: string }
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
  /** set for a workflow run (the server's marker): labelled with the workflow, no planner actions */
  wf: { id: string; name: string; run_id: string; test: boolean } | null;
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
  /** the server's totals for this session (usage scope session, snapshot, run_finished): total = every agent but the planner;
      plannerCost = the planner's own share; crewAgents / crewTok = those agents' count and token parts. Never summed here. */
  total: number | null;
  plannerCost: number | null;
  crewAgents: number;
  crewTok: { i: number; o: number; cr: number; cw: number };
  /** step number -> its builders' totals (usage scope session steps) */
  stepTotals: Record<string, ChatTotals>;
  cleared: boolean;          // "Move to Landed" in Missions
  flash: number;             // time of the last step that turned done (orbit / system burst)
  flashN: number | null;
  created: number;
  autopilot: boolean;
  /** the Auto answers switch (server state; off by default) */
  autoAnswers: boolean;
  /* planner */
  plannerId: Id | null;
  plannerStatus: string;
  plannerModel: string | null;
  promoted: boolean;
  promoReason: string | null;
  promoBy: 'criteria' | 'user' | null;
  promoting: boolean;
  /** planner_model: harness, start / top model, "<harness> · <model>" label and option id now; started = someone wrote to it
      (harness and start model fixed); auto = it may promote itself; switchableTo = picker options it can move to now */
  plannerHarness: string | null;
  plannerStart: string | null;
  plannerTop: string | null;
  plannerLabel: string | null;
  plannerOption: string | null;
  plannerStarted: boolean;
  plannerAuto: boolean;
  switchableTo: string[];
  /* "Send plan to CLI" (chat_from_plan): waiting for its chat_started; draftV of the plan last sent */
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
/** auto = timed out and took the recommendation; decided = a plan-step worker's question settled by Auto answers (builders only) */
export type QueueUi = 'open' | 'sent' | 'timedout' | 'autopilot' | 'auto' | 'decided' | 'ended';
export interface QueueItem {
  id: Id;
  kind: 'question' | 'permission' | 'info' | 'report' | 'plan' | 'review';
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
  /** Role Reviewer questions only (no session): the review, the role under review, the test it is for */
  review_id?: string;
  role?: string;
  test?: ReviewTest | '';
  /** kind review: the workflow run waiting for sign-off, and which stage */
  workflow?: { id: string; name: string; run_id: string; test: boolean };
  run_id?: string;
  stage?: number;
  at: number;
  ui: QueueUi;
  answer?: string;
  /** fading out before removal */
  leaving?: boolean;
}

/* ---------- agents + activity ---------- */
export type Agent = Omit<AgentUsageEvent, 'type'>;
export type Activity = Omit<ActivityEvent, 'type'>;

/** One CLI chat's totals as the server sent them (usage scope chat). */
export interface ChatTotals { cost: number; tools: number; n: number; i: number; o: number; cr: number; cw: number }

/* ---------- CLI chats (the chat screen's CLI side) ---------- */
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
  /** the chat's CLI and model (chat_started / chat_model): harness id, "Claude · Sonnet", "claude:sonnet" */
  harness: string | null;
  label: string | null;
  optionId: string | null;
  /** someone wrote to it (server's started, or a message the page sent): its CLI and model are fixed */
  written: boolean;
  cwd: string;
  dirId: Id | null;
  busy: boolean;
  /** chat_started arrived */
  started: boolean;
  log: FlightEntry[];
  /** id of the bubble being streamed (chat_delta), null between replies */
  streamId: string | null;
  typing: boolean;
  agentIds: Id[];
  /** opened by "Send plan to CLI": the next user message is that plan (this is its label) */
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
  /** the tally role this agent defines (define path): agent_draft / agent_create carry it; null = a plain new agent */
  role: string | null;
  /** the drafting call's own tokens and cost (agent_drafted.usage), shown with the draft */
  cost: RunUsage | null;
}

/* ---------- Connections and the MCP library ---------- */
/** The last mcp_library (loaded = one has arrived). assignments: agent name -> server names. */
export interface McpState {
  loaded: boolean; servers: McpServer[]; assignments: Record<string, string[]>;
  connections: NamedItem[]; importSources: NamedItem[]; error: string | null;
}
/** A Test click: testing until connection_test answers, then done with the answer. */
export type ConnTest = { status: 'testing' } | { status: 'done'; result: Omit<ConnectionTestEvent, 'type' | 'id'> };
/** Workflows: the last workflows_list (folders a workflow can be saved in, the agents a stage may name per folder, the name
    typed at the last sign-off), every run seen (workflow_run_state; newest per workflow in `latest`), the last save / remove
    error, and a refusal per workflow (a refused Run, a refused review) in `runErrors`. */
export interface WorkflowsState {
  /** a run id to open on the review screen (set by an Incoming review card, taken by the Workflows view) */
  openReview: string | null;
  loaded: boolean; list: Workflow[]; folders: WorkflowsListEvent['folders']; agents: WorkflowsListEvent['agents']; reviewerName: string;
  runs: Record<string, WorkflowRun>; latest: Record<string, string>; error: string | null; runErrors: Record<string, string>;
}

/** The Usage screen: the last usage_data for the latest request (null until one arrives), how many usage_get requests are unanswered, and the latest request (`want`: a reply for another request is ignored). */
export interface UsageState { data: Omit<UsageDataEvent, 'type'> | null; pending: number; want: UsageRequest | null }

/** An import candidate list for one source: loading until mcp_imports answers. */
export type McpImportList = { loading: true } | { loading: false; servers: McpImportCandidate[] };

/* ---------- undefined roles: the list and one review per role ---------- */
export interface RolesState { loaded: boolean; threshold: number; resurface: number; entries: RoleEntry[] }
/** starting = review_start sent; running = the reviewer is reading; case = the case is in; failed / refused = a plain message, the role stays reviewable */
export type ReviewStatus = 'starting' | 'running' | 'case' | 'failed' | 'refused';
export interface RoleReview {
  role: string;
  reviewId: string | null;
  status: ReviewStatus;
  model: string;
  /** review_progress lines, oldest first (the last few) */
  progress: string[];
  phase: string;
  case: RoleCase | null;
  error: string | null;
  /** the decision sent, until review_decided */
  deciding: RoleDecision | null;
  /** review_decided: the user's decision (the role then rests, or the agent is being defined) */
  decided: { decision: RoleDecision; reviewerVerdict: RoleDecision | null } | null;
  /** define path: the agent was saved (agent_saved with this role): its name and the case's folder-relative path */
  saved: { agent: string; casePath: string | null } | null;
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
  /** the chat screen's Planner / CLI switch */
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
  /** planner picker: the option sent (planner_choose), until planner_model / planner_choice answers */
  pickerChoosing: string | null;
  /** CLI chat picker: the option sent (cli_choose), until cli_choice answers */
  cliChoosing: string | null;
  newPlanBusy: boolean;
  newChatBusy: boolean;
  vis: { open: boolean; wide: boolean; width: number };
  settingsMsg: string | null;
  settingsAdding: string | null;
  settingsAddPath: string;
  picking: boolean;
  /** who asked for the folder picker: 'output' = the workflow form (the path only fills its field), else Settings (adds a working directory) */
  pickFor: 'output' | null;
  /** the folder picked for the workflow form, waiting for the form to take it (null = none; '' = cancelled) */
  pickedOutput: string | null;
  dirMenu: { top: number; left: number; right: number; bottom: number } | null;
  toasts: Toast[];
}

/* ---------- Repos panel (right-hand panel while the Files tab is open) ---------- */
export interface GitState {
  /** git_repos.available: null until the first answer, false = git is not installed */
  available: boolean | null;
  loaded: boolean;
  /** git_scan sent, waiting for git_repos */
  scanning: boolean;
  repos: GitRepo[];
  /** repo id -> the operation in flight */
  busy: Record<string, GitOp>;
  /** repo id -> git's last error text / the last success note (cleared by the next operation) */
  error: Record<string, string>;
  note: Record<string, string>;
  /** repo id -> paths the user unticked (everything is ticked by default, also new files) */
  unticked: Record<string, string[]>;
  /** repo id -> commit message being typed; repo id -> card opened / closed by hand (default: open when it has changes) */
  message: Record<string, string>;
  open: Record<string, boolean>;
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
  /** planner_choice: the picker's options, what the next new plan starts on, auto-promote, the rules text */
  plannerChoice: Omit<PlannerChoiceEvent, 'type'> | null;
  /** cli_choice: the CLI chat picker's options and what the next new chat starts on */
  cliChoice: Omit<CliChoiceEvent, 'type'> | null;
  /* agents, usage, activity */
  agents: Record<Id, Agent>;
  tokens: number;
  cost: number;
  usageEv: { input_tokens?: number; output_tokens?: number; cache_read_tokens?: number; cache_write_tokens?: number; tokens?: number } | null;
  /** usage scope app: the cost per agent role; usage scope chat: that CLI chat's totals (the server sums, the page shows) */
  byRole: Record<string, number>;
  chatTotals: Record<Id, ChatTotals>;
  acts: Activity[];                       // oldest first, last 600
  lastAct: Record<Id, Id>;                // agent_id -> activity id
  /* Incoming */
  queue: QueueItem[];                     // arrival order
  /* CLI chats */
  chats: Record<Id, Chat>;
  chatOrder: Id[];
  currentChat: Id | null;
  chatPending: string | null;             // first message, sent once chat_started arrives
  codeModePref: ChatMode | null;          // the mode picked before a chat exists (applied to the next chat)
  chatFromPlan: Id | null;                // session whose plan was sent to the CLI; its chat_started keeps mode plan
  chatItems: Record<Id, ChatItem>;
  /* Crew */
  crewDefs: CrewAgentDef[] | null;
  crewLoading: boolean;
  crewDirId: Id | null;                   // crew_list.dir_id: whose folder agents are listed (and where new ones go)
  crewDirPick: Id | null;                 // the folder picked in Crew (get_crew {dir_id}); null = the server's default
  toolChoices: string[];                  // crew_list.tool_choices
  crewSkills: SkillInfo[];                // crew_list.skills: skills in the listed folder + the additional folders

  crewUses: Record<string, number>;       // agent name -> use count (crew_list, then live agent_uses)
  crewForm: CrewForm;
  /* undefined roles (roles_list) and their reviews; roleOpen = the role whose review screen shows in Crew */
  roles: RolesState;
  reviews: Record<string, RoleReview>;
  roleOpen: string | null;
  mcp: McpState;
  wf: WorkflowsState;
  usage: UsageState;
  connTests: Record<string, ConnTest>;
  mcpImports: Record<string, McpImportList>;
  crewRemoving: string | null;            // agent_remove sent, waiting for agent_removed
  crewError: string | null;               // the last agent_removed failure
  crewFlash: string | null;               // a card just added (highlighted for a moment)
  /* settings, files, editor */
  settings: SettingsState | null;
  fx: FxState;
  files: Record<string, FileView>;        // "root|path" -> file_content (or an error)
  editor: EditorState;
  git: GitState;
}
