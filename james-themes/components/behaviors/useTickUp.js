import { useEffect, useState } from 'react';

// Counts a number up to `target` (~800ms, ease-out, from 90%). Returns target at once if motion is off or reduced-motion is set.
export function useTickUp(target, motion = true, ms = 800) {
  const still = !motion || (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [v, setV] = useState(still ? target : target * 0.9);
  useEffect(() => {
    if (still) { setV(target); return undefined; }
    let raf, t0 = null; const from = target * 0.9;
    const step = (ts) => { if (t0 === null) t0 = ts; const k = Math.min(1, (ts - t0) / ms), e = 1 - Math.pow(1 - k, 3); setV(k < 1 ? from + (target - from) * e : target); if (k < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, still, ms]);
  return v;
}
