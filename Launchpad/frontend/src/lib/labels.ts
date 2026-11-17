/* Display labels shared by several screens (copied from the vanilla page). */
import type { ChatMode, ReviewTest, RoleDecision } from '../contract';

export const STEP_LABEL: Record<string, string> = { todo: 'To do', in_progress: 'In progress', blocked: 'Blocked', done: 'Done', failed: 'Failed' };
export const S_LABEL: Record<string, string> = { planning: 'Planning', running: 'Running', waiting: 'Waiting on you', done: 'Done', stopped: 'Stopped', failed: 'Failed', blocked: 'Ended blocked' };
export const P_LABEL: Record<string, string> = { working: 'thinking', waiting: 'waiting on you', idle: 'idle', done: 'done' };

export const MODES: ChatMode[] = ['default', 'accept_edits', 'plan'];
export const MODE_LABEL: Record<ChatMode, string> = { default: 'Ask before edits', accept_edits: 'Auto-accept edits', plan: 'Plan' };   // icons: views/Code (MODE_ICON)
export const MODE_HINT: Record<ChatMode, string> = {
  default: 'The CLI asks before it edits files or runs commands',
  accept_edits: 'File edits are accepted without asking; commands still ask',
  plan: 'Read-only: the CLI explores and proposes a plan, nothing is changed',
};

export const AUTO_ANSWERS_HINT = "Auto answers: while on, every question a builder asks in this run is answered at once with the builder's own recommendation, so work carries on while you are away. Each one is saved as a question file and listed in the report. The planner's questions and CLI chats are never answered for you. Permission requests are not affected: Autopilot is the switch for those.";
export const AP_HINT = 'Autopilot approves every builder permission request without showing a card. No exceptions: that includes git push and writes outside the working folder.';

/** Display names of the six built-in roles (the role ids and agent file names stay as they are). */
export const ROLE_LABEL: Record<string, string> = {
  planner: 'Planner', astronaut: 'Explorer', orchestrator: 'Orchestrator', builder: 'Builder', visual: 'Visualizer', pilot: 'CLI',
  drafter: 'Agent drafter',
};
export const roleLabel = (r: unknown): string => ROLE_LABEL[String(r || '')] || String(r || 'agent');
/** An agent name as shown: a bare role id ("orchestrator", "astronaut") becomes its display name; anything else stays. */
export const agentLabel = (n: unknown): string => { const t = String(n ?? ''); return ROLE_LABEL[t] || t; };

/** Agent purposes, in the order Crew shows them; added agents may be any but planning. */
export const PURPOSES = ['planning', 'exploring', 'building', 'reviewing', 'other'] as const;
export const ADDABLE_PURPOSES = ['exploring', 'building', 'reviewing', 'other'] as const;
export const PURPOSE_LABEL: Record<string, string> = { planning: 'Planning', exploring: 'Exploring', building: 'Building', reviewing: 'Reviewing', other: 'Other' };
export const PURPOSE_HINT: Record<string, string> = {
  planning: 'Shapes the work with you before anything is built',
  exploring: 'Looks things up; read-only (no write, edit or shell tools)',
  building: 'Does a plan step; gets the Builder\'s permission cards and guards',
  reviewing: 'Checks work; read-only (no write, edit or shell tools)',
  other: "Anything else; guarded like building (permission cards and the Builder's checks)",
};
/** Tools an exploring or reviewing agent never gets, whatever its file lists. */
export const WRITE_TOOLS = ['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'];
/** Models the Add an agent form offers (the agent-file check also accepts claude-... ids). */
export const AGENT_MODELS: { value: string; label: string }[] = [
  { value: 'sonnet', label: 'Sonnet' }, { value: 'haiku', label: 'Haiku (cheapest)' }, { value: 'opus', label: 'Opus (strongest)' },
  { value: 'inherit', label: 'Inherit (same as the session)' },
];

export const SET_LABEL: Record<string, string> = {
  question_timeout_s: 'Question timer (seconds)', permission_timeout_s: 'Permission timer (seconds; unanswered = denied)',
  autopilot_default: 'Autopilot on for new sessions', planner_start: 'Planner start model', planner_top: 'Planner model after promotion',
  planner_start_model: 'Planner start model', planner_target_model: 'Planner model after promotion', promotion_window: 'Promotion window (turns)',
  promotion_window_turns: 'Promotion window (turns)', promotion_criteria: 'Promotion criteria file', pilot_model: 'CLI model', planner_top_model: 'Planner model after promotion',
  planner_harness: 'Planner CLI (new plans)', pilot_harness: 'CLI chat: CLI (new chats)', planner_auto_promote: 'Planner may promote itself (auto-promote)',
  visual_model: 'Visualizer model', reviewer_model: 'Role Reviewer model', planner_model: 'Planner model (pinned)',
};

/** Queue tag text per kind (Incoming and CLI cards). */
export const KIND_TAG: Record<string, { cls: string; text: string }> = {
  question: { cls: 'ques', text: 'Question' },
  permission: { cls: 'perm', text: 'Permission' },
  info: { cls: 'info', text: 'Update' },
  report: { cls: 'info', text: 'Report' },
  plan: { cls: 'ques', text: 'Plan' },
};

/** The Role Reviewer's five tests, in the fixed order the case shows them (titles as the server writes them). */
export const REVIEW_TESTS: { test: ReviewTest; title: string }[] = [
  { test: 'value', title: 'Clear value' }, { test: 'logic', title: 'Logic beyond the skill' }, { test: 'history', title: 'Clear usage history' },
  { test: 'fixes', title: 'Mistakes or issues it would fix' }, { test: 'independent', title: 'Independent view: is a subagent the right fix?' },
];
export const STRENGTH_LABEL: Record<string, string> = { none: 'No evidence', weak: 'Weak evidence', moderate: 'Moderate evidence', strong: 'Strong evidence' };
export const DECISION_LABEL: Record<RoleDecision, string> = { define: 'Define an agent', keep: 'Keep as skill + Builder', not_yet: 'Not yet' };
export const DECISION_HINT: Record<RoleDecision, string> = {
  define: 'A drafter writes the agent from the case; you edit it and save',
  keep: 'Stay with a skill and the generic Builder; the case notes what the skill should cover',
  not_yet: 'Keep counting uses; ask again later',
};
