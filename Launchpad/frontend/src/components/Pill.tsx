/* The Orbit button (.pill). variant: default | primary | soft | ghost | danger | sugg | pickedbtn.
   size: md (40px) | sm (32px) | xs (26px). `icon` goes before the label; with an icon and no label the button is a
   round icon button (.icon) and must have an aria-label (add data-tip="text:..." for a hover label). */
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type PillVariant = 'default' | 'primary' | 'soft' | 'ghost' | 'danger' | 'sugg' | 'pickedbtn';

export interface PillProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: PillVariant;
  size?: 'md' | 'sm' | 'xs';
  icon?: ReactNode;
}

export function pillClass(variant: PillVariant = 'default', size: 'md' | 'sm' | 'xs' = 'md', extra = ''): string {
  return ['pill', variant !== 'default' ? variant : '', size !== 'md' ? size : '', extra].filter(Boolean).join(' ');
}

export function Pill({ variant = 'default', size = 'md', className = '', type = 'button', icon, children, ...rest }: PillProps) {
  const iconOnly = icon != null && (children == null || children === false);
  return <button type={type} className={pillClass(variant, size, [iconOnly ? 'icon' : '', className].filter(Boolean).join(' '))} {...rest}>{icon}{children}</button>;
}
