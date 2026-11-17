/* Demo data for undefined roles ("Used but not defined"): four made-up roles with their uses, and the case the
   Role Reviewer would write for each (frontend-dev -> keep, copy-editor -> not yet, data-migrator -> define,
   release-checker has one use so it is not listed). Same names as the zero-token server demo. */
import type { ReviewSection, ReviewTest, RoleCase, RoleDecision, RoleEntry, RoleUse, RunUsage } from '../contract';

const MIN = 60_000;
const iso = (ago: number): string => new Date(Date.now() - ago).toISOString();

const use = (k: number, ago: number, o: Partial<RoleUse> = {}): RoleUse => ({
  id: `u${k}-${ago}`, at: iso(ago), dir_id: 'd1', folder: 'claims-project', session_id: 'S-A', run: 1, step: k, title: `Step ${k}`,
  skills: [], outcome: 'done', questions: 0, assumptions: 0, timed_out: 0, sent_back: false, named_agent: false, ...o,
});

function entry(name: string, uses: RoleUse[], o: Partial<RoleEntry> = {}): RoleEntry {
  return {
    name, base_agent: 'Builder', purpose: 'building', skills: [...new Set(uses.flatMap(u => u.skills))], folders: [{ dir_id: 'd1', name: 'claims-project' }],
    uses_total: uses.length, first_used: uses[uses.length - 1].at, last_used: uses[0].at, samples: [], verdict: null, dismissed: false, last_review: null,
    uses, problems: uses.filter(u => u.outcome !== 'done' || u.sent_back).length,
    state: uses.length >= 2 ? 'listed' : 'few_uses', visible: uses.length >= 2, uses_to_list: Math.max(0, 2 - uses.length), resurfaced: false, reviewing: false, review_id: null,
    ...o,
  };
}

export const demoRoles = (): RoleEntry[] => [
  entry('data-migrator', [
    use(3, 9 * MIN, { skills: ['sql-style'], title: 'Move the readmission tables', outcome: 'failed', questions: 1, assumptions: 1 }),
    use(2, 95 * MIN, { skills: ['sql-style'], title: 'Port the loader schema' }),
    use(1, 300 * MIN, { skills: ['sql-style'], title: 'Map the old columns' })]),
  entry('frontend-dev', [
    use(4, 20 * MIN, { skills: ['claims-glossary'], title: 'Tidy the dashboard tab' }),
    use(3, 70 * MIN, { skills: ['claims-glossary'], title: 'Fix the chart legend' }),
    use(2, 160 * MIN, { skills: ['claims-glossary'], title: 'Align the filter bar', sent_back: true }),
    use(1, 400 * MIN, { skills: ['claims-glossary'], title: 'Rename the tabs' })]),
  entry('copy-editor', [
    use(3, 40 * MIN, { title: 'Edit the cover note' }),
    use(2, 220 * MIN, { title: 'Tighten the summary', outcome: 'blocked' }),
    use(1, 500 * MIN, { title: 'Proof the glossary' })]),
  entry('release-checker', [use(1, 30 * MIN, { title: 'Check the release notes' })]),
];

const usage = (cost: number, tokens: number): RunUsage => ({ tokens, cost, input_tokens: Math.round(tokens * 0.8), output_tokens: Math.round(tokens * 0.2), cache_read_tokens: 0, cache_write_tokens: 0 });
/** The drafting call's figures, shown with the draft. */
export const DEMO_DRAFT_USAGE: RunUsage = usage(0.0042, 4200);

const TEST_TITLE: Record<ReviewTest, string> = {
  value: 'Clear value', logic: 'Logic beyond the skill', history: 'Clear usage history', fixes: 'Mistakes or issues it would fix',
  independent: 'Independent view: is a subagent the right fix?',
};
const sec = (test: ReviewTest, finding: string, strength: ReviewSection['strength'], evidence: [string, string][]): ReviewSection =>
  ({ test, title: TEST_TITLE[test], finding, strength, evidence: evidence.map(([quote, source]) => ({ quote, source })) });

export function demoCase(role: string, reviewId: string, answer?: string): RoleCase {
  const base = { case_id: `${role}-${reviewId}`, review_id: reviewId, role, date: new Date().toISOString(), reviewer: { name: 'Role Reviewer', harness: 'claude', model: 'sonnet', label: 'Claude · Sonnet' }, decision: null, case_file: `${role}-${reviewId}.md` };
  if (role === 'frontend-dev') {
    return { ...base, uses_total: 4, uses_recorded: 4, opened: ['U4', 'U3', 'U2', 'U1'], missing: [], history_thin: false, skill_notes: '- Name the tab layout rules once (filter bar first, chart legend right)\n- List the colours the glossary allows\n- Say when to leave a tab alone', proposal: null, questions: [], usage: usage(0.0487, 18200),
      verdict: 'keep', reason: 'Every use leaned on the same skill and the instructions added little beyond it; the Builder with that skill covers it.',
      sections: [
        sec('value', 'The role names a real specialism, but the Builder handled each step unaided.', 'weak', [['Step 3: legend fixed in one pass', 'session S-A, step 3']]),
        sec('logic', 'No logic beyond what the claims-glossary skill already states.', 'none', []),
        sec('history', 'Four uses over two days, one sent back.', 'moderate', [['sent back after run 1', 'session S-A, run 1']]),
        sec('fixes', 'The sent-back step was a wording slip, not a recurring mistake.', 'weak', [['Align the filter bar: revised draft', 'session S-A, step 2']]),
        sec('independent', 'A separate agent would add a definition to maintain for no new behaviour.', 'moderate', [['Builder definition covers editing workbook tabs', 'app/agents/builder/agent.md']]),
      ] };
  }
  if (role === 'copy-editor') {
    return { ...base, uses_total: 3, uses_recorded: 3, opened: ['U3', 'U2', 'U1'], missing: [], history_thin: true, skill_notes: '', proposal: null, questions: [], usage: usage(0.0391, 14900),
      verdict: 'not_yet', reason: 'Three uses is thin, one was blocked for an unrelated permission, and nothing yet says the Builder cannot do it.',
      sections: [
        sec('value', 'Plausible value in a consistent house style, not yet shown.', 'weak', [['Edit the cover note', 'session S-A, step 3']]),
        sec('logic', 'The instructions repeat a style guide the planner pasted each time.', 'weak', [['"Use plain words; no passive voice"', 'sample step 1']]),
        sec('history', 'Three uses, one blocked.', 'weak', [['blocked on a permission card', 'session S-A, step 2']]),
        sec('fixes', 'No recorded mistake this role prevents.', 'none', []),
        sec('independent', 'Too little evidence for an independent view either way.', 'none', []),
      ] };
  }
  return { ...base, uses_total: 3, uses_recorded: 3, opened: ['U3', 'U2', 'U1'], missing: [], history_thin: false, skill_notes: '', usage: usage(0.0613, 21400),
    questions: [{ test: 'logic', question: 'Do you always want a row-count check before and after a move?', why: 'Two steps repeat it; the skill does not say it.', recommended: 'Yes', ...(answer ? { answer } : {}) }],
    proposal: { name: 'data-migrator', purpose: 'building', description: 'Moves tables between schemas and checks row counts before and after.', instructions: '- Count rows before and after every move\n- Stop and report when counts differ' },
    verdict: 'define', reason: 'The planner kept adding the same row-count rules the skill lacks, and the one failed use skipped them.',
    sections: [
      sec('value', 'A clear specialism: moving data safely between schemas.', 'strong', [['Port the loader schema', 'session S-A, step 2']]),
      sec('logic', `Row-count checks are needed on every move and are not in the skill${answer ? ` (you said: ${answer})` : ''}.`, 'strong', [['"Count rows before and after"', 'sample step 2']]),
      sec('history', 'Three uses, the latest failed.', 'moderate', [['failed after one question', 'session S-A, step 3']]),
      sec('fixes', 'The failed use moved a table without a count; the rule would have caught it.', 'strong', [['row counts differed by 412', 'session S-A, step 3']]),
      sec('independent', 'A defined agent that always counts is the right fix; a skill alone was already ignored once.', 'moderate', [['skill sql-style has no migration rules', 'skill sql-style']]),
    ] };
}

/** The decision a case recommends, for the demo's decide handler. */
export const demoVerdict = (role: string): RoleDecision => role === 'frontend-dev' ? 'keep' : role === 'copy-editor' ? 'not_yet' : 'define';
