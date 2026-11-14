/* Agent purpose marks: an icon per purpose (shape, not only colour) and the purpose tag (icon + label, coloured by
   the --purpose-* tokens through data-purpose). Used by Crew, plan cards and Missions. */
import type { ReactNode } from 'react';
import { PURPOSE_LABEL } from '../lib/labels';
import { AlertTriangle, Compass, Hammer, ShieldCheck, Telescope } from './icons';

export const PURPOSE_ICON: Record<string, ReactNode> = {
  planning: <Compass />, exploring: <Telescope />, building: <Hammer />, reviewing: <ShieldCheck />,
};

/** "Building" with its icon, in the purpose's colours. */
export function PurposeTag({ purpose, children, icon = true }: { purpose: string; children?: ReactNode; icon?: boolean }) {
  return <span className="ptag" data-purpose={purpose}>{icon ? PURPOSE_ICON[purpose] ?? null : null}{children ?? PURPOSE_LABEL[purpose] ?? purpose}</span>;
}

/** The agent on a plan step, shown when it is not the Builder, or when the Builder stands in for a named agent
    that is missing or broken (fallback: a coral chip with a warning icon, naming the agent that was asked for). */
export function StepAgent({ a, step }: { a: { name: string; label: string; purpose: string; fallback: boolean }; step?: string }) {
  const where = step ? `${step}: ` : '';
  if (a.fallback) {
    const asked = a.name || 'the named agent';
    return <span className="stepagent fallback" title={`${where}${asked} is not available here (missing, broken or not a step worker), so the ${a.label} runs this step`}>
      <AlertTriangle />{a.label}<span className="sa-was">instead of {asked}</span>
    </span>;
  }
  return <span className="stepagent" data-purpose={a.purpose} title={`${where}done by ${a.label} (${(PURPOSE_LABEL[a.purpose] || a.purpose).toLowerCase()} agent)`}>{PURPOSE_ICON[a.purpose] ?? null}{a.label}</span>;
}
