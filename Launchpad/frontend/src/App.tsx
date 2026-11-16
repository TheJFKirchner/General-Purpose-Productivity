/* App shell: header + tab views + the right-hand aside + the visuals panel slot, and the page-wide overlays
   (modal, pen editor, settings, folder menu, tooltip, toasts). Each screen lives in src/views/<Name>/. The "plan" tab
   is the chat screen (views/Chat): the Planner / Claude Code switch over both conversations. */
import { useEffect, type ReactNode } from 'react';
import { sel, useComputed, useLaunchpad, type View } from './store';
import { DirMenu, ModalHost, TipHost, Toasts } from './components';
import { Header, panelId, tabId } from './components/Header';
import ChatScreen from './views/Chat/Chat';
import Missions from './views/Missions/Missions';
import Crew from './views/Crew/Crew';
import Files from './views/Files/Files';
import EditorModal from './views/Files/EditorModal';
import Aside from './views/Aside/Aside';
import VisualsPanel from './views/Visuals/Visuals';
import SettingsModal from './views/Settings/Settings';

export default function App() {
  const view = useLaunchpad(st => st.ui.view);
  const { waiting, visOpen } = useComputed(st => ({ waiting: sel.openCount(st), visOpen: sel.visShown(st) }));
  const editorDirty = useLaunchpad(st => st.editor.open && st.editor.dirty);

  /* page title counts what needs you; body classes drive the vanilla CSS (v-missions swaps orbit for the feed) */
  useEffect(() => { document.title = waiting ? `(${waiting}) Launchpad · COSMO` : 'Launchpad · COSMO'; }, [waiting]);
  useEffect(() => { document.body.classList.toggle('v-missions', view === 'missions'); }, [view]);
  useEffect(() => { document.body.classList.toggle('vis-open', visOpen); }, [visOpen]);
  useEffect(() => {
    if (!editorDirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [editorDirty]);

  return (
    <>
      <div className="app">
        <Header />
        <main>
          {/* every view stays mounted (typed text, scroll and local state survive a tab switch, as in the vanilla
              page); .view-slot is display:contents, so each view's <section class="view card"> is main's flex child */}
          <Slot v="plan" view={view}><ChatScreen /></Slot>
          <Slot v="missions" view={view}><Missions /></Slot>
          <Slot v="crew" view={view}><Crew /></Slot>
          <Slot v="files" view={view}><Files /></Slot>
          <Aside />
          <VisualsPanel />
        </main>
      </div>
      <ModalHost />
      <EditorModal />
      <SettingsModal />
      <DirMenu />
      <TipHost />
      <Toasts />
    </>
  );
}

/** One tab's panel (role=tabpanel, labelled by its tab in the header). */
function Slot({ v, view, children }: { v: View; view: View; children: ReactNode }) {
  return <div className="view-slot" role="tabpanel" id={panelId(v)} aria-labelledby={tabId(v)} hidden={view !== v}>{children}</div>;
}
