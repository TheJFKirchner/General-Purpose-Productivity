/* Model / file text as safe markdown. This is the ONLY component in the app that uses dangerouslySetInnerHTML,
   and it only ever passes the output of md() / docHtml() (src/lib/markdown.ts), which escapes everything first. */
import { useMemo, type ElementType } from 'react';
import { docHtml, md } from '../lib/markdown';

export interface MarkdownProps {
  text: string | null | undefined;
  /** true: documents with a YAML header (plan.md, agent files) get a tidy summary + step list */
  doc?: boolean;
  /** extra classes; "md" is always added */
  className?: string;
  as?: ElementType;
  title?: string;
  id?: string;
  /** accessible name (aria-label); with a label the box is a named region unless `role` says otherwise */
  label?: string;
  role?: string;
}

export function Markdown({ text, doc = false, className = '', as: Tag = 'div', title, id, label, role }: MarkdownProps) {
  const html = useMemo(() => (doc ? docHtml(text ?? '') : md(text ?? '')), [text, doc]);
  return <Tag className={`md${className ? ' ' + className : ''}`} title={title} id={id} aria-label={label}
    role={role ?? (label ? 'region' : undefined)} dangerouslySetInnerHTML={{ __html: html }} />;
}
