// Shading for pictorial visuals. t.ramp = four rgb stops, light -> dark
export function shade(t, v, lo, hi) {
  const k = Math.max(0, Math.min(0.999, (v - lo) / (hi - lo))) * 3, i = Math.floor(k), f = k - i, a = t.ramp[i], b = t.ramp[i + 1];
  return `rgb(${[0, 1, 2].map((j) => Math.round(a[j] + (b[j] - a[j]) * f)).join(',')})`;
}
// true when white text is needed on shade(t, v, lo, hi)
export const isDeep = (v, lo, hi) => (v - lo) / (hi - lo) > 0.36;
