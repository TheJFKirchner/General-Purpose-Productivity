/* Cards and the standard view frame. */
import type { HTMLAttributes, ReactNode } from 'react';

/** White rounded card (.card). */
export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`card${className ? ' ' + className : ''}`} {...rest} />;
}

/** A tab's frame: <section class="view card"> with the standard header (.vhead: h1, a line under it, tools on the right).
    Missions, Crew and Files use this look; the chat screen's Planner and Claude Code panes have their own chat header (.chat-head). */
export function ViewFrame({ id, label, title, sub, tools, children, bodyClass = 'vbody' }: {
  id: string; label: string; title: ReactNode; sub?: ReactNode; tools?: ReactNode; children?: ReactNode; bodyClass?: string | null;
}) {
  return (
    <section className="view card" id={id} aria-label={label}>
      <div className="vhead">
        <div><h1>{title}</h1>{sub != null && <p>{sub}</p>}</div>
        {tools}
      </div>
      {bodyClass ? <div className={bodyClass}>{children}</div> : children}
    </section>
  );
}
