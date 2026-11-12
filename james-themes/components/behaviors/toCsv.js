// columns = [{ key, label }]; rows = [{ key: value }]. Raw values, not formatted ones.
const cell = (v) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
export const toCsv = (columns, rows) => [columns.map((c) => cell(c.label)).join(','), ...rows.map((r) => columns.map((c) => cell(r[c.key])).join(','))].join('\n');
// sheets = [{ name, columns, rows }] -> one file, a titled block per sheet
export const toCsvBook = (sheets) => sheets.map((s) => cell(s.name) + '\n' + toCsv(s.columns, s.rows)).join('\n\n');
export function saveText(filename, text, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob(['\uFEFF' + text], { type })), a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
