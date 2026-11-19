import { Component, useState } from 'react';
import { ALL, useFilters } from '../Filters/FilterContext.jsx';
import Select from '../Controls/Select.jsx';
import { useSection } from '../Lib/useSection.js';
import { commentaryFor } from '../Lib/commentary.js';
import Commentary from './Commentary.jsx';
import Note from './Note.jsx';
import DataOrigin from './DataOrigin.jsx';
import { dataOrigin } from '../Lib/origin.js';

class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return <div className="section-error">This section failed to render: {this.state.error.message}</div>;
  }
}

/** The frame around one section: asks the Analysis server (or an export's precomputed results) for the section's
 *  { data, metrics } at the current filters, then shows its note, the section body and its commentary.
 *  info = meta.cards[id] from the server: { filters, tables }. filters = this section's own filters (config
 *  "section": "<id>"), drawn in its header: [{ name, label, options }]. filterMeta = every fast filter (name ->
 *  { column, label }). A filter that is set but doesn't reach this section shows as a tag ("Region: all").
 *  inspect: { meta, reportFilters } adds an "About this data" button. */
export default function SectionFrame({ module, info, filters = [], filterMeta = {}, version, note, showCommentary = true, half, inspect }) {
  const { meta } = module;
  const { values, setFilter } = useFilters();
  const [aboutOpen, setAboutOpen] = useState(false);
  const filterNames = info?.filters ?? [];
  const { result, loading } = useSection(meta.id, filterNames, values, version);
  const calm = result?.notIncluded || result?.noData;
  const failed = result?.error;
  const match = showCommentary ? commentaryFor(meta.commentary, values, filterMeta, filterNames) : null;
  const ignored = Object.keys(filterMeta).filter((n) => values[n] !== undefined && values[n] !== ALL && !filterNames.includes(n));

  return (
    <section className={`section${half ? ' half' : ''}${loading && result ? ' refreshing' : ''}`} id={meta.id}>
      <header className="section-head">
        <h2>{meta.title}</h2>
        {ignored.map((n) => (
          <span key={n} className="scope-tag" title={`${filterMeta[n].label} does not narrow this section`}>{filterMeta[n].label}: all</span>
        ))}
        {filters.length > 0 && (
          <div className="section-filters">
            {filters.map((f) => (
              <Select key={f.name} label={f.label} value={values[f.name]} options={f.options} onChange={(v) => setFilter(f.name, v)} />
            ))}
          </div>
        )}
        {inspect && (
          <button type="button" className={`about-btn${aboutOpen ? ' on' : ''}`} aria-expanded={aboutOpen} onClick={() => setAboutOpen((o) => !o)} title="Where this data comes from">
            About this data
          </button>
        )}
      </header>
      {inspect && aboutOpen && <DataOrigin origin={dataOrigin(meta.id, inspect.meta, values, inspect.reportFilters)} />}
      {!result && loading && <div className="section-loading" aria-busy="true">Loading…</div>}
      {failed && <div className={calm ? 'section-note' : 'section-error'}>{calm ? result.error : `Analysis failed: ${result.error}`}</div>}
      <ErrorBoundary>
        {note && result && !failed && <Note markdown={note} metrics={result.metrics} />}
        {result && !failed && <module.default data={result.data} metrics={result.metrics} filters={values} />}
        {match && <Commentary match={match} />}
      </ErrorBoundary>
    </section>
  );
}
