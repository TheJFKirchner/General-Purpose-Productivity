/* Small React hooks shared by the views. */
import { useEffect, useState } from 'react';

/** Re-render every `ms` milliseconds and return Date.now() (timers, "12s ago" ages, countdown bars). */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(t); }, [ms]);
  return now;
}

/** Call `fn` on every animation frame with (now, dt ms) while mounted. For the orbit / solar-system animations. */
export function useAnimationFrame(fn: (now: number, dt: number) => void): void {
  useEffect(() => {
    let raf = 0, last = 0, alive = true;
    const loop = (now: number) => {
      if (!alive) return;
      const dt = last ? Math.min(100, now - last) : 0; last = now;
      fn(now, dt);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { alive = false; cancelAnimationFrame(raf); };
  }, [fn]);
}
