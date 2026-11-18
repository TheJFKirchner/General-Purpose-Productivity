/* Workflows: the server-event handlers (workflows_list, workflow_run_state) used by reducer.ts. The list and every run
   are the server's; nothing is decided here. */
import type { WorkflowRunStateEvent, WorkflowsListEvent } from '../contract';
import { toast, type Ctx } from './core';

export function onWorkflowsList(c: Ctx, ev: WorkflowsListEvent): void {
  const w = c.st.wf;
  w.loaded = true;
  w.list = Array.isArray(ev.workflows) ? ev.workflows : [];
  w.folders = Array.isArray(ev.folders) ? ev.folders : [];
  w.agents = ev.agents && typeof ev.agents === 'object' ? ev.agents : {};
  w.reviewerName = typeof ev.reviewer_name === 'string' ? ev.reviewer_name : '';
  w.error = ev.error || null;
}

export function onWorkflowRunState(c: Ctx, ev: WorkflowRunStateEvent): void {
  const w = c.st.wf, run = ev.run, wid = run ? run.workflow_id : ev.workflow_id;
  if (wid) { if (ev.error) w.runErrors[wid] = ev.error; else delete w.runErrors[wid]; }
  if (ev.error && !c.st.replaying) toast(c, ev.error);
  if (!run || !run.id) return;
  w.runs[run.id] = run;
  /* the newest run of a workflow is the one its card shows */
  const cur = w.runs[w.latest[run.workflow_id]];
  if (!cur || cur.id === run.id || (run.started_at || '') >= (cur.started_at || '')) w.latest[run.workflow_id] = run.id;
}
