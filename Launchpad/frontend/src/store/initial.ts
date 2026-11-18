/* Initial state (the File Explorer layout and the editor pane come back from localStorage). */
import type { AppState, CrewForm, EditorPane, EditorState, FxState, GitState } from './types';
import type { AgentFields } from '../contract';
import { LS_EDITOR_VIEW, LS_FILES, lsGet } from '../lib/storage';

const emptyAgentFields = (): AgentFields => ({ name: '', description: '', purpose: '', model: 'sonnet', tools: [], instructions: '' });

export function initialCrewForm(): CrewForm {
  return { open: false, fields: emptyAgentFields(), problems: [], error: null, saving: false, draftText: '', drafting: false, draftError: null, drafted: false, role: null, cost: null };
}

export function initialEditor(pane?: EditorPane): EditorState {
  return {
    open: false, root: '', path: '', title: '', version: null, text: '', text0: '', dirty: false, waiting: false, saving: false,
    restoring: false, editable: true, applies: null, validates: null, discardArm: false, conflict: null, banner: null, status: '',
    pane: pane || lsGet<EditorPane>(LS_EDITOR_VIEW, 'side'), backupsShown: false, backups: null,
  };
}

export function initialGit(): GitState {
  return { available: null, loaded: false, scanning: false, repos: [], busy: {}, error: {}, note: {}, unticked: {}, message: {}, open: {} };
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
      stopConfirm: null, apConfirm: null, pickerChoosing: null, cliChoosing: null, newPlanBusy: false, newChatBusy: false,
      vis: { open: false, wide: false, width: 0 },
      settingsMsg: null, settingsAdding: null, settingsAddPath: '', picking: false, pickFor: null, pickedOutput: null,
      dirMenu: null, toasts: [],
    },
    replaying: false, quiet: false,
    sessions: {}, order: [], current: null, preLog: [], preTyping: false, preName: '', preRoundTag: '', rounds: {}, plannerChoice: null, cliChoice: null,
    agents: {}, tokens: 0, cost: 0, usageEv: null, byRole: {}, chatTotals: {}, acts: [], lastAct: {},
    queue: [],
    chats: {}, chatOrder: [], currentChat: null, chatPending: null, codeModePref: null, chatFromPlan: null, chatItems: {},
    crewDefs: null, crewLoading: false, crewDirId: null, crewDirPick: null, toolChoices: [], crewSkills: [], crewUses: {},
 crewForm: initialCrewForm(),
    roles: { loaded: false, threshold: 2, resurface: 5, entries: [] }, reviews: {}, roleOpen: null,
    mcp: { loaded: false, servers: [], assignments: {}, connections: [], importSources: [], error: null }, connTests: {}, mcpImports: {},
    wf: { openReview: null, loaded: false, list: [], folders: [], agents: {}, reviewerName: '', runs: {}, latest: {}, error: null, runErrors: {} },
    crewRemoving: null, crewError: null, crewFlash: null,
    settings: null, fx: initialFx(), files: {}, editor: initialEditor(), git: initialGit(),
  };
}
