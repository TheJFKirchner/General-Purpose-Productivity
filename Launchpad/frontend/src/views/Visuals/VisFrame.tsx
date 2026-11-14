/* One sandboxed option frame inside a box element. The iframe is made imperatively (frames.ts) into a host div that
   React never renders children into, so the frame is never moved, re-attached or reloaded by a re-render. A new `html`
   (a revised option) or library gets a fresh frame; unmounting removes it.
   - Height: the frame reports its content height (clamped in frames.ts); the iframe becomes that tall, never shorter
     than the box's CSS min-height, so the whole drawing shows with no inner scrollbar
   - Loading: a spinner covers the box until the frame reports ready (big libraries take seconds to parse) */
import { useEffect, useRef, useState } from 'react';
import { createVisFrame, DEFAULT_LIB } from './frames';
import { Loader2 } from '../../components/icons';

export function VisFrame({ html, lib = DEFAULT_LIB, dir, className, onBlocked, onError, onFresh }: {
  html: string;
  /** the option's drawn_with: the only library inlined into the frame */
  lib?: string;
  /** the session's folder (dir_id): where an installed library (Plotly, Bokeh) is looked up */
  dir?: string | null;
  className: string;
  onBlocked: () => void;
  onError?: (msg: string) => void;
  /** called each time a fresh frame is made (the card hides its old script-error line) */
  onFresh?: () => void;
}) {
  const outer = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const cbs = useRef({ onBlocked, onError, onFresh });
  cbs.current = { onBlocked, onError, onFresh };
  useEffect(() => {
    const el = host.current; if (!el) return;
    cbs.current.onFresh?.();
    setLoading(true);
    let fr: ReturnType<typeof createVisFrame> | null = null;
    let base: number | null = null;              // the iframe's CSS height (248px in a card, 62vh enlarged)
    const onSize = (h: number) => {
      if (!fr) return;
      if (base == null) base = parseFloat(getComputedStyle(fr.iframe).height) || 0;
      fr.iframe.style.height = Math.max(base, h) + 'px';
    };
    fr = createVisFrame(html, {
      onBlocked: () => { setLoading(false); cbs.current.onBlocked(); },
      onError: m => cbs.current.onError?.(m),
      onSize,
      onReady: () => setLoading(false),
    }, lib, dir);
    el.appendChild(fr.iframe);
    base = parseFloat(getComputedStyle(fr.iframe).height) || null;
    return fr.dispose;
  }, [html, lib, dir]);
  return (
    <div className={`${className} vf`} ref={outer} aria-busy={loading}>
      <div className="vf-host" ref={host} />
      {loading ? <div className="vo-loading" role="status"><Loader2 className="spin" />Drawing this option…</div> : null}
    </div>
  );
}
