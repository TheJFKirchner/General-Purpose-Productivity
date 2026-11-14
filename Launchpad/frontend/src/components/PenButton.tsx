/* The pen next to any editable markdown file: opens the editor (store editor state; modal in views/Files). */
import { actions } from '../store';
import { Pencil } from './icons';

export function PenButton({ root, path, label = 'Edit' }: { root: string | null | undefined; path: string | null | undefined; label?: string }) {
  if (root == null || !path) return null;
  return (
    <button type="button" className="penbtn" title="Edit this markdown file"
      onClick={e => { e.preventDefault(); actions.openEditor(root, path); }}><Pencil />{label}</button>
  );
}
