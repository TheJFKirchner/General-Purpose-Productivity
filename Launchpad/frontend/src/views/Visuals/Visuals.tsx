/* The visuals sidecar panel: the planner's visual option sets, sliding over the right side of the Plan tab.
   Vanilla source: prototype/launchpad-orbit.html HTML 764-779; JS 2838-2972 (panel, cards, pick / tweak / retry,
   enlarge, drag to resize). The frames and their security model live in frames.ts / VisFrame.tsx.
   The panel stays mounted (hidden) while a set exists, so its frames are not reloaded when it closes and reopens,
   as in the vanilla page. The Plan header's "Visuals" reopen button and the chat's visual notes are the Plan view's. */
import { useEffect, useRef, useState, type FormEvent, type MouseEvent, type PointerEvent, type ReactNode } from 'react';
import './Visuals.css';
import { actions, sel, useCurrentSession, useLaunchpad } from '../../store';
import type { VisualOption } from '../../contract';
import type { VisualSet } from '../../store';
import { closeModal, openModal } from '../../components';
import { VisFrame } from './VisFrame';
import { DEFAULT_LIB, libName } from './frames';
import { Check, ChevronLeft, ChevronRight, Inbox, Loader2, Maximize2, RotateCw, X } from '../../components/icons';

const BLOCKED = 'Blocked: this option tried to load another page.';

export default function VisualsPanel() {
  const s = useCurrentSession();
  const set = useLaunchpad(sel.curVisSet);
  const shown = useLaunchpad(sel.visShown);
  const vis = useLaunchpad(st => st.ui.vis);
  const open = useLaunchpad(sel.openCount);
  const blocking = useLaunchpad(sel.anyBlocking);
  const panel = useRef<HTMLDivElement>(null);
  const drag = useRef<{ right: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  /* the Earlier / Later set tooltip goes away on a mouse click and stays away until the pointer leaves the button
     (a click focuses the button, and the shared tooltip shows on focus; a button that turns disabled gets no events) */
  const [navTipOff, setNavTipOff] = useState<'prev' | 'next' | null>(null);
  if (!s || !set) return null;
  const quietTip = (e: MouseEvent<HTMLButtonElement>, which: 'prev' | 'next') => {
    if (e.detail === 0) return;                    // keyboard: keep focus and its tooltip
    setNavTipOff(which);
    e.currentTarget.blur();                        // focusout hides the shared tooltip now
  };

  const sets = s.visualSets, k = sets.indexOf(set);
  const sideTitle = open ? `${open} card${open > 1 ? 's' : ''} in Incoming${blocking ? ', one is blocking a run' : ''}` : 'Show the orbit and Incoming';

  /* drag the left edge to resize */
  const onGripDown = (e: PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const main = (panel.current?.closest('main') || document.querySelector('main'))?.getBoundingClientRect();
    if (!main) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { right: main.right, width: main.width };
    setDragging(true);
  };
  const onGripMove = (e: PointerEvent<HTMLDivElement>) => {
    const m = drag.current; if (!m) return;
    actions.setVisWidth(Math.max(360, Math.min(m.right - 28 - e.clientX, m.width - 56 - 320)));
  };
  const onGripUp = () => { drag.current = null; setDragging(false); };

  return (
    <div className={`vis-panel card${vis.wide ? ' wide' : ''}${dragging ? ' dragging' : ''}`} id="visPanel" ref={panel} hidden={!shown}
      role="complementary" aria-label="Visual options from the planner" style={!vis.wide && vis.width ? { width: vis.width + 'px' } : undefined}>
      <div className="vis-grip" id="visGrip" title="Drag to resize" onPointerDown={onGripDown} onPointerMove={onGripMove} onPointerUp={onGripUp} onPointerCancel={onGripUp} />
      <div className="vis-head">
        <div className="vis-title"><h2>Visuals</h2><span className="fl-sum" id="visSetLbl">{sets.length > 1 ? `Set ${k + 1} of ${sets.length}` : ''}</span></div>
        <div className="vis-tools">
          <button className="pill sm ghost icon" type="button" id="visPrev" aria-label="Earlier set" data-tip={navTipOff === 'prev' ? undefined : 'text:Earlier set'} hidden={sets.length < 2} disabled={k <= 0}
            onClick={e => { quietTip(e, 'prev'); actions.visPrev(); }} onPointerLeave={() => setNavTipOff(null)}><ChevronLeft /></button>
          <button className="pill sm ghost icon" type="button" id="visNext" aria-label="Later set" data-tip={navTipOff === 'next' ? undefined : 'text:Later set'} hidden={sets.length < 2} disabled={k >= sets.length - 1}
            onClick={e => { quietTip(e, 'next'); actions.visNext(); }} onPointerLeave={() => setNavTipOff(null)}><ChevronRight /></button>
          <button className="pill sm" type="button" id="visWide" aria-pressed={vis.wide} onClick={() => actions.toggleVisWide()}>{vis.wide ? 'Narrow' : 'Wide'}</button>
          <button className="pill sm" type="button" id="visSide" title={sideTitle} onClick={() => actions.openVis(false)}>
            <Inbox />Incoming<span className={`badge${blocking ? ' urgent' : ''}`} id="visBadge" hidden={!open}>{open}</span>
          </button>
          <button className="pill sm ghost icon" type="button" id="visClose" aria-label="Close the visuals panel" data-tip="text:Close" onClick={() => actions.openVis(false)}><X /></button>
        </div>
      </div>
      <p className="vis-brief" id="visBrief">{set.brief || 'Design options'}</p>
      <div className="vis-grid" id="visGrid">
        {set.options.map(o => <VisCard key={`${s.id}|${set.set_id}|${o.id}`} sid={s.id} dir={s.dirId} set={set} o={o} />)}
      </div>
    </div>
  );
}

/** The library line of an option, the same for every library (ECharts included). Fallback: the server's "drawn in
    ECharts, styled like <library>" label; a drawn option with no script (palette, hero card, layout): "HTML and CSS";
    else "Drawn with <library>". Before the html arrives: only when a library was asked for. Tooltip: what the folder has. */
export function libLabel(set: Pick<VisualSet, 'library' | 'drawn_with' | 'libraries' | 'library_note'>, html?: string | null): { text: string; tip: string; fallback: boolean } | null {
  const tip = set.libraries && set.libraries.length ? `Available for this folder: ${set.libraries.map(libName).join(', ')}` : '';
  if (set.library_note) return { text: set.library_note.charAt(0).toUpperCase() + set.library_note.slice(1), tip, fallback: true };
  if (html && !/<script\b/i.test(html)) return { text: 'HTML and CSS', tip, fallback: false };
  if (!html && !set.library) return null;
  return { text: `Drawn with ${libName(set.drawn_with)}`, tip, fallback: false };
}

function VisCard({ sid, dir, set, o }: { sid: string; dir: string | null; set: VisualSet; o: VisualOption }) {
  const pending = set.pending[o.id];
  const lib = o.drawn_with || set.drawn_with || DEFAULT_LIB, label = libLabel(set, o.status === 'ready' ? o.html : null);
  const status = pending ? 'rendering' : o.status, picked = set.picked_id === o.id, ready = status === 'ready';
  /* blocked / script error belong to one version of the option's html; a revised option gets a fresh frame */
  const [blockedHtml, setBlockedHtml] = useState<string | null>(null);
  const [warn, setWarn] = useState<string | null>(null);
  const [tweak, setTweak] = useState('');
  const html = o.html || '';
  const stateText = picked ? 'Picked' : status === 'rendering' ? (pending === 'tweak' ? 'Revising…' : 'Rendering…') : status === 'failed' ? 'Failed' : '';
  /* while the option is not drawable its frame is gone; when it comes back it gets a fresh one (vanilla drops the record) */
  const drawable = ready && !!html;
  useEffect(() => { if (!drawable) setBlockedHtml(null); }, [drawable]);

  let frame: ReactNode;
  if (drawable) {
    frame = blockedHtml === html
      ? <div className="vo-frame"><div className="vo-ph failed">{BLOCKED}</div></div>
      : <VisFrame className="vo-frame" html={html} lib={lib} dir={dir} onFresh={() => setWarn(null)} onBlocked={() => setBlockedHtml(html)}
          onError={m => setWarn(`Script error inside this option: ${m}`)} />;
  } else if (status === 'failed') {
    frame = <div className="vo-frame"><div className="vo-ph failed"><b>This option failed to draw.</b>{o.error ? <span>{String(o.error).slice(0, 240)}</span> : null}</div></div>;
  } else {
    frame = <div className="vo-frame"><div className="vo-ph"><Loader2 className="spin" />{pending === 'tweak' ? 'Revising this option…' : 'The Visualizer is drawing this option…'}</div></div>;
  }

  const submitTweak = (e: FormEvent) => {
    e.preventDefault();
    const t = tweak.trim();
    if (t && actions.visTweak(sid, set.set_id, o.id, t)) setTweak('');
  };

  return (
    <article className={`vopt ${status}${picked ? ' picked' : ''}`} data-oid={o.id}>
      <div className="vo-top">
        <b className="vo-lbl">{o.label || `Option ${o.id}`}</b>
        <span className={`vo-state ${picked ? 'picked' : status}`}>{stateText}</span>
        <button className="pill xs ghost vo-big" type="button" title="Enlarge" disabled={!ready} onClick={() => visEnlarge(sid, dir, set, o)}><Maximize2 />Enlarge</button>
      </div>
      {label ? <p className={`vo-lib${label.fallback ? ' fallback' : ''}`} tabIndex={label.tip ? 0 : undefined} data-tip={label.tip ? `text:${label.tip}` : undefined}>{label.text}</p> : null}
      {frame}
      <p className="vo-warn" hidden={!warn}>{warn}</p>
      <div className="row vo-acts">
        <button className={`pill sm ${picked ? 'pickedbtn' : 'primary'} vo-pick`} type="button" title={picked ? 'Click to clear the pick' : 'Use this one'} disabled={!ready}
          onClick={() => actions.visPick(sid, set.set_id, picked ? null : o.id)}>{picked ? <><Check />Picked</> : 'Pick this'}</button>
        <button className="pill sm vo-retry" type="button" hidden={status !== 'failed'} onClick={() => actions.visRetry(sid, set.set_id, o.id)}><RotateCw />Retry</button>
      </div>
      <form className="other vo-tweak" onSubmit={submitTweak}>
        <label className="sr" htmlFor={`vt-${set.set_id}-${o.id}`}>Tweak this option</label>
        <input className="field" id={`vt-${set.set_id}-${o.id}`} placeholder="Tweak just this one, e.g. same but horizontal" value={tweak} disabled={!ready} onChange={e => setTweak(e.target.value)} />
        <button className="pill sm" type="submit" disabled={!ready}>Revise</button>
      </form>
    </article>
  );
}

/** The enlarge view: the same option in a fresh sandboxed frame inside the shared modal. */
function VisBig({ html, lib, dir }: { html: string; lib: string; dir: string | null }) {
  const [blocked, setBlocked] = useState(false);
  if (blocked) return <div className="vis-big"><div className="vo-ph failed">{BLOCKED}</div></div>;
  return <VisFrame className="vis-big" html={html} lib={lib} dir={dir} onBlocked={() => setBlocked(true)} />;
}

function visEnlarge(sid: string, dir: string | null, set: VisualSet, o: VisualOption) {
  if (!o.html) return;
  const picked = set.picked_id === o.id;
  const label = libLabel(set, o.html);
  openModal({
    title: o.label || 'Visual option',
    wide: true,
    meta: [set.brief, label && label.text, o.path].filter(Boolean).join(' · '),
    body: <VisBig html={o.html} lib={o.drawn_with || set.drawn_with || DEFAULT_LIB} dir={dir} />,
    actions: [{ label: picked ? 'Picked (clear)' : 'Pick this', icon: picked ? <Check /> : undefined, primary: !picked, onClick: () => { actions.visPick(sid, set.set_id, picked ? null : o.id); closeModal(); } }],
  });
}
