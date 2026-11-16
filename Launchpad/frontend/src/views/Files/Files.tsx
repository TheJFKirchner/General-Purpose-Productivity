/* File Explorer: connected folders + Launchpad's own files as a tree, and a file pane. Markdown shows formatted (or
   raw) with a pen to edit it; other text shows as plain text, read-only. Layout (open folders, selection, raw,
   collapsed, tree width) is remembered in localStorage by the store.
   Vanilla source: prototype/launchpad-orbit.html HTML 725-736; JS 3081-3192. The editor modal is EditorModal.tsx. */
import './Files.css';
import { useRef, type PointerEvent as RPointerEvent } from 'react';
import { actions, sel, useComputed, useLaunchpad, type FxState } from '../../store';
import type { DirEntry } from '../../contract';
import { Empty, Loading, Markdown, PenButton, ViewFrame } from '../../components';
import { AlertTriangle, ChevronDown, ChevronRight, File, FileText, Folder, FolderOpen, Pencil, RotateCw } from '../../components/icons';
import { baseName, fmtBytes, fmtTime } from '../../lib/format';

export default function Files() {
  const fx = useLaunchpad(st => st.fx);
  const hasSettings = useLaunchpad(st => !!st.settings);
  const roots = useComputed(st => (st.settings ? sel.fxRoots(st) : null));
  const wrapRef = useRef<HTMLDivElement>(null);
  const treeRef = useRef<HTMLDivElement>(null);

  /* drag the grip: the tree follows the pointer; the width is stored (and persisted) on release */
  const onGrip = (e: RPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    const g = e.currentTarget, wrap = wrapRef.current, tree = treeRef.current; if (!wrap || !tree) return;
    const r = wrap.getBoundingClientRect(), left = r.left, max = r.width * .6;
    let w = fx.width;
    g.setPointerCapture(e.pointerId);
    const mv = (ev: PointerEvent) => { w = Math.round(Math.max(180, Math.min(max, ev.clientX - left))); tree.style.width = w + 'px'; };
    const up = () => { g.removeEventListener('pointermove', mv); g.removeEventListener('pointerup', up); actions.setFxWidth(w); };
    g.addEventListener('pointermove', mv); g.addEventListener('pointerup', up);
  };

  return (
    <ViewFrame id="viewFiles" label="File explorer" title="Files" bodyClass={null}
      sub="Connected folders and Launchpad's own files. Markdown files have a pen to edit them; everything else is view‑only."
      tools={<div className="row">
        <button className="pill sm" type="button" id="fxToggle" onClick={() => actions.toggleFxCollapsed()}>{fx.collapsed ? 'Show folders' : 'Hide folders'}</button>
        <button className="pill sm" type="button" id="fxRefresh" onClick={() => actions.fxRefresh()}><RotateCw />Refresh</button>
      </div>}>
      <div className={`fx-wrap${fx.collapsed ? ' collapsed' : ''}`} id="fxWrap" ref={wrapRef}>
        <div className="fx-tree" id="fxTree" role="tree" aria-label="Folders" ref={treeRef} style={{ width: fx.width + 'px' }}>
          {!hasSettings || !roots ? <div className="fx-note"><Loading>Loading folders…</Loading></div> : (
            <ul>
              {roots.map(r => {
                const open = fx.open.includes(sel.fxKey(r.root, ''));
                return (
                  <li key={r.root} className="fx-rootli">
                    <div className="fx-root-row">
                      <button type="button" className={`fx-node fx-root${r.exists ? '' : ' missing'}`} aria-expanded={open} title={r.full} onClick={() => actions.fxToggle(r.root, '')}>
                        <span className="tw">{open ? <ChevronDown /> : <ChevronRight />}</span>{open ? <FolderOpen className="fi" /> : <Folder className="fi" />}<span className="nm">{r.name}</span>
                        {r.isDefault ? <span className="k">Primary</span> : r.isAdditional ? <span className="k">Additional</span> : null}{r.exists ? null : <span className="k">missing</span>}
                      </button>
                      {r.app || !r.exists ? null : <button type="button" className="pill xs ghost" title="Open this folder's .launchpad session folders" onClick={() => actions.fxOpenPath(r.root, '.launchpad')}>Sessions</button>}
                    </div>
                    {open ? <FxChildren fx={fx} root={r.root} path="" /> : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className="fx-grip" id="fxGrip" title="Drag to resize" onPointerDown={onGrip} />
        <div className="fx-file" id="fxFile"><FilePane fx={fx} /></div>
      </div>
    </ViewFrame>
  );
}

function FxChildren({ fx, root, path }: { fx: FxState; root: string; path: string }) {
  const k = sel.fxKey(root, path), list = fx.cache[k];
  if (fx.err[k] != null) return <div className="fx-note err"><AlertTriangle />{fx.err[k]}</div>;
  if (!list) return <div className="fx-note"><Loading /></div>;
  if (!list.length) return <div className="fx-note">Empty folder</div>;
  return <ul>{list.map(e => <FxEntry key={e.name} fx={fx} root={root} path={path} e={e} />)}</ul>;
}

function FxEntry({ fx, root, path, e }: { fx: FxState; root: string; path: string; e: DirEntry }) {
  const p = path ? path + '/' + e.name : e.name;
  if (e.type === 'dir') {
    const open = fx.open.includes(sel.fxKey(root, p));
    return (
      <li>
        <button type="button" className="fx-node" aria-expanded={open} onClick={() => actions.fxToggle(root, p)}>
          <span className="tw">{open ? <ChevronDown /> : <ChevronRight />}</span>{open ? <FolderOpen className="fi" /> : <Folder className="fi" />}<span className="nm">{e.name}</span>{e.name === '.launchpad' ? <span className="k">sessions</span> : null}
        </button>
        {open ? <FxChildren fx={fx} root={root} path={p} /> : null}
      </li>
    );
  }
  const selected = !!fx.sel && fx.sel.root === root && fx.sel.path === p;
  const kind = e.kind === 'markdown' ? 'md' : e.kind === 'text' ? 'txt' : e.kind === 'too_large' ? 'big' : e.kind === 'binary' ? 'bin' : '';
  return (
    <li>
      <button type="button" className={`fx-node file ${e.kind || ''}`} aria-selected={selected} title={`${p}${e.size != null ? ' · ' + fmtBytes(e.size) : ''}`} onClick={() => actions.fxSelect(root, p)}>
        <span className="tw" />{e.kind === 'markdown' || e.kind === 'text' ? <FileText className="fi" /> : <File className="fi" />}<span className="nm">{e.name}</span><span className="k">{kind}{e.editable ? <Pencil aria-label="editable" /> : null}</span>
      </button>
    </li>
  );
}

function FilePane({ fx }: { fx: FxState }) {
  const s = fx.sel;
  const f = useLaunchpad(st => (s ? st.files[sel.fxKey(s.root, s.path)] : undefined));
  const where = useComputed(st => (s ? sel.rootLabel(st, s.root) : ''));
  if (!s) {
    return <Empty icon={<FileText />} title="Pick a file">Markdown files show formatted, with a pen to edit them. Other text files are shown as plain text, read-only. Each connected folder has a Sessions shortcut to its past plans, flight logs and reports.</Empty>;
  }
  const { root, path } = s;
  const file = f && !('error' in f) ? f : null, err = f && 'error' in f ? f.error : null;
  let body;
  if (!f) body = <Loading />;
  else if (err != null) body = <div className="warn"><b className="warn-h"><AlertTriangle />Could not open this file</b>{err}</div>;
  else if (file!.kind === 'binary') body = <Empty icon={<File />} title="Binary file">Not shown here.</Empty>;
  else if (file!.kind === 'too_large') body = <Empty icon={<File />} title="Too large to show">{fmtBytes(file!.size)}. Open it in another program.</Empty>;
  else if (file!.kind === 'markdown' && !fx.raw) body = <div className="prompt"><Markdown doc text={file!.text || ''} /></div>;
  else body = <div className="prompt"><pre className="raw">{file!.text || ''}</pre></div>;
  return <>
    <div className="fx-head">
      <h2>{baseName(path)}</h2>
      {file && file.kind === 'markdown' ? (
        <div className="seg" role="group" aria-label="View">
          <button type="button" aria-pressed={!fx.raw} onClick={() => actions.setFxRaw(false)}>Formatted</button>
          <button type="button" aria-pressed={fx.raw} onClick={() => actions.setFxRaw(true)}>Raw</button>
        </div>
      ) : null}
      {file && file.editable && file.kind === 'markdown' ? <PenButton root={root} path={path} /> : null}
      <button type="button" className="pill xs ghost" onClick={() => actions.fxSelect(root, path)}><RotateCw />Reload</button>
    </div>
    <div className="fx-meta">
      <code>{where} / {path}</code>
      {file ? ` · ${fmtBytes(file.size)}${file.mtime != null ? ' · modified ' + fmtTime(file.mtime) : ''}${file.editable ? '' : ' · view-only'}${file.applies === 'new_sessions' ? ' · edits apply to new sessions only' : ''}` : null}
    </div>
    {body}
  </>;
}
