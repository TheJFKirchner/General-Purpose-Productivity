import './controls.css';
import { toCsv, toCsvBook, saveText } from '../behaviors/toCsv.js';

// Small download button. Give either columns + rows (one table) or sheets = [{ name, columns, rows }] (several tables in one file)
export function CsvButton({ filename = 'data.csv', columns, rows, sheets, children }) {
  return <button type="button" className="jt-mini" onClick={() => saveText(filename, sheets ? toCsvBook(sheets) : toCsv(columns, rows))}>{children ?? (sheets ? 'Download all' : 'CSV')}</button>;
}
