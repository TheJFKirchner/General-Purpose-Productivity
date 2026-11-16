/* Demo data (ported unchanged from the vanilla page): folders, settings, files, the crew list, plan / report text. */
import type { CrewAgentDef, Directory, SettingValue } from '../contract';

export const PRICE: Record<string, [number, number, number, number]> = { opus: [15, 75, 1.5, 18.75], sonnet: [3, 15, 0.3, 3.75], haiku: [1, 5, 0.1, 1.25] };   // $ per million: in, out, cache read, cache write

export const FILES: Record<string, string[]> = {
  'S-A': ['loader/load_claims.py', 'loader/schema.sql', 'profile/claims_extract_profile.md', 'qa/row_count_recon.md', 'handoff.md', 'data/claims_q3.parquet'],
  'S-B': ['sql/readmissions_30d.sql', 'sql/facility_map.sql', 'workbook/readmissions_tab.xlsx', 'qa/readmissions_vs_q2.md', 'data/census_q3.csv'],
  other: ['out/notes.md', 'plan.md', 'brief.md', 'out/trend_tabs.py', 'packages/2026Q2/inpatient_trend.xlsx'],
};

export const fsDirs = (): Directory[] => [
  { dir_id: 'd1', path: 'C:/work/claims-project', name: 'claims-project', exists: true, is_default: true, busy: true },
  { dir_id: 'd2', path: 'C:/work/readmissions', name: 'readmissions', exists: true, is_default: false, busy: true }];

export const fsVals = (): Record<string, SettingValue> => ({
  question_timeout_s: { value: 180, applies: 'now', overridden_by_launch: false },
  permission_timeout_s: { value: 180, applies: 'now', overridden_by_launch: false },
  autopilot_default: { value: false, applies: 'new_sessions', overridden_by_launch: false },
  planner_start: { value: 'sonnet', applies: 'new_sessions', overridden_by_launch: false },
  planner_top: { value: 'opus', applies: 'new_sessions', overridden_by_launch: false },
  promotion_window: { value: 2, applies: 'new_sessions', overridden_by_launch: false },
  promotion_criteria: { value: PROMOTION_PATH, applies: 'new_sessions', overridden_by_launch: false },
  pilot_model: { value: 'sonnet', applies: 'new_sessions', overridden_by_launch: '--pilot-model sonnet' },
  visual_model: { value: 'haiku', applies: 'new_sessions', overridden_by_launch: false } });

export interface DemoFile {
  kind: 'markdown' | 'text' | 'binary' | 'too_large'; text?: string; size: number; mtime: number; version: number; editable: boolean;
  applies?: 'now' | 'new_sessions' | null; validates_as?: 'agent' | 'plan' | null; backups: { backup_id: string; saved_at: string; size: number; text: string }[];
  touched?: boolean;
}

/** Built-in agent definitions live at app/agents/<folder>/agent.md (role id -> folder; the server's layout). */
const ROLE_FOLDER: Record<string, string> = { planner: 'planner', astronaut: 'explorer', orchestrator: 'orchestrator', builder: 'builder', visual: 'visualizer', pilot: 'claude_code', drafter: 'drafter' };
export const PROMOTION_PATH = 'app/agents/planner/promotion.md';
export const agentPath = (role: string | null | undefined): string => `app/agents/${ROLE_FOLDER[role ?? ''] ?? role}/agent.md`;

export function demoFiles(): Record<string, Partial<DemoFile>> {
  const md = (text: string, o: Partial<DemoFile> = {}): Partial<DemoFile> => ({ kind: 'markdown', text, editable: true, applies: 'now', validates_as: null, ...o });
  const tx = (text: string): Partial<DemoFile> => ({ kind: 'text', text, editable: false });
  return {
    'd1|README.md': md('# Claims project\n\nLoader and QA for the monthly claims extract.\n\n- `loader/` builds the table\n- `qa/` holds the reconciliation notes'),
    'd1|notes/team-notes.md': md('# Team notes\n\n- Use `service_from_dt` for the incurred month\n- Ask before excluding more than 1% of rows'),
    'd1|loader/load_claims.py': tx('import pandas as pd\n\n\ndef load(path):\n    df = pd.read_parquet(path)\n    df["incurred_month"] = df.service_from_dt.dt.to_period("M")\n    return df\n'),
    'd1|loader/schema.sql': tx('create table claims (\n  claim_id varchar,\n  service_from_dt date,\n  paid_dt date\n);'),
    'd1|data/claims_q3.parquet': { kind: 'binary', size: 48234112, editable: false },
    'd1|.launchpad/S-A/plan.md': md('---\nplan: "Claims loader rebuild"\nstatus: "approved"\ndate: "2026-11-12"\nsession: "S-A"\nsteps:\n- {n: 1, title: "Profile the source extract", skill: null, after: [], status: "done"}\n- {n: 2, title: "Build the loader", skill: null, after: [1], status: "in_progress"}\n---\n# Claims loader rebuild\n\n## Goal\nRebuild the monthly loader.\n\n## Steps\n\n### Step 1: Profile the source extract\nProfile columns and dates.\n\n### Step 2: Build the loader\nWrite `loader/load_claims.py`.', { validates_as: 'plan', applies: 'new_sessions' }),
    'd1|.launchpad/S-A/flight-log.md': md('# Flight log\n\n- 09:12 Profiler read 41 columns\n- 09:20 Loader builder started step 2'),
    'd1|.launchpad/S-A/operations-manual.md': md('# Operations manual\n\n- Extract lives in `data/claims_q3.parquet`\n- Tests: `python -m pytest qa/`'),
    'd1|.launchpad/S-A/steps/step-01.md': md('# Step 1 report\n\nBuilt `profile/claims_extract_profile.md`. Three date fields found.'),
    'd1|.launchpad/S-A/activity.log': tx('09:12:01 profiler Read data/claims_q3_sample.csv done\n09:12:40 profiler Bash python profile/profile_extract.py done\n'),
    'd2|README.md': md('# Readmissions\n\n30-day readmission SQL and the workbook tab.'),
    'd2|sql/readmissions_30d.sql': tx('-- 30-day readmissions\nselect facility_id, count(*) from readmits group by 1;'),
    'd2|exports/claims_full.csv': { kind: 'too_large', size: 734003200, editable: false },
    'd2|.launchpad/S-B/plan.md': md('---\nplan: "Readmissions tab"\nstatus: "approved"\ndate: "2026-11-12"\nsession: "S-B"\nsteps:\n- {n: 1, title: "Write the 30-day readmission SQL", skill: null, after: [], status: "in_progress"}\n---\n# Readmissions tab\n\n## Steps\n\n### Step 1: Write the 30-day readmission SQL\nUse NPI facility ids.', { validates_as: 'plan', applies: 'new_sessions' }),
    [`app|${agentPath('planner')}`]: md('---\nname: launchpad-planner\ndescription: Interviews the user in rounds and writes the plan file.\nmodel: opus\n---\n# Planner\n\nYou help the user plan one piece of work. You **never** build anything yourself.\n\n- Interview in rounds of at most 3 questions\n- Use `ask_user` for every question', { validates_as: 'agent', applies: 'new_sessions' }),
    [`app|${agentPath('builder')}`]: md('---\nname: launchpad-builder\ndescription: Builds one plan step from a brief.\nmodel: sonnet\n---\n# Builder\n\nBuild exactly one plan step from the brief.', { validates_as: 'agent', applies: 'new_sessions' }),
    'd1|.claude/agents/sql-builder.md': md(FOLDER_AGENT_FILES['sql-builder'], { validates_as: 'agent', applies: 'new_sessions' }),
    'd1|.claude/agents/sql-reviewer.md': md(FOLDER_AGENT_FILES['sql-reviewer'], { validates_as: 'agent', applies: 'new_sessions' }),
    [`app|${PROMOTION_PATH}`]: md('## Promote to Opus when\n- the work has **three or more outputs**\n- there is a sign-off point\n\n## Stay on Sonnet when\n- it is a small, single-output change', { applies: 'new_sessions' }),
  };
}

export const PLANNER_OLD_BACKUP = '---\nname: launchpad-planner\ndescription: Interviews the user.\nmodel: opus\n---\n# Planner (older version)\n\nAsk questions, then write the plan.';

export const DRAFT_C_MARKDOWN = `# Q3 inpatient trend refresh

**Status:** draft · **Audience:** manager group · **Basis:** incurred month

## Goal
Refresh last quarter's inpatient trend package with Q3 data and add a 30-day readmissions tab.

## Steps
| # | Step | Done when |
|---|------|-----------|
| 1 | Pull the Q3 claims extract | Extract saved, row counts logged |
| 2 | Refresh the trend tabs | Summary, cost trend, utilization and top drivers match the new data |
| 3 | Build the readmissions tab (Sql builder) | Top 10 facilities, 30-day window, after utilization |
| 4 | Review the readmissions SQL (Sql reviewer) | NULL handling, join fan-out and row counts checked |
| 5 | Draft commentary | Only after you sign off the numbers |

## Sign-off points
- Numbers reviewed before commentary (step 5)

## Inputs
- \`plans/q3-inpatient-refresh/notes.md\` (interview notes)
- Last quarter's package: \`packages/2026Q2/inpatient_trend.xlsx\`

> Out of scope: outpatient, pharmacy.`;

/** Tools the Add an agent form offers (crew_list.tool_choices). */
export const TOOL_CHOICES = ['Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash', 'WebFetch', 'WebSearch', 'TodoWrite'];

/** Starting use counts (per agent name); the demo bumps them as agents start and sends agent_uses. */
export const START_USES: Record<string, number> = {
  'launchpad-planner': 14, 'launchpad-astronaut': 37, 'launchpad-orchestrator': 9, 'launchpad-builder': 41, 'launchpad-visual': 12,
  'launchpad-pilot': 6, 'sql-builder': 3, 'sql-reviewer': 0,
};

/** The two agents in the demo's connected folder d1 (.claude/agents/), as files. */
const FOLDER_AGENT_FILES: Record<string, string> = {
  'sql-builder': `---\nname: sql-builder\ndescription: Writes and tests analysis SQL against the warehouse. Long house-style prompt.\npurpose: building\nmodel: sonet\ntools: Read, Write, Edit, Glob, Grep, Notebook\n---\n# SQL builder\n\nYou write analysis SQL for the claims warehouse and test it before handing over.\n\n## House rules\n${Array.from({ length: 28 }, (_, k) => `${k + 1}. ${['Read the brief and the plan step before touching any file.', 'Never write outside the session folder.', 'Use CTEs, not nested subqueries, and name every CTE for what it holds.', 'Every query gets a header comment: purpose, inputs, grain.', 'Ask the user (ask_user) before excluding more than 1% of rows.', 'Prefer `service_from_dt` for incurred month unless the brief says otherwise.', 'Log row counts before and after every join.'][k % 7]}`).join('\n')}\n\n## Hand-over\nEnd with \`report_step\` listing every file and the row counts you logged.`,
  'sql-reviewer': '---\nname: sql-reviewer\ndescription: Reviews new SQL for NULL handling, join fan-out and row-count drift before a step is marked done.\npurpose: reviewing\nmodel: haiku\ntools: Read, Glob, Grep\n---\n# SQL reviewer\n\nRead the step\'s SQL and its brief, then check:\n\n- NULL handling in every filter and join key\n- joins that multiply rows (compare counts before and after)\n- row counts against last quarter\n\nReport what you found as a short list. You never change files.',
};

/** Folder agents as crew_list entries (the demo fills root / path / uses / instructions). */
export function folderAgentsBase(): CrewAgentDef[] {
  return [
    { name: 'sql-builder', display_name: 'Sql builder', role: null, purpose: 'building', builtin: false, step_worker: true, model: 'sonet',
      description: 'Writes and tests analysis SQL against the warehouse. Long house-style prompt.',
      builtin_tools: ['Read', 'Write', 'Edit', 'Glob', 'Grep'], custom_tools: [{ name: 'report_step', description: 'Write the step report and end the step.' }],
      mcp_servers: [{ name: 'warehouse', config: 'stdio: python -m warehouse_mcp' }], disallowed_tools: [],
      warnings: ['Model "sonet" is not a known alias; the default model will be used.', 'Tool "Notebook" in tools: is not a known built-in and was ignored.'] },
    { name: 'sql-reviewer', display_name: 'Sql reviewer', role: null, purpose: 'reviewing', builtin: false, step_worker: true, model: 'haiku',
      description: 'Reviews new SQL for NULL handling, join fan-out and row-count drift before a step is marked done.',
      builtin_tools: ['Read', 'Glob', 'Grep'], custom_tools: [{ name: 'report_step', description: 'Write the step report and end the step.' }], mcp_servers: [], disallowed_tools: [], warnings: [] },
  ];
}

export function crewBase(): CrewAgentDef[] {
  return [
    { name: 'launchpad-visual', display_name: 'Visualizer', role: 'visual', purpose: 'planning', builtin: true, model: 'haiku',
      description: 'Draws small visuals and design options on made-up data so the user can settle a design question while planning.',
      instructions: '# Visualizer\n\nDraw one small visual per option as a self-contained HTML fragment.\n\n- ECharts is available as a global `echarts`; do not add a script tag for it\n- Made-up data only; never read project data\n- No network, no external fonts or images',
      builtin_tools: [], custom_tools: [{ name: 'save_visual', description: 'Save one option as HTML for the panel.' }], mcp_servers: [], disallowed_tools: [], warnings: [] },
    { name: 'launchpad-pilot', display_name: 'Claude Code', role: 'pilot', purpose: 'building', builtin: true, model: 'sonnet', setup: 'project',
      description: 'A plain Claude Code chat with the standard tools in the connected folder (the Claude Code side of the chat screen).',
      instructions: '', prompt_note: "Uses Claude Code's own prompt and tools: this file has no body of its own.",
      builtin_tools: null, custom_tools: [], mcp_servers: [], disallowed_tools: [], warnings: [] },
    { name: 'launchpad-planner', display_name: 'Planner', role: 'planner', purpose: 'planning', builtin: true, model: 'sonnet', source_path: agentPath('planner'),
      promotion: { start_model: 'sonnet', target_model: 'opus', window_turns: 2, criteria_path: PROMOTION_PATH,
        criteria: '## Promote to Opus when\n- the work has **three or more outputs** or crosses teams\n- there is a sign-off point or a data-quality risk\n- the user asks for depth\n\n## Stay on Sonnet when\n- it is a small, single-output change\n- the user wants a quick draft' },
      description: 'Interviews the user in rounds and writes the plan file. Never builds anything itself.',
      instructions: `# Planner\n\nYou help the user plan one piece of work. You **never** build anything yourself.\n\n## How you work\n- Interview in rounds of at most 3 questions, each with a recommended answer and a one-line reason\n- Use \`ask_user\` for every question; never ask in plain text\n- Send the Explorer (\`explore\`) for any file lookup\n- When the done checklist is complete, or the user says "draft now", write the plan with \`write_plan\`\n\n## Done checklist\n| Item | Required |\n|---|---|\n| Goal | yes |\n| Audience | yes |\n| Inputs and outputs | yes |\n| Done criteria per step | yes |\n| Sign-off points | if any |\n\n## Plan format\n\`\`\`\n# <name>\nstatus: draft\nsteps:\n  1. <title> | skill | depends on\n\`\`\`\n\n> Never output raw HTML such as <script> tags; write plain markdown only.`,
      builtin_tools: [], custom_tools: [{ name: 'ask_user', description: 'Ask the user up to 3 questions, each with options and a recommended answer. Parks the turn until answered.' },
        { name: 'explore', description: 'Send the Explorer to look something up in the project files. Returns a summary of at most 300 words.' },
        { name: 'save_note', description: 'Append a decision and its reason to the interview notes.' }, { name: 'write_plan', description: 'Validate the plan header and save plan.md.' }],
      mcp_servers: [], disallowed_tools: [], warnings: [] },
    { name: 'launchpad-orchestrator', display_name: 'Orchestrator', role: 'orchestrator', purpose: 'building', builtin: true, model: 'sonnet',
      description: 'Runs an approved plan one step at a time, starting the Builder or the agent the plan names for each step, and asking the user through the queue.',
      instructions: '# Orchestrator\n\nRun the approved plan **one step at a time**.\n\n1. Read `plan.md` and the interview notes\n2. For each step: write a brief, start a builder with `run_builder`, wait for its report\n3. Mark the step with `update_step` (done, blocked or failed) and list what was built\n4. Stop at every sign-off point and ask the user with `ask_user` (blocking)\n5. When all steps are done, write the final report\n\nNever edit project files yourself.',
      builtin_tools: ['Read', 'Glob', 'Grep'], custom_tools: [{ name: 'run_builder', description: 'Start a builder agent on one plan step with a brief; returns its step report.' },
        { name: 'update_step', description: 'Set a step status and record built files and the step report path.' }, { name: 'ask_user', description: 'Ask the user through the Incoming queue.' }],
      mcp_servers: [], disallowed_tools: ['Bash', 'Write', 'Edit'], warnings: [] },
    { name: 'launchpad-astronaut', display_name: 'Explorer', role: 'astronaut', purpose: 'exploring', builtin: true, model: 'haiku',
      description: 'Quick read-only file lookups for the Planner and the Orchestrator.',
      instructions: 'You look things up in the project files and answer in at most 300 words, as bullets. Read-only: you never change anything.',
      builtin_tools: ['Read', 'Glob', 'Grep'], custom_tools: [], mcp_servers: [], disallowed_tools: [], warnings: [] },
    { name: 'launchpad-builder', display_name: 'Builder', role: 'builder', purpose: 'building', builtin: true, model: 'sonnet',
      description: 'Builds one plan step from a brief: code, SQL or documents, inside the session folder.',
      instructions: '# Builder\n\nBuild exactly one plan step from the brief you are given.\n\n- Stay inside the session folder\n- Ask with `ask_user` when a choice changes the result; give your recommendation\n- Finish with `report_step`: what you built (file paths), what you decided, anything unfinished',
      builtin_tools: ['Read', 'Write', 'Edit', 'Bash', 'Glob', 'Grep'], custom_tools: [{ name: 'ask_user', description: 'Ask the user a question; timed unless the brief marks it blocking.' }, { name: 'report_step', description: 'Write the step report and end the step.' }],
      mcp_servers: [{ name: 'databricks', config: { command: 'python', args: ['-m', 'dbx_mcp', '--read-only'], env: { DATABRICKS_HOST: '${DATABRICKS_HOST}' } } }],
      disallowed_tools: ['WebFetch', 'WebSearch'], warnings: [] },
  ];
}
