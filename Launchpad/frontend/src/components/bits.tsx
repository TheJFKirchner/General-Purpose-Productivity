/* Small shared display pieces (class names from the vanilla CSS in theme.css). */
import type { ReactNode } from 'react';
import { KIND_TAG, S_LABEL } from '../lib/labels';
import { CircleHelp, ClipboardList, FileText, Info, Loader2, ShieldAlert, UserCheck } from './icons';

const KIND_ICON: Record<string, ReactNode> = {
  question: <CircleHelp />, permission: <ShieldAlert />, info: <Info />, report: <FileText />, plan: <ClipboardList />, review: <UserCheck />,
};

/** Kind tag with its icon: Question / Permission / Update / Report / Plan (.tag.ques|perm|info). */
export function Tag({ kind, children }: { kind: string; children?: ReactNode }) {
  const t = KIND_TAG[kind] || { cls: 'info', text: kind };
  return <span className={`tag ${t.cls}`}>{KIND_ICON[kind] ?? null}{children ?? t.text}</span>;
}

/** Inline loading line: spinning icon + text (.loading). */
export function Loading({ children = 'Loading…' }: { children?: ReactNode }) {
  return <span className="loading" role="status"><Loader2 className="spin" />{children}</span>;
}

/** Neutral chip (.chip), e.g. "Run A"; variant ok | warnc | rev. */
export function Chip({ children, variant, title }: { children: ReactNode; variant?: 'ok' | 'warnc' | 'rev'; title?: string }) {
  return <span className={`chip${variant ? ' ' + variant : ''}`} title={title}>{children}</span>;
}

/** Session letter badge (.letter): wait = coral, done = green, off = grey. */
export function Letter({ children, state }: { children: ReactNode; state?: 'wait' | 'done' | 'off' | '' }) {
  return <span className={`letter${state ? ' ' + state : ''}`}>{children}</span>;
}

/** Run / step status chip (.status running|waiting|done|stopped|failed|blocked|in_progress). */
export function Status({ status, label }: { status: string; label?: string }) {
  return <span className={`status ${status}`}>{label ?? S_LABEL[status] ?? status}</span>;
}

/** Empty state (.empty): optional icon in a soft circle, bold title line, text. */
export function Empty({ title, children, card = false, icon, className = '', id, hidden }: { title?: ReactNode; children?: ReactNode; card?: boolean; icon?: ReactNode; className?: string; id?: string; hidden?: boolean }) {
  return (
    <div className={`empty${card ? ' card' : ''}${className ? ' ' + className : ''}`} id={id} hidden={hidden}>
      {icon ? <span className="empty-ic" aria-hidden="true">{icon}</span> : null}
      {title != null && <b>{title}</b>}{children}
    </div>
  );
}

/** Coral count badge (.badge); hidden at 0. */
export function Badge({ n, urgent = false }: { n: number; urgent?: boolean }) {
  if (!n) return null;
  return <span className={`badge${urgent ? ' urgent' : ''}`}>{n}</span>;
}

/** The planner's sun icon (.sunicon working|waiting|idle). */
export function SunIcon({ status }: { status: string }) {
  return <span className={`sunicon ${status}`} />;
}

/** Folder chip (.dirchip) with the full path as tooltip. */
export function DirChip({ label, path }: { label: string; path?: string }) {
  if (!label) return null;
  return <span className="dirchip" title={path || ''}>{label}</span>;
}
