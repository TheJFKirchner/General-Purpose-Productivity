/* Toasts (bottom centre). Raise one with actions.toast(text); they leave after 2.8 s. Silent while state.quiet. */
import { useLaunchpad } from '../store';
import { Info } from './icons';

export function Toasts() {
  const toasts = useLaunchpad(st => st.ui.toasts);
  return <div className="toasts" role="status" aria-live="polite">{toasts.map(t => <div key={t.id} className="toast"><Info />{t.text}</div>)}</div>;
}
