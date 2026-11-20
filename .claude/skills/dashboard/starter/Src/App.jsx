// Shared shell for both outputs:
//   dashboard mode (Src/main.jsx): every registered section, data from the Analysis server (/api); fast filters
//     recompute sections, slow parameters (e.g. "Data as of") re-run the pipeline after a confirmation
//   report mode (.export/entry.jsx): chosen sections, results precomputed for the report's filter combinations,
//     header + footer stamp, plus the report's own settings: theme overrides, hidden parts, a notice line, text tabs
// Tabs: sections with meta.tab are grouped under the tabs defined in Src/Sections/index.js.
// Filters sit at one of three levels: the whole dashboard, one tab, or one section (dashboard.config.json).
// The current tab and the reader's fast filter choices live in the URL hash (#tab=<id>&region=East), so links
// and reloads keep them, in exports too (Src/Lib/hash.js).
// Text above a section: its note (live numbers) and its commentary (commentary.json, by meta.commentary id).
import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import config from '../dashboard.config.json';
import { getMeta, getStatus, runPipeline } from './Lib/source.js';
import { applyTheme, setReportThemeOverrides } from './Lib/theme.js';
import { dataAsOf, daysBetween, todayIso } from './Lib/dates.js';
import { ALL, FilterProvider, useFilters } from './Filters/FilterContext.jsx';
import { readHash, writeHash } from './Lib/hash.js';
import FilterBar from './Controls/FilterBar.jsx';
import TabBar from './Controls/TabBar.jsx';
import SectionFrame from './Components/SectionFrame.jsx';
import ReportHeader from './Components/ReportHeader.jsx';
import ReportFooter from './Components/ReportFooter.jsx';
import './styles.css';
import './host.css'; // the design library's page styles for copied items (copied verbatim; never edited)
import './Lib/host-runtime.js'; // the design library's drawing rules for copied items (copied verbatim)
import './custom.css'; // looks-only overrides and page settings, hand-written; wins over styles.css

export function mount(props) {
  createRoot(document.getElementById('root')).render(<App {...props} />);
  // the page's real height, for npm run shot (it crops the screenshot to it)
  new ResizeObserver(() => { document.body.dataset.height = String(Math.ceil(document.body.getBoundingClientRect().height) + 16); }).observe(document.body);
}

const hashTab = () => readHash().tab ?? null;

/** Keeps the URL hash in step with the tab and the filter choices. `names` = filters the reader may change
 *  (locked report filters are never written or read); `valid(name, value)` = the value is one of its options.
 *  A hash edited by hand switches the tab and applies the filters it names, keeping the
 *  others. One listener handles both, so a tab change can't re-render and overwrite the hash before it's read. */
function HashSync({ tab, names, valid, onTab }) {
  const { values, setFilter } = useFilters();
  const latest = useRef(null);
  latest.current = { tab, names, valid, values, onTab };
  const pick = (vals, ns) => Object.fromEntries(ns.map((n) => [n, vals[n]]));

  useEffect(() => {
    writeHash(tab, pick(values, names));
  }, [tab, values, names.join('|')]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onHash = () => {
      const { tab: current, names: ns, valid: ok, values: vals, onTab: switchTab } = latest.current;
      const h = readHash();
      if (h.tab && h.tab !== current) switchTab(h.tab);
      const next = pick(vals, ns);
      for (const n of ns) {
        if (h[n] !== undefined && ok(n, h[n]) && h[n] !== vals[n]) {
          next[n] = h[n];
          setFilter(n, h[n]);
        }
      }
      writeHash(h.tab ?? current, next);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
/** A report's text tab: plain paragraphs, "- " lines become a list. */
function TextTab({ text }) {
  return (
    <section className="section report-text">
      {text.trim().split(/\n\s*\n/).map((block, i) => {
        const lines = block.split('\n');
        return lines.every((l) => l.trim().startsWith('- ')) ? (
          <ul key={i}>{lines.map((l, j) => <li key={j}>{l.trim().slice(2)}</li>)}</ul>
        ) : (
          <p key={i}>{block}</p>
        );
      })}
    </section>
  );
}

/** Slow-parameter confirmation, pipeline progress and pipeline failure, above the sections. */
function PipelineBanner({ pending, status, lastSeconds, onConfirm, onCancel, onDismiss }) {
  if (status?.state === 'running') {
    return (
      <div className="pipeline-banner" role="status">
        <span className="grow">
          Re-pulling data ({status.elapsed ?? 0}s{lastSeconds ? ` of about ${lastSeconds}s` : ''})… Sections keep showing the current data until it finishes.
        </span>
        {status.log?.length > 0 && <code>{status.log.at(-1)}</code>}
      </div>
    );
  }
  if (status?.state === 'failed') {
    return (
      <div className="pipeline-banner failed" role="alert">
        <span className="grow">The pipeline run failed, so the data was not changed: {status.error}</span>
        <button type="button" onClick={onDismiss}>Dismiss</button>
      </div>
    );
  }
  if (!pending) return null;
  return (
    <div className="pipeline-banner" role="dialog" aria-label="Re-pull data">
      <span className="grow">
        Change <b>{pending.label}</b> to <b>{pending.valueLabel}</b>? This re-runs the pipeline and re-pulls the source data
        {lastSeconds ? ` (last run took about ${lastSeconds}s)` : ''}.
      </span>
      <button type="button" className="primary" onClick={onConfirm}>Re-pull data</button>
      <button type="button" onClick={onCancel}>Cancel</button>
    </div>
  );
}

function App({ sections, tabs = [], notes, report = null }) {
  const [state, setState] = useState({ loading: true });
  const [tab, setTab] = useState(hashTab);
  const [only] = useState(() => readHash().only ?? null); // #only=<section id>: that section alone (npm run shot)
  const [pending, setPending] = useState(null); // slow parameter change waiting for confirmation
  const [status, setStatus] = useState(null); // pipeline run status (live dashboard only)

  const reload = () =>
    getMeta().then(
      (meta) => {
        setState({ meta });
        if (meta.pipeline?.state === 'running') setStatus(meta.pipeline);
      },
      (error) => setState({ error }),
    );

  useEffect(() => {
    reload(); // hash changes (tab and filters) are handled by HashSync once the page has loaded
  }, []);

  // while the pipeline runs: poll its status; when it finishes, reload meta (new data version -> sections refetch)
  useEffect(() => {
    if (status?.state !== 'running') return undefined;
    const timer = setInterval(() => {
      getStatus().then(
        (s) => {
          setStatus(s);
          if (s.state !== 'running') reload();
        },
        () => {},
      );
    }, 1500);
    return () => clearInterval(timer);
  }, [status?.state]);

  if (state.error) return <div className="page"><div className="section-error">Could not load data: {state.error.message}</div></div>;
  if (state.loading) return <div className="page loading">Loading…</div>;

  const { meta } = state;
  const { manifest } = meta;
  const themeName = report?.theme ?? config.theme;
  if (report?.themeOverrides) setReportThemeOverrides(themeName, report.themeOverrides);
  applyTheme(themeName);
  const hidden = new Set(report?.hide ?? []);
  const cardInfo = (id) => meta.cards[id]; // the section's analytic: { filters, tables }

  const tabList = tabs.filter((t) => t.text || sections.some((s) => s.meta.tab === t.id));
  const activeTab = tabList.some((t) => t.id === tab) ? tab : tabList[0]?.id;
  const visible = only ? sections.filter((s) => s.meta.id === only) : tabList.length ? sections.filter((s) => s.meta.tab === activeTab) : sections;
  const selectTab = (id) => {
    setTab(id); // HashSync writes it to the URL
    window.scrollTo({ top: 0 });
  };

  // filter state covers every section; the bar shows only filters used on the current tab
  const filtersOf = (s) => cardInfo(s.meta.id)?.filters ?? [];
  const usedFilters = [...new Set(sections.flatMap(filtersOf))].filter((n) => meta.filters[n]);
  const reportFilters = report?.filters ?? {};
  // filters the reader may change, so the URL may carry them; a value must be one of the filter's options
  const changeable = hidden.has('filters') ? [] : usedFilters.filter((n) => !reportFilters[n]?.locked);
  const validChoice = (n, v) => (meta.filters[n]?.options ?? []).includes(v);
  const fromHash = readHash();
  const initial = Object.fromEntries(usedFilters.map((n) => [
    n,
    changeable.includes(n) && validChoice(n, fromHash[n]) ? fromHash[n] : reportFilters[n]?.value ?? ALL,
  ]));
  // Where a filter lives (dashboard.config.json "filters"): no "tab"/"section" = the whole dashboard (bar above the
  // tabs), "tab" = a bar under the tab names, shown on that tab, "section" = in that section's header.
  const showable = (n) => !hidden.has('filters') && !reportFilters[n]?.locked;
  const levelOf = (n) => (meta.filters[n].section ? 'section' : meta.filters[n].tab ? 'tab' : 'dashboard');
  const dashFilters = usedFilters.filter((n) => levelOf(n) === 'dashboard' && showable(n));
  const tabFilters = usedFilters.filter((n) => levelOf(n) === 'tab' && meta.filters[n].tab === activeTab && showable(n));
  const sectionFilters = (id) =>
    usedFilters.filter((n) => meta.filters[n].section === id && showable(n)).map((n) => ({ name: n, ...meta.filters[n] }));
  const params = report ? [] : Object.keys(meta.parameters ?? {});
  const textTab = tabList.find((t) => t.id === activeTab)?.text;

  const usedTables = [...new Set(sections.flatMap((s) => cardInfo(s.meta.id)?.tables ?? []))];
  const asOf = dataAsOf(manifest, usedTables);
  const pulled = manifest.generated_at ? daysBetween(manifest.generated_at, todayIso()) : null;
  // a source given as a file path shows as its file name only
  const sources = [...new Set(usedTables.map((n) => manifest.tables[n]?.source).filter(Boolean).map((s) => (/[\\/]/.test(s) && !/\s/.test(s) ? s.split(/[\\/]/).pop() : s)))];

  const askParam = (name, value) => {
    const p = meta.parameters[name];
    if (value === p.value) return setPending(null);
    setPending({ name, value, label: p.label, valueLabel: p.options.find((o) => o.value === value)?.label ?? value });
  };
  const confirmParam = () => {
    const { name, value } = pending;
    setPending(null);
    runPipeline({ [name]: value }).then(
      (r) => setStatus(r.error ? { state: 'failed', error: r.error } : { state: 'running', elapsed: 0, log: [] }),
      (e) => setStatus({ state: 'failed', error: e.message }),
    );
  };

  // meta.size "half" is honored only when two half sections are adjacent; a lone half goes full width
  const half = visible.map((s) => s.meta.size === 'half');
  const paired = half.map(() => false);
  for (let i = 0; i < half.length - 1; i++) {
    if (half[i] && half[i + 1]) {
      paired[i] = paired[i + 1] = true;
      i++;
    }
  }

  document.title = report?.title ?? config.title;

  return (
    <FilterProvider initial={initial}>
      <HashSync tab={tabList.length > 1 ? activeTab : null} names={changeable} valid={validChoice} onTab={setTab} />
      <div className="page">
        <ReportHeader
          title={report?.title ?? config.title}
          audience={report?.audience}
          asOf={asOf}
          source={hidden.has('source') ? null : config.dataSource || sources.join('; ')}
          staleDays={!report && pulled !== null && pulled > (config.staleDays ?? 7) ? pulled : null}
        />
        {report?.notice && <div className="report-notice" role="note">{report.notice}</div>}
        <FilterBar names={dashFilters} meta={meta} params={params} onParam={askParam} busy={status?.state === 'running'} />
        {tabList.length > 1 && <TabBar tabs={tabList} active={activeTab} onSelect={selectTab} />}
        <FilterBar names={tabFilters} meta={meta} className="tab-level" />
        <PipelineBanner
          pending={pending}
          status={status}
          lastSeconds={status?.last_seconds ?? meta.pipeline?.last_seconds}
          onConfirm={confirmParam}
          onCancel={() => setPending(null)}
          onDismiss={() => setStatus(null)}
        />
        <main className="sections" key={activeTab}>
          {textTab && <TextTab text={textTab} />}
          {visible.map((mod, i) => (
            <SectionFrame
              key={mod.meta.id}
              module={mod}
              info={cardInfo(mod.meta.id)}
              filters={sectionFilters(mod.meta.id)}
              filterMeta={meta.filters}
              version={meta.version}
              note={hidden.has('notes') ? undefined : notes[mod.meta.id]}
              showCommentary={!hidden.has('commentary')}
              half={paired[i]}
              inspect={report?.inspect ? { meta, reportFilters } : null}
            />
          ))}
        </main>
        {report && !hidden.has('footer') && <ReportFooter reportName={report.name} exportDate={report.exportDate} asOf={asOf} />}
      </div>
    </FilterProvider>
  );
}
