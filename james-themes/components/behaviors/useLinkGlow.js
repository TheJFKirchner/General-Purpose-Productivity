import { useState } from 'react';

// Shared hover state linking a LedgerTable and a PlanSplit (or any pair keyed by row name).
// const [active, setActive] = useLinkGlow();
// <PlanSplit active={active} onActive={setActive} ... />  <LedgerTable active={active} onActive={setActive} ... />
export function useLinkGlow() {
  return useState(null);
}
