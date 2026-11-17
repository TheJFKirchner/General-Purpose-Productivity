/* The chat screen's CLI side: a plain CLI chat in a connected folder (was the Free Flight tab).
   Vanilla source: prototype/launchpad-orbit.html HTML 672-698; JS 2429-2676.
   Streaming replies, tool calls as compact inline rows, permission / plan / question cards inline where they occur
   (never in Incoming, never timed). Modes: default (ask before edits) -> accept_edits -> plan -> default; Shift+Tab
   cycles, the server's chat_mode wins. Esc interrupts a running turn. Both keys only act while this side is showing.
   Under the box: the CLI-then-model picker (components/ModelPicker.tsx, sel.cliPickerView, actions.chooseCli).
   All chat state is in the store (chats, chatItems); this view only renders it and calls actions. It stays mounted
   when the switch shows the Planner, so a typed draft survives. */
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import './Code.css';
import { actions, getState, sel, useComputed, useLaunchpad } from '../../store';
import type { Activity, Chat, ChatItem, FlightEntry } from '../../store';
import { ChatBubble, Empty, isModalOpen, Markdown, ModelPicker, SysLine, TypingDots } from '../../components';
import { Check, ChevronsRight, Hand, Pause, Plus, Send, Square, Terminal } from '../../components/icons';
import type { ChatMode } from '../../contract';
import { MODE_HINT, MODE_LABEL } from '../../lib/labels';
import { cleanName, clock, toolCat, toolShort, tokShort, usd } from '../../lib/format';

const MODE_ICON: Record<ChatMode, ReactNode> = { default: <Hand />, accept_edits: <ChevronsRight />, plan: <Pause /> };

/** True when the CLI side of the chat screen is on screen. */
const codeShowing = () => { const st = getState(); return st.ui.view === 'plan' && st.ui.chatSide === 'code'; };

export default function Code() {
  const showing = useLaunchpad(st => st.ui.view === 'plan' && st.ui.chatSide === 'code');
  const chats = useLaunchpad(st => st.chats);
  const chatOrder = useLaunchpad(st => st.chatOrder);
  const currentChat = useLaunchpad(st => st.currentChat);
  const items = useLaunchpad(st => st.chatItems);
  const newChatBusy = useLaunchpad(st => st.ui.newChatBusy);
  const v = useComputed(st => {
    const c = sel.curChat(st), u = sel.chatUsage(st), dir = c ? sel.dirLabelOf(st, c.dirId, c.cwd) : '';
    return {
      c,
      name: sel.codeAgentName(st),
      mode: c ? c.mode : st.codeModePref || 'default',
      sub: c ? (dir ? `Chat in ${dir}` : 'Chat') : 'The CLI in a connected folder',
      cost: usd(u ? u.cost : 0),
      tok: u ? tokShort({ i: u.in, o: u.out, cr: u.cr, cw: u.cw }) : '0 tokens',
      tools: u ? u.tools : 0,
    };
  });
  const { c, mode } = v;
  const busy = !!(c && c.busy);

  const [text, setText] = useState('');
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modeRef = useRef<HTMLButtonElement>(null);
  const newRef = useRef<HTMLButtonElement>(null);

  /* keep the open chat scrolled to the newest line: new entries, streamed text, typing dots, another chat, back on this side */
  const last = c && c.log.length ? c.log[c.log.length - 1] : null;
  const scrollKey = c ? `${c.id}|${c.log.length}|${last && last.kind === 'bubble' ? last.text.length : ''}|${c.typing}` : '';
  useLayoutEffect(() => {
    const el = logRef.current; if (el && showing) el.scrollTop = el.scrollHeight;
  }, [scrollKey, showing]);

  /* textarea grows with its text, up to 160 px */
  const autoGrow = () => { const t = inputRef.current; if (!t) return; t.style.height = 'auto'; t.style.height = Math.min(160, t.scrollHeight) + 'px'; };
  useLayoutEffect(autoGrow, [text, showing]);

  /* Shift+Tab changes mode (focus in this chat), Esc stops a running turn; only on this side, not while a dialog is open */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const st = getState();
      if (!codeShowing() || isModalOpen() || st.ui.view === 'settings' || st.editor.open || st.crewForm.open) return;
      const ae = document.activeElement;
      const inChat = ae === document.body || ae === inputRef.current || ae === modeRef.current || !!(ae && logRef.current && logRef.current.contains(ae));
      const ch = sel.curChat(st);
      if (e.key === 'Tab' && e.shiftKey && inChat) { e.preventDefault(); actions.cycleMode(); }
      else if (e.key === 'Escape' && ch && ch.busy) { e.preventDefault(); actions.stopChat(); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const t = text.trim();
    if (t && actions.sendChat(t)) setText('');
  };
  const onInputKey = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
  };

  return (
    <div className="chat-pane" id="viewCode" aria-label="CLI chat">
      <div className="chat-head">
        <div>
          <small id="codeSub" title={c && c.cwd ? c.cwd : ''}>{v.sub}</small>
          <h1 id="codeName">{v.name}</h1>
        </div>
        <div className="head-tags">
          <div className="head-row">
            <button className="pill sm" type="button" id="newChat" ref={newRef} title="Start a fresh CLI chat" disabled={newChatBusy}
              onClick={() => actions.chooseDir(newRef.current, dirId => actions.newChat(dirId))}>{newChatBusy ? null : <Plus />}{newChatBusy ? 'Starting…' : 'New chat'}</button>
          </div>
          <span className="pcost" data-tip="chat" tabIndex={0}>This chat · <b>{v.cost}</b> · <span>{v.tok}</span> · <span>{`${v.tools} tool call${v.tools === 1 ? '' : 's'}`}</span></span>
        </div>
      </div>
      <div className="msgs" id="codeLog" aria-live="polite" ref={logRef}>
        <Empty id="codeEmpty" className="log-empty" icon={<Terminal />} title="CLI" hidden={currentChat != null}>
          A plain chat in the CLI harness, in the project folder: it behaves as the harness does in a terminal, with its standard tools and permission prompts. Type below to start, or send a plan here from the Planner.
        </Empty>
        {chatOrder.map(id => chats[id] ? <ChatLog key={id} chat={chats[id]} items={items} hidden={id !== currentChat} /> : null)}
      </div>
      <form className="composer code-comp" id="codeComposer" autoComplete="off" onSubmit={submit}>
        <button type="button" className="modepill" id="modePill" ref={modeRef} data-mode={mode} title={`${MODE_HINT[mode]}. Shift+Tab to change.`}
          onClick={() => actions.cycleMode()}>{MODE_ICON[mode]}<span>{MODE_LABEL[mode]}</span></button>
        <label htmlFor="codeInput" className="sr">Message the CLI</label>
        <textarea id="codeInput" ref={inputRef} rows={1} value={text} onChange={e => setText(e.target.value)} onKeyDown={onInputKey}
          placeholder={mode === 'plan' ? 'Ask for a plan' : 'Ask the CLI to do something'} />
        <button className="pill danger" type="button" id="codeStop" hidden={!busy} title="Interrupt the running turn (Esc)" onClick={() => actions.stopChat()}><Square />Stop</button>
        <button className="pill primary" type="submit"><Send />Send</button>
      </form>
      <CliPicker />
      <div className="code-hint"><kbd>Shift</kbd>+<kbd>Tab</kbd> changes mode · <kbd>Esc</kbd> stops a running turn · <kbd>Enter</kbd> sends, <kbd>Shift</kbd>+<kbd>Enter</kbd> adds a line</div>
    </div>
  );
}

/** The CLI chat's CLI-then-model picker under its box (the planner's picker without auto-promote and New plan). The
    open chat takes a choice at once until its first message; after that the choice is for the next new chat (noted). */
function CliPicker() {
  const v = useComputed(st => sel.cliPickerView(st));
  const chatId = useLaunchpad(st => st.currentChat);
  if (!v) return null;
  return <ModelPicker id="cpk" rowId="cliControls" view={v} who="CLI chat" resetKey={chatId} onPick={id => actions.chooseCli(id)} />;
}

/** One chat's log (every chat stays rendered, only the open one shows, so expanded tool rows survive). */
function ChatLog({ chat, items, hidden }: { chat: Chat; items: Record<string, ChatItem>; hidden: boolean }) {
  return (
    <div className="log" hidden={hidden}>
      {chat.log.map(e => <Entry key={e.id} e={e} items={items} />)}
      {chat.typing ? <TypingDots label="The CLI is working" /> : null}
    </div>
  );
}

function Entry({ e, items }: { e: FlightEntry; items: Record<string, ChatItem> }) {
  switch (e.kind) {
    case 'bubble': return <ChatBubble who={e.who} text={e.text} streaming={!!e.streaming} plan={e.plan} />;
    case 'sys': return <SysLine text={e.text} cls={e.cls} />;
    case 'tool': return <ToolRow a={e.act} />;
    case 'card': { const i = items[e.itemId]; return i ? <ChatCard i={i} /> : null; }
  }
}

/* tool calls as compact inline rows (also in the activity feed); <details> is left uncontrolled so an expanded row
   stays expanded when its status changes */
function ToolRow({ a }: { a: Activity }) {
  const status = a.status || '';
  const stt = status === 'started' ? <i className="live" title="running" /> : status === 'done' ? <Check aria-label="done" /> : status;
  return (
    <details className={`toolrow ${status}`}>
      <summary><span className={`tl ${toolCat(a.tool)}`} title={a.tool}>{toolShort(a.tool)}</span><span className="sm">{a.summary || ''}</span><span className="stt">{stt}</span></summary>
      <div className="tooldet">
        <div><b>Tool</b> <code>{a.tool}</code></div>
        {a.summary ? <div><b>Target</b> <code>{a.summary}</code></div> : null}
        <div className="mut">{[cleanName(a.name), status, clock(a.ts)].filter(Boolean).join(' · ')}</div>
      </div>
    </details>
  );
}

const TAG: Record<string, [string, string]> = { permission: ['perm', 'Permission'], plan: ['ques', 'Plan'], question: ['ques', 'Question'] };

/* inline cards: permission, plan, question. Same messages and settled labels as the vanilla chatCardEl. */
function ChatCard({ i }: { i: ChatItem }) {
  const open = i.ui === 'open';
  const noteRef = useRef<HTMLInputElement>(null);
  const [tagCls, tagText] = TAG[i.kind] || ['info', i.kind];
  const respond = actions.chatRespond;
  /* the card's own text box: read at click time (Deny sends it as a note) */
  const note = () => (noteRef.current ? noteRef.current.value.trim() : '');

  const onOther = (e: FormEvent) => {
    e.preventDefault(); if (!open) return;
    const val = note(); if (!val) return;
    if (i.kind === 'plan') respond(i.id, { decision: 'deny', message: val }, `Keep planning · “${val}”`);
    else if (i.kind === 'question') respond(i.id, { answer: val }, `You answered: ${val}`);
    else respond(i.id, { decision: 'deny', message: val }, `Denied · “${val}”`);
  };

  let body: ReactNode;
  if (i.kind === 'permission') {
    const sug = Array.isArray(i.suggestions) ? i.suggestions : [];
    const deny = () => { const n = note(); respond(i.id, n ? { decision: 'deny', message: n } : { decision: 'deny' }, n ? `Denied · “${n}”` : 'Denied'); };
    body = <>
      <h3>{i.title || `Allow ${i.tool || 'this tool'}?`}</h3>
      {i.body ? <pre className="cmd">{i.body}</pre> : null}
      {open ? <>
        <div className="row">
          <button className="pill" type="button" onClick={() => respond(i.id, { decision: 'allow' }, 'Allowed')}>Allow</button>
          {sug.length
            ? sug.map((s, k) => <button key={k} className="pill" type="button"
                onClick={() => respond(i.id, { decision: 'always', ...(s.remember ? { remember: s.remember } : {}) }, s.label || 'Always allowed')}>{s.label || 'Always allow'}</button>)
            : <button className="pill" type="button" onClick={() => respond(i.id, { decision: 'always' }, 'Always allowed')}>Always allow</button>}
          <button className="pill" type="button" onClick={deny}>Deny</button>
        </div>
        <form className="other" onSubmit={onOther}>
          <label className="sr" htmlFor={`dn-${i.id}`}>Optional note sent with Deny</label>
          <input id={`dn-${i.id}`} ref={noteRef} placeholder="Optional: tell the CLI what to do instead (sent with Deny)" />
        </form>
      </> : null}
    </>;
  } else if (i.kind === 'plan') {
    body = <>
      {i.title ? <h3>{i.title}</h3> : null}
      <Markdown doc className="mdbox" text={i.markdown ?? i.body ?? ''} />
      {open ? <>
        <div className="row">
          <button className="pill primary" type="button" onClick={() => respond(i.id, { decision: 'allow', mode: 'accept_edits' }, `Plan approved · continuing in ${MODE_LABEL.accept_edits}`)}>Approve · auto-accept edits</button>
          <button className="pill" type="button" onClick={() => respond(i.id, { decision: 'allow', mode: 'default' }, `Plan approved · continuing in ${MODE_LABEL.default}`)}>Approve · ask before edits</button>
        </div>
        <form className="other" onSubmit={onOther}>
          <label className="sr" htmlFor={`pf-${i.id}`}>What should change</label>
          <input id={`pf-${i.id}`} ref={noteRef} placeholder="Or say what to change and keep planning" />
          <button className="pill sm" type="submit">Keep planning</button>
        </form>
      </> : null}
    </>;
  } else {
    const opts = Array.isArray(i.options) ? i.options : [];
    body = <>
      <h3>{i.title || 'Question'}</h3>
      {i.body ? <Markdown className="qbody" text={i.body} /> : null}
      {open ? <>
        {opts.length ? <div className="row">{opts.map((o, k) => <button key={k} className="pill" type="button" onClick={() => respond(i.id, { answer: o }, `You chose: ${o}`)}>{o}</button>)}</div> : null}
        <form className="other" onSubmit={onOther}>
          <label className="sr" htmlFor={`cq-${i.id}`}>Your answer</label>
          <input id={`cq-${i.id}`} ref={noteRef} placeholder="Or type your own answer…" />
          <button className="pill sm" type="submit">Send</button>
        </form>
      </> : null}
    </>;
  }

  return (
    <div className={`ccard ${i.kind}${open ? '' : ' settled'}`}>
      <div className="cc-top"><span className={`tag ${tagCls}`}>{tagText}</span>{i.tool ? <span className="who"><code>{i.tool}</code></span> : null}</div>
      {body}
      {open ? null : <p className="settle"><b>{i.result || 'Answered'}</b></p>}
    </div>
  );
}
