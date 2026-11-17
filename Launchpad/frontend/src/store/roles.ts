/* Undefined roles (the Crew tab's "Used but not defined" list and the Role Reviewer's case): the server-event
   handlers (roles_list, review_*) used by reducer.ts. The list and the case are the server's; nothing is decided
   or added up here. One review state per role, so the screen survives the role leaving the list. */
import type {
  ReviewCaseEvent, ReviewDecidedEvent, ReviewFailedEvent, ReviewProgressEvent, ReviewRefusedEvent, ReviewStartedEvent, RolesListEvent,
} from '../contract';
import type { Ctx } from './core';
import type { RoleReview } from './types';

const PROGRESS_KEEP = 8;

export const newReview = (role: string): RoleReview => ({
  role, reviewId: null, status: 'starting', model: '', progress: [], phase: '', case: null, error: null, deciding: null, decided: null, saved: null,
});

/** The review state for a role (created on first use). */
export function reviewOf(c: Ctx, role: string): RoleReview {
  if (!c.st.reviews[role]) c.st.reviews[role] = newReview(role);
  return c.st.reviews[role];
}

export function onRolesList(c: Ctx, ev: RolesListEvent): void {
  const entries = Array.isArray(ev.entries) ? ev.entries : [];
  c.st.roles = { loaded: true, threshold: ev.threshold ?? c.st.roles.threshold, resurface: ev.resurface_uses ?? c.st.roles.resurface, entries };
  /* a review already running (this page was reloaded): show it as running */
  for (const e of entries) {
    if (!e.reviewing) continue;
    const r = reviewOf(c, e.name);
    if (r.status !== 'running' && r.status !== 'starting') { Object.assign(r, newReview(e.name), { status: 'running' as const }); }
    if (e.review_id) r.reviewId = e.review_id;
  }
}

export function onReviewStarted(c: Ctx, ev: ReviewStartedEvent): void {
  const r = reviewOf(c, ev.role);
  Object.assign(r, newReview(ev.role), { status: 'running' as const, reviewId: ev.review_id, model: ev.model || '' });
}

export function onReviewProgress(c: Ctx, ev: ReviewProgressEvent): void {
  const r = reviewOf(c, ev.role);
  if (r.status === 'starting') r.status = 'running';
  if (ev.review_id) r.reviewId = ev.review_id;
  r.phase = ev.phase;
  if (ev.text && r.progress[r.progress.length - 1] !== ev.text) r.progress = [...r.progress, ev.text].slice(-PROGRESS_KEEP);
}

export function onReviewCase(c: Ctx, ev: ReviewCaseEvent): void {
  const r = reviewOf(c, ev.role);
  r.status = 'case'; r.reviewId = ev.review_id; r.case = ev.case; r.error = null; r.deciding = null;
  const d = ev.case && ev.case.decision;                      // a replay of a case the user already decided
  r.decided = d ? { decision: d.decision, reviewerVerdict: ev.case.verdict } : null;
}

export function onReviewFailed(c: Ctx, ev: ReviewFailedEvent): void {
  const r = reviewOf(c, ev.role);
  r.status = 'failed'; r.error = ev.error || 'The review could not finish.';
}

export function onReviewRefused(c: Ctx, ev: ReviewRefusedEvent): void {
  const r = reviewOf(c, ev.role);
  /* "already running": keep showing the running review; any other refusal is a plain message */
  if (ev.review_id) { r.status = 'running'; r.reviewId = ev.review_id; return; }
  r.status = 'refused'; r.error = ev.error || 'This role cannot be reviewed now.';
}

export function onReviewDecided(c: Ctx, ev: ReviewDecidedEvent): void {
  const r = reviewOf(c, ev.role);
  r.deciding = null;
  r.decided = { decision: ev.decision, reviewerVerdict: ev.reviewer_verdict };
}
