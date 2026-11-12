import { useState } from 'react';
import './layout.css';
import { SlabButton } from '../controls/SlabButton.jsx';
import { LedgerTable } from '../tables/LedgerTable.jsx';
import { CsvButton } from '../controls/CsvButton.jsx';
import { CommentaryNote } from './CommentaryNote.jsx';
import { SourceLine } from './SourceLine.jsx';

// finding = title stating the takeaway; measure = caption naming the measure
// optional: actions (SlabButtons), commentary (text), source (text), table = { columns, rows } -> adds a chart/table flip button (ViewFlip)
// download = { filename, sheets:[{ name, columns, rows }] } -> small "Download all" button at the top right of the section
export function FindingPanel({ finding, measure, actions, commentary, source, table, download, children }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className="jt-panel">
      <div className="jt-panelhead">
        <div><h2>{finding}</h2>{measure && <p className="cap">{measure}</p>}</div>
        {(actions || table || download) && <div className="jt-btnrow">{actions}{download && <CsvButton filename={download.filename} sheets={download.sheets} />}{table && <SlabButton kind="sec" onClick={() => setAsTable(!asTable)}>{asTable ? 'Show chart' : 'Show table'}</SlabButton>}</div>}
      </div>
      {table && asTable ? <LedgerTable columns={table.columns} rows={table.rows} csv={table.csv} /> : children}
      {commentary && <CommentaryNote>{commentary}</CommentaryNote>}
      {source && <SourceLine>{source}</SourceLine>}
    </section>
  );
}
