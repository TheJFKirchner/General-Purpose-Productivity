/* Websocket contract, typed. Source of truth: the header of app/server.py (do not change it here first).
   Server -> UI events are `ServerEvent`; UI -> server messages are `UiMessage`.
   Fields the vanilla page tolerated as optional (older servers, demo, history replays) are optional here too. */

export type Id = string;
/** Role ids (unchanged); display names: Planner, Explorer, Orchestrator, Builder, CLI (role pilot), Visualizer; drafter = the agent drafter;
    reviewer = the Role Reviewer (reviews an undefined role; no session, app-wide cost only). */
export type Role = 'planner' | 'astronaut' | 'orchestrator' | 'builder' | 'pilot' | 'visual' | 'drafter' | 'reviewer';
export type StepStatus = 'todo' | 'in_progress' | 'blocked' | 'done' | 'failed';
export type RunEndStatus = 'done' | 'stopped' | 'failed' | 'blocked';
export type ChatMode = 'default' | 'accept_edits' | 'plan';
export type Applies = 'now' | 'new_sessions';
export type FileKind = 'markdown' | 'text' | 'binary' | 'too_large';
export type FileErrorCode = 'conflict' | 'invalid' | 'not_allowed' | 'not_found' | 'too_large' | 'binary';
export type Remember = 'session' | 'project_local';

export interface TokenCounts {
  input_tokens?: number;
  output_tokens?: number;
  cache_read_tokens?: number;
  cache_write_tokens?: number;
}

/* ---------- shared shapes ---------- */
export interface Question { id: string; title: string; body?: string; rec?: string | null; options?: string[] }
export interface QuestionRoundBody { id: string; round: number; questions: Question[] }
export interface RoundAnswer { accepted: boolean; option?: string; text?: string }
/** `agent` = the agent named for the step (null = the Builder; only the Builder or folder agents); `agent_display` = who
    runs it (`Builder` when null); `agent_fallback` = the named agent is missing / broken / not a step worker here, so the Builder runs it. */
export interface PlanStep { n: number; title: string; status?: StepStatus; agent?: string | null; agent_display?: string | null; agent_fallback?: boolean;
  /** the purpose of the agent that runs the step ("building" for the Builder): the chip colour, whatever folder Crew shows */
  agent_purpose?: Purpose | string | null;
  /** skill names the plan names for the step (absent = none): its worker gets them on top of its own allowlist */
  skills?: string[];
  /** the step's skills not found in the session's folders (ignored at run time; shown greyed) */
  skills_unknown?: string[];
  /** the step's role slug (absent = none; never with a non-null agent): a specialism no listed agent fits; runs on the Builder,
      tallied under this name (roles_list). Shown as a chip on the step. */
  role?: string }

/** One skill found in a session's folders (crew_list.skills). shadowed = an earlier folder has one of the same name. */
export interface SkillInfo { name: string; description?: string; path?: string; folder_name?: string; dir_id?: Id | null; source?: 'claude' | 'agents' | string; shadowed?: boolean }
/** An agent's skills (crew_list agents[].skill_setting): "all", a list of names, or "cli" (the CLI chat: the harness decides). */
export type SkillSetting = 'all' | 'cli' | string[];

/** What an agent is for (Crew colours, the planner's registry, permissions for added agents). */
export type Purpose = 'planning' | 'exploring' | 'building' | 'reviewing' | 'other';
/** The fields of the "Add an agent" form (agent_draft reply, agent_create). */
export interface AgentFields { name: string; description: string; purpose: Purpose | ''; model: string; tools: string[]; instructions: string }
/** One agent run's own figures (a role review, a drafting call). */
export interface RunUsage extends TokenCounts { tokens: number; cost: number }

/* ---------- undefined roles (tally + Role Reviewer) ---------- */
export type RoleDecision = 'define' | 'keep' | 'not_yet';
export type RoleState = 'few_uses' | 'dismissed' | 'resting' | 'defining' | 'listed';
export type StepOutcome = 'done' | 'failed' | 'blocked';
/** One recorded use of a role (newest first in roles_list). sent_back = the session's plan was revised after that run;
    named_agent = tallied under the name of an agent that does not exist. */
export interface RoleUse {
  id: string; at: string; dir_id: Id | null; folder: string; session_id: Id; run: number | null; step: number | null; title: string;
  skills: string[]; outcome: StepOutcome; questions: number; assumptions: number; timed_out: number; sent_back: boolean; named_agent: boolean;
}
export interface RoleSample { text: string; session_id: Id; step: number | null; title: string; at: string }
/** One tally entry. visible = show under "Used but not defined"; state / uses_to_list explain why not. */
export interface RoleEntry {
  name: string; base_agent: string; purpose: Purpose | string; skills: string[]; folders: { dir_id: Id | null; name: string }[];
  uses_total: number; first_used: string; last_used: string; samples: RoleSample[];
  verdict: { decision: RoleDecision; reviewer_verdict: RoleDecision | null; at: string; uses_at: number; case_file: string | null } | null;
  dismissed: boolean;
  last_review: { review_id: string; verdict: RoleDecision; case_file: string | null; cost: number; tokens: number; at: string } | null;
  uses: RoleUse[]; problems: number;
  state: RoleState; visible: boolean; uses_to_list: number; resurfaced: boolean; reviewing: boolean; review_id: string | null;
}
export type ReviewTest = 'value' | 'logic' | 'history' | 'fixes' | 'independent';
export type EvidenceStrength = 'none' | 'weak' | 'moderate' | 'strong';
export interface ReviewSection { test: ReviewTest; title: string; finding: string; evidence: { quote: string; source: string }[]; strength: EvidenceStrength }
/** The Role Reviewer's case. sections: always five, in ReviewTest order. proposal only for define; skill_notes only for keep. */
export interface RoleCase {
  case_id: string; review_id: string; role: string; date: string;
  reviewer: { name: string; harness: string; model: string; label: string };
  uses_total: number; uses_recorded: number; opened: string[]; missing: string[];
  sections: ReviewSection[]; verdict: RoleDecision; reason: string; history_thin: boolean; skill_notes: string;
  proposal: { name: string; purpose: Purpose | ''; description: string; instructions: string } | null;
  questions: { test: ReviewTest | ''; question: string; why: string; recommended: string; answer?: string }[];
  usage: RunUsage;
  decision: { decision: RoleDecision; at: string; agent?: string; folder?: string } | null;
  case_file: string | null;
}
/** One validation problem from the server: usually "field: message" text (the agent-file check), or an object. */
export type AgentProblem = string | { field?: string; message?: string; text?: string };

export interface VisualOption {
  id: string; label: string; status: 'rendering' | 'ready' | 'failed'; html?: string; error?: string; path?: string;
  /** the library key the html needs (echarts | chartjs | d3 | plotly | bokeh); only that one is inlined in its frame */
  drawn_with?: string;
}
export interface VisualSetBody {
  set_id: string; brief: string; options: VisualOption[]; picked_id: string | null;
  /** asked for: a library key when known, else the name the planner gave; null = not asked (ECharts) */
  library?: string | null;
  /** the library key actually used */
  drawn_with?: string;
  /** library keys available for the session's folder */
  libraries?: string[];
  /** "drawn in ECharts, styled like <library>" when it fell back, else null */
  library_note?: string | null;
}

/** is_default = the primary folder; is_additional = ticked as additional (joins every new session / chat as add_dirs, minus its primary). */
export interface Directory { dir_id: Id; path: string; name: string; exists: boolean; is_default: boolean; is_additional?: boolean; busy: boolean }
export interface SettingValue { value: unknown; applies: Applies; overridden_by_launch: boolean | string }

export interface DirEntry {
  name: string; type: 'dir' | 'file'; size?: number; mtime?: number | string; kind?: FileKind | null; editable?: boolean;
}
export interface BackupItem { backup_id: string; saved_at: string; size: number }

export interface PermissionSuggestion { label: string; remember: Remember }

export interface CrewAgentDef {
  name: string;
  display_name?: string;
  /** null for folder agents */
  role?: Role | string | null;
  description?: string;
  model?: string;
  source_path?: string;
  instructions?: string;
  builtin_tools?: string[] | null;
  custom_tools?: { name: string; description?: string }[];
  mcp_servers?: { name: string; config?: unknown }[];
  /** false = this agent's engine cannot take MCP servers per run (assignments are kept but do nothing). Absent = yes. NOT in the spec table: assumed. */
  mcp_supported?: boolean;
  /** one line naming the engine when mcp_supported is false, e.g. "Cursor". Optional. */
  engine_label?: string;
  disallowed_tools?: string[];
  warnings?: string[];
  gated_tools?: string[];
  setup?: 'lean' | 'project' | string;
  engine_prompt?: boolean | string;
  prompt_note?: string;
  root?: string;
  path?: string;
  editable?: boolean;
  /** planning | exploring | building | reviewing | other (a folder agent with a missing or unknown purpose is other) */
  purpose?: Purpose | string;
  /** times this agent was started (per user, survives restarts); live updates come as agent_uses */
  uses?: number;
  /** one of Launchpad's six agents (false = a file in the connected folder's .claude/agents/) */
  builtin?: boolean;
  /** folder agents: false when the file is broken (its problems are in warnings), so plans cannot use it */
  step_worker?: boolean;
  /** "all" | [skill names] | "cli" (defaults: Planner all, others none; names missing from crew_list.skills are ignored at run time) */
  skill_setting?: SkillSetting;
  promotion?: {
    start_model?: string; target_model?: string; auto_promote?: boolean; window_turns?: number; criteria?: string; criteria_path?: string;
    root?: string; path?: string; editable?: boolean;
  };
}

/* planner chat history entries (snapshot sessions[].chat, session_started.chat): plain entries or replayed events */
export type PlannerHistoryItem =
  | { role: 'user' | 'assistant' | 'planner' | 'system'; text?: string; markdown?: string; type?: undefined }
  | { role: 'round'; round: QuestionRoundBody; type?: undefined }
  | { role: 'answers'; roundId: string; answers: Record<string, RoundAnswer>; skipped?: boolean; type?: undefined }
  | (ServerEvent & { session_id?: Id });

/* CLI chat history entries: {role, markdown} or a tool row or a replayed event */
export type ChatHistoryItem =
  | { role: 'user' | 'assistant' | 'system'; markdown?: string; text?: string; tool?: undefined; type?: undefined }
  | ({ tool: string; type?: undefined; role?: undefined } & Partial<Omit<ActivityEvent, 'type'>>)
  | (ServerEvent & { chat_id?: Id });

export interface SnapshotSession {
  session_id: Id;
  id?: Id;
  dir_id?: Id;
  cwd?: string;
  folder?: string;
  chat?: PlannerHistoryItem[];
  history?: PlannerHistoryItem[];
  report_sent?: boolean;
  running?: boolean;
  total_cost_usd?: number;
  planner_cost_usd?: number;
  visual_sets?: VisualSetBody[];
  plan_revision?: number;
  draft_pending?: boolean;
  runs?: number;
  autopilot?: boolean;
  auto_answers?: boolean;
  model?: string;
  planner_model?: string | { model?: string; promoted?: boolean; reason?: string | null; by?: 'criteria' | 'user' | null };
  promoted?: boolean;
  reason?: string | null;
  by?: 'criteria' | 'user' | null;
  /* the other planner_model fields (harness, start_model, label, started, switchable_to ...) */
  harness?: string; start_model?: string; top_model?: string; label?: string; option_id?: string; auto_promote?: boolean;
  started?: boolean; switchable_to?: string[];
}
export interface SnapshotChat extends ChatModelFields {
  id?: Id; chat_id?: Id; dir_id?: Id; additional_dir_ids?: Id[]; mode?: ChatMode; cwd?: string; busy?: boolean;
  history?: ChatHistoryItem[];
}

/* ---------- here -> UI ---------- */
export interface SnapshotEvent { type: 'snapshot'; current_session_id?: Id | null; sessions?: SnapshotSession[]; chats?: SnapshotChat[] }
export interface PlannerMessageEvent { type: 'planner_message'; text: string; session_id?: Id }
export interface UserMessageEvent { type: 'user_message'; text: string; session_id?: Id }   // history replays only
export interface TypingEvent { type: 'typing'; on: boolean; session_id?: Id }
export interface QuestionRoundEvent extends QuestionRoundBody { type: 'question_round'; session_id?: Id }
/** Cost totals, summed on the server only (app/costs.py) and sent live; the page displays them and adds nothing up.
    app = everything (by_role = cost per agent role); session = that session's total (every agent but the planner) and the
    planner's own share; chat = that CLI chat's totals. */
export interface AppUsageEvent extends TokenCounts { type: 'usage'; scope?: 'app'; tokens: number; cost: number; by_role?: Record<string, number> }
export interface StepUsage extends TokenCounts { cost: number; tool_calls: number; agents: number }
export interface SessionUsageEvent extends TokenCounts {
  type: 'usage'; scope: 'session'; session_id: Id; cost: number; planner_cost: number; agents: number;
  /** the step agents (builders) of each step, keyed by step number */
  steps: Record<string, StepUsage>;
}
export interface ChatUsageEvent extends TokenCounts { type: 'usage'; scope: 'chat'; chat_id: Id; cost: number; tokens: number; tool_calls: number; agents: number }
export type UsageEvent = AppUsageEvent | SessionUsageEvent | ChatUsageEvent;
export interface CrewEvent { type: 'crew'; agents: { name: string; role?: Role | string; status?: string; session_id?: Id | null }[] }
export interface PlanMetaEvent { type: 'plan_meta'; name?: string; mode?: string; status?: string; session_id?: Id }
export interface SystemEvent { type: 'system'; text: string; session_id?: Id | null; chat_id?: Id | null }
export interface SessionStartedEvent {
  type: 'session_started'; session_id: Id; folder?: string; dir_id?: Id; cwd?: string;
  /** the additional folders this session got (fixed when it started) */
  additional_dir_ids?: Id[];
  chat?: PlannerHistoryItem[]; report_sent?: boolean;
}
export interface SettingsEvent {
  type: 'settings'; directories: Directory[]; values: Record<string, SettingValue>; can_pick_directory: boolean;
  additional_dir_ids?: Id[];
}
export interface DirectoryPickedEvent { type: 'directory_picked'; path: string | null }
export interface DirListingEvent { type: 'dir_listing'; root: string; path: string; entries: DirEntry[] }
export interface FileContentEvent {
  type: 'file_content'; root: string; path: string; kind: FileKind; text?: string; size: number; mtime?: number | string;
  version: string | number; editable: boolean; applies: Applies | null; validates_as: 'agent' | 'plan' | null;
}
export interface FileSavedEvent { type: 'file_saved'; root: string; path: string; version: string | number; backup_id: string | null; applies?: Applies | null }
export interface FileErrorEvent {
  type: 'file_error'; root: string; path: string; code: FileErrorCode; message: string;
  current?: { text: string; version: string | number };
}
export interface BackupsEvent { type: 'backups'; root: string; path: string; items: BackupItem[] }
/** One changed file in a repo: M modified, A added (staged), D deleted, U unmerged, ? untracked; counts are 0 for binary files. */
export interface GitFile { path: string; status: 'M' | 'A' | 'D' | 'U' | '?'; added: number; removed: number; binary: boolean }
/** A repo found in a connected folder (see the git_repos header in app/server.py). linked = a remote and an upstream branch exist. */
export interface GitRepo {
  repo_id: string; name: string; dir_id: Id; folder_name: string; rel: string; branch: string | null; detached: boolean;
  remote: { name: string; host: string; owner: string; repo: string } | null; upstream: string | null; linked: boolean;
  ahead: number; behind: number; clean: boolean; files: GitFile[]; more: number; added: number; removed: number; error: string | null;
}
export interface GitReposEvent { type: 'git_repos'; available: boolean; repos: GitRepo[] }
export type GitOp = 'refresh' | 'fetch' | 'commit' | 'push';
export interface GitResultEvent { type: 'git_result'; repo_id: string; op: GitOp; ok: boolean; committed: boolean; message: string; repo: GitRepo | null }
export interface PlanDraftEvent {
  type: 'plan_draft'; session_id: Id; path: string; markdown: string; steps: PlanStep[]; revision?: number; previous_runs?: number;
}
export interface RunStartedEvent {
  type: 'run_started'; session_id: Id; name: string; steps: PlanStep[]; run?: number; revision?: number; autopilot?: boolean;
}
export interface PlannerModelEvent {
  type: 'planner_model'; session_id: Id; model: string; promoted: boolean; reason: string | null; by: 'criteria' | 'user' | null;
  /** harness and models of this session; label = "<harness> · <model>" now; option_id = "<harness>:<model>" now */
  harness?: string; start_model?: string; top_model?: string; label?: string; option_id?: string;
  /** this session may promote itself */
  auto_promote?: boolean;
  /** someone wrote to it: harness and start model are fixed */
  started?: boolean;
  /** picker options it can move to now (all available ones before its first message; else its top model while promotable) */
  switchable_to?: string[];
}
/** One harness-and-model pair of the planner picker; available = agentlib says its engine is (else note "not available yet"). */
export interface PlannerOption { id: string; harness: string; harness_label: string; model: string; model_label: string; label: string; available: boolean; note: string | null }
/** The planner picker: options, what the next new plan starts on (per user), auto-promote, the rules text. */
export interface PlannerChoiceEvent {
  type: 'planner_choice'; options: PlannerOption[];
  choice: { option_id: string; harness: string; model: string; label: string };
  auto_promote: boolean; top_model: string; top_label: string;
  /** start = top: no promotion */
  promotion_off: boolean;
  /** --model pins the planner for this launch (no choosing) */
  pinned: string | null;
  /** planner settings a launch option sets */
  overridden: string[];
  rules: { markdown: string; path: string | null };
}
/** The CLI chat's picker: the same options as the planner's (harness = "CLI" in the UI), what the next new chat starts
    on (settings pilot_harness + pilot_model, per user). Independent of the planner's choice. */
export interface CliChoiceEvent {
  type: 'cli_choice'; options: PlannerOption[];
  choice: { option_id: string; harness: string; model: string; label: string };
  /** CLI chat settings a launch option sets */
  overridden: string[];
}
/** A CLI chat's CLI and model (as in chat_started); started = someone wrote to it (CLI and model fixed). */
export interface ChatModelFields { harness?: string; model?: string; label?: string; option_id?: string; started?: boolean }
/** Sent when a chat nobody has written to is reloaded with a new choice, and at its first message. */
export interface ChatModelEvent extends ChatModelFields { type: 'chat_model'; chat_id: Id }
export interface AutopilotEvent { type: 'autopilot'; session_id: Id; on: boolean }
/** The Auto answers switch of a session (after set_auto_answers; also in the snapshot as sessions[].auto_answers). */
export interface AutoAnswersEvent { type: 'auto_answers'; session_id: Id; on: boolean }
/** One plan-step worker's question decided under Auto answers (builders only): its own recommended answer was taken. Shown as a
    compact, marked line in Incoming (not in the planner chat). id = the question's queue id; a card still showing is settled. */
export interface AutoAnswerEvent {
  type: 'auto_answer'; session_id: Id; id: string; agent: string; step: number | null; title: string; answer: string;
}
export interface StepUpdateEvent {
  type: 'step_update'; session_id: Id; n: number; status?: StepStatus; built?: string[]; report_path?: string;
  agent?: string | null; agent_display?: string | null; agent_fallback?: boolean; agent_purpose?: Purpose | string | null;
  skills?: string[]; skills_unknown?: string[]; role?: string;
}
export interface QueueItemEvent {
  type: 'queue_item';
  id: Id;
  session_id: Id | null;
  chat_id?: Id | null;
  kind: 'question' | 'permission' | 'plan' | 'info';
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
  tool?: string;                               // permission
  command?: string;                            // run permission cards
  suggestions?: PermissionSuggestion[];        // chat permission cards
  markdown?: string;                           // chat plan cards
  /** Role Reviewer questions (session_id and chat_id null; never auto-answered): the review, the role, the test it is for */
  review_id?: string;
  role?: string;
  test?: ReviewTest | '';
}
export interface QueueResolvedEvent { type: 'queue_resolved'; id: Id; answer: string | null; by?: 'user' | 'timer' | 'autopilot' | 'auto' }
export interface ByModel extends TokenCounts { model: string; cost_usd: number }
export interface AgentUsageEvent extends TokenCounts {
  type: 'agent_usage';
  session_id: Id | null;
  chat_id?: Id | null;
  agent_id: Id;
  role: Role;
  name: string;
  step: number | null;
  status: 'working' | 'idle' | 'done' | string;
  cost_usd: number;
  tool_calls: number;
  by_model?: ByModel[];
}
export interface ActivityEvent {
  type: 'activity';
  id: Id;
  session_id: Id | null;
  chat_id?: Id | null;
  agent_id: Id;
  role: Role | string;
  name: string;
  step: number | null;
  tool: string;
  summary: string;
  status: 'started' | 'done' | 'denied' | 'failed';
  ts: string;
  auto?: boolean;
}
export interface RunFinishedEvent {
  type: 'run_finished'; session_id: Id; status: RunEndStatus; report_path: string; markdown: string;
  total_cost_usd?: number; planner_cost_usd?: number; report_sent?: boolean;
}
/** dir_id = the connected folder whose .claude/agents/ files are included; tool_choices = tools the Add form offers. */
export interface CrewListEvent { type: 'crew_list'; agents: CrewAgentDef[]; dir_id?: Id | null; tool_choices?: string[];
  /** skills found in dir_id (primary) + the additional folders, primary first */
  skills?: SkillInfo[] }
/** An agent's use count changed (keyed by agent name). */
export interface AgentUsesEvent { type: 'agent_uses'; name: string; uses: number }
/** usage = the drafting call's own tokens and cost; role = echoed on the define path (agent_draft with role). */
export interface AgentDraftedEvent { type: 'agent_drafted'; ok: boolean; dir_id?: Id; fields?: Partial<AgentFields>; error?: string; usage?: RunUsage; role?: string }
/** ok: a fresh crew_list follows (and roles_list on the define path). Not ok: error + problems (the agent-file check).
    role / case_path (define path): the tally entry is gone; case_path = ".claude/agent-cases/<name>.md" in that folder. */
export interface AgentSavedEvent { type: 'agent_saved'; ok: boolean; dir_id?: Id; name?: string; error?: string; problems?: AgentProblem[]; role?: string; case_path?: string }
/** The undefined-roles tally, every entry (most recently used first), with visibility. */
export interface RolesListEvent { type: 'roles_list'; threshold: number; resurface_uses: number; entries: RoleEntry[] }
/* ---------- Connections and the MCP library (spec Features/2026-11-17-settings-connections-mcp.md) ---------- */
/** connection_test: installed false = program not found; installed + reachable false = detail has the error;
    usable false (Cursor) = installed but Launchpad cannot use it yet. reachable / version may be null when not checked. */
export interface ConnectionTestEvent {
  type: 'connection_test'; id: string; installed: boolean; version?: string | null; reachable?: boolean | null; usable?: boolean | null; detail?: string | null;
}
export type McpKind = 'command' | 'url';
export type McpStatus = 'connected' | 'failed' | 'untested' | 'testing';
/** The config of one server. Secret values (env, headers) arrive masked and are sent back unchanged to keep them
    (ASSUMED shape: the table only says "its config with secret values masked"). */
export interface McpConfig { command?: string; args?: string[]; env?: Record<string, string>; url?: string; headers?: Record<string, string> }
export interface McpServer { name: string; kind: McpKind; config: McpConfig; status: McpStatus; detail?: string | null; tool_count?: number | null; tested_at?: string | null }
/** A connection or import source, as listed by the server (id + display name). */
export interface NamedItem { id: string; name: string }
/** The reply to every MCP message. connections / import_sources are ASSUMED to ride on it (the table does not say
    where they come from); error = a refused save (assumed; else the text arrives as a system line). */
export interface McpLibraryEvent {
  type: 'mcp_library'; servers: McpServer[]; assignments: Record<string, string[]>;
  connections?: NamedItem[]; import_sources?: NamedItem[]; error?: string | null;
}
export interface McpImportCandidate { name: string; kind: McpKind; summary: string; exists: boolean }
export interface McpImportsEvent { type: 'mcp_imports'; source: string; servers: McpImportCandidate[] }
export interface ReviewStartedEvent { type: 'review_started'; review_id: string; role: string; model: string; harness: string }
export interface ReviewProgressEvent { type: 'review_progress'; review_id: string; role: string; phase: 'reading' | 'asking' | 'finalising'; text: string }
/** The finished case (also replayed on connect: the latest case per role). */
export interface ReviewCaseEvent { type: 'review_case'; review_id: string; role: string; case: RoleCase }
/** The review errored; the role stays reviewable. */
export interface ReviewFailedEvent { type: 'review_failed'; review_id: string; role: string; error: string }
/** review_start refused: one already running for the role (review_id = it) or the role is not in the tally. */
export interface ReviewRefusedEvent { type: 'review_refused'; role: string; review_id: string | null; error: string }
export interface ReviewDecidedEvent { type: 'review_decided'; role: string; decision: RoleDecision; reviewer_verdict: RoleDecision | null; review_id: string | null; case_file: string | null }
export interface AgentRemovedEvent { type: 'agent_removed'; ok: boolean; dir_id?: Id; name?: string; error?: string }
export interface ChatStartedEvent extends ChatModelFields {
  type: 'chat_started'; chat_id: Id; mode?: ChatMode; cwd?: string; dir_id?: Id | null; busy?: boolean;
  additional_dir_ids?: Id[];
  /** set when chat_from_plan opened the chat (mode plan; the plan follows as the first user message) */
  from_session_id?: Id | null;
  history?: ChatHistoryItem[];
}
export interface ChatTypingEvent { type: 'chat_typing'; chat_id: Id; on: boolean }
export interface ChatDeltaEvent { type: 'chat_delta'; chat_id: Id; text: string }
export interface ChatMessageEvent { type: 'chat_message'; chat_id: Id; role: 'assistant' | 'user'; markdown?: string; text?: string }
export interface ChatModeEvent { type: 'chat_mode'; chat_id: Id; mode: ChatMode }
export interface ChatDoneEvent { type: 'chat_done'; chat_id: Id; status: 'ok' | 'stopped' | 'failed'; error?: string }
export interface VisualSetEvent extends VisualSetBody { type: 'visual_set'; session_id: Id }

export type ServerEvent =
  | SnapshotEvent | PlannerMessageEvent | UserMessageEvent | TypingEvent | QuestionRoundEvent | UsageEvent | CrewEvent
  | PlanMetaEvent | SystemEvent | SessionStartedEvent | SettingsEvent | DirectoryPickedEvent | DirListingEvent
  | FileContentEvent | FileSavedEvent | FileErrorEvent | BackupsEvent | PlanDraftEvent | RunStartedEvent
  | PlannerModelEvent | PlannerChoiceEvent | CliChoiceEvent | AutopilotEvent | AutoAnswersEvent | AutoAnswerEvent | StepUpdateEvent | QueueItemEvent | QueueResolvedEvent | AgentUsageEvent
  | ActivityEvent | RunFinishedEvent | CrewListEvent | ChatStartedEvent | ChatModelEvent | ChatTypingEvent | ChatDeltaEvent
  | ChatMessageEvent | ChatModeEvent | ChatDoneEvent | VisualSetEvent
  | AgentUsesEvent | AgentDraftedEvent | AgentSavedEvent | AgentRemovedEvent | GitReposEvent | GitResultEvent
  | RolesListEvent | ReviewStartedEvent | ReviewProgressEvent | ReviewCaseEvent | ReviewFailedEvent | ReviewRefusedEvent
  | ReviewDecidedEvent | ConnectionTestEvent | McpLibraryEvent | McpImportsEvent;

export type ServerEventType = ServerEvent['type'];

/** Every server event type, for tests and exhaustiveness checks. */
export const SERVER_EVENT_TYPES: ServerEventType[] = [
  'snapshot', 'planner_message', 'user_message', 'typing', 'question_round', 'usage', 'crew', 'plan_meta', 'system',
  'session_started', 'settings', 'directory_picked', 'dir_listing', 'file_content', 'file_saved', 'file_error',
  'backups', 'plan_draft', 'run_started', 'planner_model', 'planner_choice', 'cli_choice', 'autopilot', 'auto_answers', 'auto_answer', 'step_update', 'queue_item', 'queue_resolved',
  'agent_usage', 'activity', 'run_finished', 'crew_list', 'chat_started', 'chat_model', 'chat_typing', 'chat_delta', 'chat_message',
  'chat_mode', 'chat_done', 'visual_set', 'agent_uses', 'agent_drafted', 'agent_saved', 'agent_removed',
  'git_repos', 'git_result',
  'roles_list', 'review_started', 'review_progress', 'review_case', 'review_failed', 'review_refused', 'review_decided',
  'connection_test', 'mcp_library', 'mcp_imports',
];

/* ---------- UI -> here ---------- */
export type UiMessage =
  | { type: 'user_message'; text: string }
  | { type: 'round_answer'; roundId: string; answers: Record<string, RoundAnswer>; skipped?: boolean }
  | { type: 'plan_approve'; session_id: Id }
  | { type: 'queue_response'; id: Id; answer: string }
  | {
      type: 'queue_response'; id: Id; decision: 'allow' | 'deny' | 'always'; remember?: Remember;
      mode?: 'default' | 'accept_edits'; message?: string;
    }
  | { type: 'queue_dismiss'; id: Id }
  | { type: 'get_crew'; dir_id?: Id }
  | { type: 'report_to_planner'; session_id: Id }
  | { type: 'run_stop'; session_id: Id }
  | { type: 'new_session'; dir_id?: Id }
  | { type: 'chat_new'; dir_id?: Id }
  | { type: 'chat_message'; chat_id: Id; text: string }
  | { type: 'chat_set_mode'; chat_id: Id; mode: ChatMode }
  | { type: 'chat_stop'; chat_id: Id }
  | { type: 'visual_pick'; session_id: Id; set_id: string; option_id: string | null }
  | { type: 'visual_tweak'; session_id: Id; set_id: string; option_id: string; text: string }
  | { type: 'visual_retry'; session_id: Id; set_id: string; option_id: string }
  | { type: 'planner_promote'; session_id: Id }
  | { type: 'planner_choose'; option_id: string; session_id?: Id }
  | { type: 'cli_choose'; option_id: string }
  | { type: 'set_autopilot'; session_id: Id; on: boolean }
  | { type: 'set_auto_answers'; session_id: Id; on: boolean }
  | { type: 'get_settings' }
  | { type: 'set_settings'; patch: Record<string, unknown> }
  | { type: 'add_directory'; path: string }
  | { type: 'remove_directory'; dir_id: Id }
  | { type: 'pick_directory' }
  | { type: 'list_dir'; root: string; path: string }
  | { type: 'read_file'; root: string; path: string }
  | { type: 'save_file'; root: string; path: string; text: string; base_version: string | number | null }
  | { type: 'list_backups'; root: string; path: string }
  | { type: 'restore_backup'; root: string; path: string; backup_id: string }
  /** role (define path): the drafter also gets the role's samples, skills and latest review case; text may be "" then */
  | { type: 'agent_draft'; dir_id: Id; text: string; role?: string }
  /** role (define path): the tally role this agent defines (entry removed, case copy saved beside the agent) */
  | { type: 'agent_create'; dir_id: Id; fields: AgentFields; role?: string }
  | { type: 'roles_get' }
  | { type: 'role_dismiss'; role: string }
  | { type: 'role_merge'; role: string; into: string }
  | { type: 'review_start'; role: string }
  | { type: 'review_decide'; role: string; decision: RoleDecision }
  | { type: 'agent_remove'; dir_id: Id; name: string }
  | { type: 'set_agent_skills'; name: string; skills: 'all' | string[]; dir_id?: Id }
  | { type: 'test_connection'; id: string }
  | { type: 'get_mcp' }
  | { type: 'save_mcp_server'; server: { name: string; kind: McpKind; config: McpConfig }; original_name?: string }
  | { type: 'remove_mcp_server'; name: string }
  | { type: 'test_mcp_server'; name: string }
  | { type: 'list_mcp_imports'; source: string }
  | { type: 'import_mcp_servers'; source: string; names: string[] }
  | { type: 'set_agent_mcp'; agent: string; servers: string[] }
  | { type: 'git_scan' }
  | { type: 'git_refresh'; repo_id: string }
  | { type: 'git_fetch'; repo_id: string }
  | { type: 'git_commit'; repo_id: string; message: string; paths: string[]; push?: boolean }
  | { type: 'git_push'; repo_id: string }

  | { type: 'chat_from_plan'; session_id: Id };

export type UiMessageType = UiMessage['type'];
