/* Chat log pieces shared by the planner chat (Plan), the Claude Code chat and the read-only archive. */
import { useId, useState, type ReactNode } from 'react';
import { Markdown } from './Markdown';
import { ChevronDown, ClipboardList } from './icons';

/** Long user text is shown folded, with "Show all" (a pasted log or plan would otherwise fill the chat). */
const isLong = (t: string) => t.length > 700 || t.split('\n').length > 12;

/** One message: "me" = the user's plain text (never markdown); "bot" = model text as safe markdown.
    plan = the plan sent from the Planner (its label): a folded, formatted plan instead of a plain bubble. */
export function ChatBubble({ who, text, streaming = false, plan }: { who: 'me' | 'bot'; text: string; streaming?: boolean; plan?: string }) {
  if (plan) return <PlanBubble label={plan} text={text} />;
  if (who === 'me') return isLong(text) ? <Folded className="bubble me long" text={text}>{text}</Folded> : <div className="bubble me">{text}</div>;
  return <Markdown text={text} className={`bubble bot${streaming ? ' streaming' : ''}`} />;
}

function Folded({ className, text, children, label = 'Show all' }: { className: string; text: string; children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <div className={`${className}${open ? ' open' : ''}`}>
      <div className="fold-body" id={id}>{children}</div>
      <button type="button" className="fold-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <ChevronDown />{open ? 'Show less' : `${label} (${text.split('\n').length} lines)`}
      </button>
    </div>
  );
}

/** The plan sent to Claude Code as its first message: a labelled, formatted plan, folded to its first lines. */
function PlanBubble({ label, text }: { label: string; text: string }) {
  return (
    <Folded className="bubble me planmsg" text={text} label="Show the whole plan">
      <span className="planmsg-h"><ClipboardList />{label}</span>
      <Markdown doc text={text} className="planmsg-md" />
    </Folded>
  );
}

/** A grey centred system line (.sys); cls promo | err | visnote. */
export function SysLine({ text, cls, children }: { text: string; cls?: string; children?: ReactNode }) {
  return <div className={`sys${cls ? ' ' + cls : ''}`}>{text}{children}</div>;
}

/** The three typing dots. */
export function TypingDots({ label = 'Planner is typing' }: { label?: string }) {
  return <div className="typing" aria-label={label}><i /><i /><i /></div>;
}
