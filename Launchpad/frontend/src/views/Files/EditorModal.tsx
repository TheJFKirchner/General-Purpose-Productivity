/* The pen editor modal (#edScrim), opened by any <PenButton> through actions.openEditor. Side-by-side / text-only /
   preview-only (remembered), apply + validation notes, conflict-safe save (load theirs / overwrite), validation and
   error banners, previous versions with restore, Esc closes (asks once when dirty), Ctrl+S saves.
   Vanilla source: prototype/launchpad-orbit.html HTML 784-792; JS 3227-3322. File text reaches the DOM only as
   textarea value, escaped text, or through <Markdown> (escape-first). */
import { useEffect, useRef, useState } from 'react';
import { actions, getState, sel, useComputed, useLaunchpad, type EditorBanner, type EditorPane } from '../../store';
import { fmtBytes, fmtTime } from '../../lib/format';
import { Loading, Markdown } from '../../components';
import { Dialog, DialogTitle } from '../../components/Dialog';
import { AlertTriangle, Check, History, Info } from '../../components/icons';

const PANES: [EditorPane, string][] = [['side', 'Side by side'], ['edit', 'Text only'], ['preview', 'Preview only']];
const ERR_TITLE: Record<string, string> = { not_allowed: 'Not allowed', not_found: 'File not found', too_large: 'Too large', binary: 'Not a text file' };

export default function EditorModal() {
  const ed = useLaunchpad(st => st.editor);
  const where = useComputed(st => (st.editor.open ? `${sel.rootLabel(st, st.editor.root)} / ${st.editor.path}` : ''));
  const textRef = useRef<HTMLTextAreaElement>(null);
  const [prev, setPrev] = useState('');
  const [armed, setArmed] = useState<Record<string, true>>({});

  /* preview follows the text, 120 ms after the last change */
  useEffect(() => {
    if (!ed.open) { setPrev(''); return; }
    if (ed.pane === 'edit') return;
    const t = setTimeout(() => setPrev(ed.text), 120);
    return () => clearTimeout(t);
  }, [ed.open, ed.text, ed.pane]);

  /* the file arrived (or was reloaded): focus the text when it can be edited */
  useEffect(() => {
    if (ed.open && !ed.waiting && ed.editable) textRef.current?.focus();
  }, [ed.open, ed.waiting, ed.editable]);

  /* "Drop my changes and restore?" arms reset whenever the list is shown again */
  useEffect(() => { setArmed({}); }, [ed.backupsShown, ed.backups]);

  /* Esc closes (asks once when there are unsaved changes), Ctrl+S / Cmd+S saves; ahead of every other key handler */
  useEffect(() => {
    if (!ed.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (!getState().editor.open) return;
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); actions.editorClose(false); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); actions.editorSave(); }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [ed.open]);

  const restore = (id: string) => {
    if (ed.dirty && !armed[id]) { setArmed(a => ({ ...a, [id]: true })); return; }
    actions.editorRestore(id);
  };

  return (
    <Dialog open={ed.open} onRequestClose={() => actions.editorClose(false)} scrimId="edScrim" className="ed"
      initialFocus={() => textRef.current?.focus()} onEscape={e => e.preventDefault() /* Esc is handled above (asks once when dirty) */}>
      {ed.open && (<>
          <div className="ed-head">
            <div><DialogTitle asChild><h2 id="edTitle">Edit · {ed.title}</h2></DialogTitle><div className="ed-path" id="edPath">{where}</div></div>
            <div className="seg" id="edPrevSeg" role="group" aria-label="Preview">
              {PANES.map(([v, label]) => <button key={v} type="button" aria-pressed={ed.pane === v} onClick={() => actions.editorSetPane(v)}>{label}</button>)}
            </div>
          </div>
          <div className="ed-notes" id="edNotes">
            {ed.applies === 'new_sessions' ? <span className="chip warnc">Changes apply to new sessions only</span> : null}
            {ed.applies === 'now' ? <span className="chip ok">Changes apply right away</span> : null}
            {ed.validates === 'agent' ? <span className="chip">Checked as an agent definition before saving</span> : null}
            {ed.validates === 'plan' ? <span className="chip">Checked as a plan file before saving</span> : null}
          </div>
          {ed.banner ? <Banner b={ed.banner} conflict={ed.conflict} /> : null}
          <div className={`ed-panes ${ed.pane}`} id="edPanes">
            <label className="sr" htmlFor="edText">Markdown text</label>
            <textarea id="edText" ref={textRef} spellCheck={false} value={ed.text} readOnly={ed.waiting || !ed.editable}
              onChange={e => actions.editorSetText(e.target.value)} />
            <Markdown text={prev} doc className="ed-prev" id="edPrev" label="Preview" />
          </div>
          {ed.backupsShown ? (
            <div className="ed-backups" id="edBackups">
              {ed.backups == null ? <Loading>Loading previous versions…</Loading>
                : ed.backups.length ? <>
                  <div className="mut">Previous versions (saved before each change). Restoring replaces the file; the current version is backed up first.</div>
                  {ed.backups.map(b => (
                    <div key={b.backup_id} className="bk">
                      <span>{fmtTime(b.saved_at)} · {fmtBytes(b.size)}</span>
                      <button className={`pill sm${armed[b.backup_id] ? ' danger' : ''}`} type="button" onClick={() => restore(b.backup_id)}>{armed[b.backup_id] ? 'Drop my changes and restore?' : 'Restore'}</button>
                    </div>
                  ))}
                </> : <p className="mut">No previous versions yet.</p>}
            </div>
          ) : null}
          <div className="ed-foot">
            <span className="ed-status" id="edStatus">{ed.status}</span>
            <button className="pill sm ghost" type="button" id="edVersions" aria-expanded={ed.backupsShown} onClick={() => actions.editorToggleBackups()}><History />Previous versions…</button>
            <button className={`pill ghost${ed.discardArm ? ' danger' : ''}`} type="button" id="edCancel" onClick={() => actions.editorClose(false)}>{ed.discardArm ? 'Discard changes?' : 'Cancel'}</button>
            <button className="pill primary" type="button" id="edSave" disabled={!ed.editable} onClick={() => actions.editorSave()}><Check />Save</button>
          </div>
      </>)}
    </Dialog>
  );
}

function Banner({ b, conflict }: { b: EditorBanner; conflict: { text: string; version: string | number } | null }) {
  let body;
  if (b.kind === 'conflict') {
    body = <>
      <div><b>This file changed on disk since you opened it.</b> {b.message} Your text is still here.</div>
      <div className="row">
        <button className="pill sm" type="button" disabled={!conflict} onClick={() => actions.editorLoadTheirs()}>Load the version on disk (drop mine)</button>
        <button className="pill sm danger" type="button" disabled={!conflict} onClick={() => actions.editorOverwrite()}>Overwrite it with mine</button>
      </div>
      {conflict ? <details><summary>Show the version on disk</summary><pre className="raw ed-theirs">{conflict.text || ''}</pre></details> : null}
    </>;
  } else if (b.kind === 'invalid') {
    body = b.code === 'invalid'
      ? <div><b>Not saved: the file did not pass the check.</b> {b.message}<br />Your text is kept; fix it and save again.</div>
      : <div><b>{ERR_TITLE[b.code] || 'Could not save'}.</b> {b.message}</div>;
  } else if (b.code === 'elsewhere') {
    body = <div><b>This file was just saved somewhere else.</b> Your changes are kept; saving will ask whether to load that version or overwrite it.</div>;
  } else if (b.code === 'viewonly') {
    body = <div><b>View-only.</b> {b.message || `Only markdown files can be edited here${b.fileKind ? ` (this one is ${b.fileKind})` : ''}.`}</div>;
  } else {
    body = <div>{b.message}</div>;
  }
  return <div className={`ed-banner ${b.kind}`} id="edBanner" role={b.kind === 'notice' ? 'status' : 'alert'}>{b.kind === 'notice' ? <Info className="ed-bic" /> : <AlertTriangle className="ed-bic" />}<div className="ed-bbody">{body}</div></div>;
}
