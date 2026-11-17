/* The Settings view (the header's Settings button, a fifth full view beside Plan, Missions, Crew and Files).
   Sections in order: Connections (Connections.tsx), MCP library (McpLibrary.tsx), Working directories (add by path or
   Browse…, make primary, two-click remove) and the server's general settings (sent when a field is left or Enter is
   pressed). Vanilla source of the last two: prototype/launchpad-orbit.html JS 2990-3063 (+ SET_LABEL in src/lib/labels.ts). */
import './Settings.css';
import { useEffect, useRef, useState } from 'react';
import { actions, useLaunchpad } from '../../store';
import type { Directory } from '../../contract';
import { baseName } from '../../lib/format';
import { SET_LABEL } from '../../lib/labels';
import { Loading, ViewFrame } from '../../components';
import { Folder, FolderOpen, Info, Plus } from '../../components/icons';
import { Connections } from './Connections';
import { McpLibrary } from './McpLibrary';

export default function SettingsView() {
  const settings = useLaunchpad(st => st.settings);
  const msg = useLaunchpad(st => st.ui.settingsMsg);
  const addPath = useLaunchpad(st => st.ui.settingsAddPath);

  const vals = (settings && settings.values) || {};
  const names = Object.keys(vals);

  return (
    <ViewFrame id="viewSettings" label="Settings" title="Settings" sub="Connections, MCP servers, connected folders, timers and models for this launch" bodyClass={null}>
      <div className="set-page">
        <div className="setbody" id="setBody">
          {msg ? <div className="warn setmsg" id="setMsg" role="status"><Info />{msg}</div> : null}
          <Connections />
          <McpLibrary />
          <section className="set-sec">
            <h3><Folder />Working directories</h3>
            <p className="mut set-hint">Sessions and CLI chats run in the primary folder (New plan and New chat let you pick another). Folders ticked as additional are given to every new session and chat too: agents may work there, and skills are found there.</p>
            <div id="setDirs"><Dirs dirs={settings ? settings.directories : null} /></div>
            <form className="other set-add" id="setAdd" onSubmit={e => { e.preventDefault(); actions.addDirectory(addPath); }}>
              <label className="sr" htmlFor="setAddPath">Folder path</label>
              <input className="field" id="setAddPath" placeholder="Type or paste a folder path, e.g. C:\work\my-project" value={addPath} onChange={e => actions.setSettingsAddPath(e.target.value)} />
              <button className="pill sm primary" type="submit"><Plus />Add</button>
              <button className="pill sm" type="button" id="setBrowse" hidden={!(settings && settings.can_pick)} onClick={() => actions.pickDirectory()}><FolderOpen />Browse…</button>
            </form>
          </section>
          <section className="set-sec">
            <h3>Settings</h3>
            <div id="setVals">
              {names.length ? <>
                {names.map(name => <SettingRow key={name} name={name} v={vals[name]} />)}
                <p className="mut set-hint">Changes are sent when you leave a field or press Enter. A value set by a launch option can only be changed by starting Launchpad without that option.</p>
              </> : settings ? <p className="mut">The server sent no settings.</p> : <Loading />}
            </div>
          </section>
        </div>
      </div>
    </ViewFrame>
  );
}

/** Connected folders. Remove takes a second click within 4 s; it is off for a busy folder or the last one. */
function Dirs({ dirs }: { dirs: Directory[] | null }) {
  const [arm, setArm] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  if (!dirs) return <Loading />;
  if (!dirs.length) return <p className="mut">No folders connected yet.</p>;
  const remove = (id: string) => {
    if (timer.current) clearTimeout(timer.current);
    if (arm !== id) { setArm(id); timer.current = setTimeout(() => setArm(null), 4000); return; }
    setArm(null); actions.removeDirectory(id);
  };
  return <>{dirs.map(d => {
    const only = dirs.length === 1, armed = arm === d.dir_id;
    return (
      <div key={d.dir_id} className={`dirrow${d.exists === false ? ' missing' : ''}${d.busy ? ' busy' : ''}`}>
        <div className="dr-main">
          <b>{d.name || baseName(d.path)}</b>
          {d.is_default ? <span className="chip ok" title="New sessions and chats run here unless the folder menu picks another">Primary</span> : null}
          {d.is_additional && !d.is_default ? <span className="chip">Additional</span> : null}
          {d.exists === false ? <span className="chip warnc">Missing on disk</span> : null}
          {d.busy ? <span className="chip">In use by a running session</span> : null}
          <code>{d.path}</code>
        </div>
        <div className="row">
          {d.is_default ? null : (
            <label className="dr-add" title="Also give new sessions and chats this folder (beside the primary)">
              <input type="checkbox" checked={!!d.is_additional} disabled={d.exists === false} onChange={e => actions.setAdditionalDir(d.dir_id, e.target.checked)} />
              Additional
            </label>
          )}
          {d.is_default ? null : <button className="pill xs" type="button" onClick={() => actions.makeDefaultDir(d.dir_id)}>Make primary</button>}
          <button className={`pill xs${armed ? ' danger' : ' ghost'}`} type="button" disabled={!!d.busy || only} onClick={() => remove(d.dir_id)}
            title={d.busy ? 'A running session uses this folder' : only ? 'At least one folder must stay connected' : 'Disconnect this folder (nothing is deleted)'}>
            {armed ? 'Confirm remove' : 'Remove'}
          </button>
        </div>
      </div>
    );
  })}</>;
}

/** One setting: checkbox for booleans, number or text input otherwise. Sent on the native change event (leaving the
    field or Enter), as in the vanilla page; the field follows new values from the server. */
function SettingRow({ name, v }: { name: string; v: unknown }) {
  const o = v && typeof v === 'object' && 'value' in (v as object) ? v as { value: unknown; applies?: string; overridden_by_launch?: boolean | string } : null;
  const val = o ? o.value : v, over = o ? o.overridden_by_launch : undefined, applies = o ? o.applies : undefined;
  const kind = typeof val === 'boolean' ? 'bool' : typeof val === 'number' ? 'num' : 'str';
  const id = 'set-' + name.replace(/[^\w-]/g, '_');
  const ref = useRef<HTMLInputElement>(null);
  const harnessOpts = useLaunchpad(st => (name === 'pilot_harness' ? st.cliChoice : name === 'planner_harness' ? st.plannerChoice : null)?.options);

  useEffect(() => {
    const i = ref.current; if (!i) return;
    if (kind === 'bool') i.checked = !!val; else i.value = String(val ?? '');
  }, [val, kind]);

  useEffect(() => {
    const i = ref.current; if (!i) return;
    const onChange = () => {
      const x = kind === 'bool' ? i.checked : kind === 'num' ? Number(i.value) : i.value.trim();
      if (kind === 'num' && !isFinite(x as number)) { actions.toast('Please enter a number'); return; }
      actions.setSetting(name, x);
    };
    i.addEventListener('change', onChange);
    return () => i.removeEventListener('change', onChange);
  }, [name, kind]);

  const label = SET_LABEL[name] || name.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());
  if (harnessOpts && harnessOpts.length) {
    /* a CLI setting reads as the pickers show it (the CLI's display label), not as its raw id */
    const hs: { harness: string; label: string; ok: boolean }[] = [];
    for (const o of harnessOpts) { const h = hs.find(x => x.harness === o.harness); if (!h) hs.push({ harness: o.harness, label: o.harness_label || o.harness, ok: o.available }); else if (o.available) h.ok = true; }
    const cur = String(val ?? '');
    return (
      <div className="setrow">
        <label htmlFor={id}>{label}</label>
        <select id={id} className="field" value={cur} disabled={!!over} onChange={e => actions.setSetting(name, e.target.value)}>
          {cur && !hs.some(h => h.harness === cur) ? <option value={cur}>{cur}</option> : null}
          {hs.map(h => <option key={h.harness} value={h.harness} disabled={!h.ok}>{h.label}{h.ok ? '' : ' (not available yet)'}</option>)}
        </select>
        <span className={`chip ${applies === 'now' ? 'ok' : ''}`}>{applies === 'now' ? 'Applies now' : applies === 'new_sessions' ? 'New sessions only' : ''}</span>
        {over ? <span className="chip warnc" title={typeof over === 'string' ? over : 'A launch option overrides this'}>Set by launch option{typeof over === 'string' ? ': ' + over : ''}</span> : null}
      </div>
    );
  }
  return (
    <div className="setrow">
      <label htmlFor={id}>{label}</label>
      {kind === 'bool'
        ? <input type="checkbox" id={id} ref={ref} defaultChecked={!!val} disabled={!!over} />
        : <input id={id} ref={ref} type={kind === 'num' ? 'number' : 'text'} step={kind === 'num' ? 'any' : undefined} defaultValue={String(val ?? '')} disabled={!!over} />}
      <span className={`chip ${applies === 'now' ? 'ok' : ''}`}>{applies === 'now' ? 'Applies now' : applies === 'new_sessions' ? 'New sessions only' : ''}</span>
      {over ? <span className="chip warnc" title={typeof over === 'string' ? over : 'A launch option overrides this'}>Set by launch option{typeof over === 'string' ? ': ' + over : ''}</span> : null}
    </div>
  );
}
