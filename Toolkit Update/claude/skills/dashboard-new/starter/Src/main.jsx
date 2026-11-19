// Live dashboard entry: every section in the registry and its tabs (tabs are optional).
// A section's note is its `export const note` (text above the chart, live numbers as {metric|format}).
import * as registry from './Sections/index.js';
import { mount } from './App.jsx';

const sections = registry.default;
const tabs = registry.tabs ?? [];
const notes = Object.fromEntries(sections.filter((m) => typeof m.note === 'string' && m.note.trim()).map((m) => [m.meta.id, m.note.trim()]));

mount({ sections, tabs, notes });
