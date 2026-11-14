/* Initial state (the File Explorer layout and the editor pane come back from localStorage). */
import type { AppState, CrewForm, EditorPane, EditorState, FxState } from './types';
import type { AgentFields } from '../contract';
import { LS_EDITOR_VIEW, LS_FILES, lsGet } from '../lib/storage';

export const emptyAgentFields = (): AgentFields => ({ name: '', description: '', purpose: '', model: 'sonnet', tools: [], instructions: '' });

export function initialCrewForm(): CrewForm {
  return { open: false, fields: emptyAgentFields(), problems: [], error: null, saving: false, draftText: '', drafting: false, draftError: null, drafted: false };
}

export function initialEditor(pane?: EditorPane): EditorState {
  return {
    open: false, root: '', path: '', title: '', version: null, text: '', text0: '', dirty: false, waiting: false, saving: false,
    restoring: false, editable: true, applies: null, validates: null, discardArm: false, conflict: null, banner: null, status: '',
    pane: pane || lsGet<EditorPane>(LS_EDITOR_VIEW, 'side'), backupsShown: false, backups: null,
  };
}

function initialFx(): FxState {
  const saved = lsGet<Partial<FxState>>(LS_FILES, {});
  return {
    cache: {}, loading: {}, err: {},
    open: Array.isArray(saved.open) ? saved.open : [],
    sel: saved.sel && typeof saved.sel === 'object' ? saved.sel : null,
    raw: !!saved.raw, collapsed: !!saved.collapsed, width: +(saved.width ?? 0) || 300, booted: false,
  };
}

export function initialState(): AppState {
  return {
    seq: 0,
    ui: {
      view: 'plan', chatSide: 'planner', conn: { text: 'Demo mode', color: 'var(--green)' }, demo: true,
      queueFilter: 'all', feedRun: '', feedAgent: '', hov: null, sel: null, focus: null, focusScroll: false,
      stopConfirm: null, apConfirm: null, pmConfirm: null, newPlanBusy: false, newChatBusy: false,
      vis: { open: false, wide: false, width: 0 },
      settingsOpen: false, settingsMsg: null, settingsAdding: null, settingsAddPath: '', picking: false,
      dirMenu: null, toasts: [],
    },
    replaying: false, quiet: false,
    sessions: {}, order: [], current: null, preLog: [], preTyping: false, preName: '', preRoundTag: '', rounds: {},
    agents: {}, tokens: 0, cost: 0, usageEv: null, usageFromServer: false, acts: [], lastAct: {},
    queue: [],
    chats: {}, chatOrder: [], currentChat: null, chatPending: null, codeModePref: null, chatFromPlan: null, chatItems: {},
    crewDefs: null, crewLoading: false, crewDirId: null, crewDirPick: null, toolChoices: [], crewUses: {}, crewForm: initialCrewForm(),
    crewRemoving: null, crewError: null, crewFlash: null,
    settings: null, fx: initialFx(), files: {}, editor: initialEditor(),
  };
}
