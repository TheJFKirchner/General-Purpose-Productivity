// Commentary: the optional commentary.json in the dashboard folder (written by the commentary skill).
//   [{ "id": "C1", "commentary": ["...", "..."], "source": "...", "filters": { "region": "East" } }, ...]
// One id per unit; each filter scenario repeats the id with its own "filters" (column: value). A section names one
// id (meta.commentary). Matching is exact: an item shows only when its "filters" equal the filters set to something
// other than All among those that reach the section. No "filters" = shown only when none is set. No match: nothing.
// The file is read at build time, so an export carries it too; in npm run dev an edit shows on save.
import { ALL } from './source.js';

const found = import.meta.glob('../../commentary.json', { eager: true, import: 'default' });
const raw = Object.values(found)[0];
const list = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : [];
export const ITEMS = list.filter((it) => it && typeof it.id === 'string' && Array.isArray(it.commentary));

const setOnly = (filters) =>
  Object.fromEntries(Object.entries(filters ?? {}).filter(([, v]) => String(v) !== ALL).map(([k, v]) => [k, String(v)]));
const same = (a, b) => Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([k, v]) => b[k] === v);

/** id = the section's meta.commentary; values = filter choices by name; filterMeta = { name: { column, label } };
 *  reaching = names of the filters that reach the section.
 *  -> { item (or null), hasItems (the id exists), covered: [labels of the columns its items are written for] } */
export function commentaryFor(id, values = {}, filterMeta = {}, reaching = []) {
  const items = id ? ITEMS.filter((it) => it.id === id) : [];
  const active = {};
  for (const name of reaching) {
    const v = values[name];
    if (v !== undefined && v !== ALL) active[filterMeta[name]?.column ?? name] = String(v);
  }
  const labelOf = Object.fromEntries(Object.entries(filterMeta).map(([n, f]) => [f?.column ?? n, f?.label ?? n]));
  const covered = [...new Set(items.flatMap((it) => Object.keys(setOnly(it.filters))))].map((c) => labelOf[c] ?? c);
  return { item: items.find((it) => same(setOnly(it.filters), active)) ?? null, hasItems: items.length > 0, covered };
}
