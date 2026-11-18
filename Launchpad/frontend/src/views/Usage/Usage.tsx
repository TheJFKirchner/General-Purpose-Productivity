/* Usage: what the agents cost. Totals for the period, a smooth stacked area chart with toggleable legend pills (bucket day / week, split CLI / model / agent,
   measure cost or one of four token counts, period 7 / 30 / 90 days / all), a sessions table under it (running first,
   sortable; a click narrows the chart to that session, shown as a chip that clears it) and a CSV of what the chart shows.
   Message: usage_get -> usage_data (see the app/server.py header). Every series carries all five measures, so changing
   the measure redraws without a request; the other controls ask again. The server groups the small series as "Other". */
import './Usage.css';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { actions, useLaunchpad } from '../../store';
import type { UsageBucket, UsageMeasure, UsagePeriod, UsageSession, UsageSplit } from '../../contract';
import { USAGE_MEASURES } from '../../contract';
import { Empty, Loading, Pill, ViewFrame } from '../../components';
import { ArrowUpDown, ChartColumnStacked, FileDown, X } from '../../components/icons';
import {
  buildCsv, coloursFor, csvName, downloadText, fillBuckets, loadChartType, saveChartType, type ChartType, fmtShort, fmtValue, folderName, hasData, isOther, kindLabel, MEASURE_LABEL, sortSessions, startedText, valuesOf,
  type SessionSort,
} from '../../lib/usageChart';

const UsageChart = lazy(() => import('./UsageChart'));

const PERIODS: { v: UsagePeriod; label: string }[] = [{ v: '7d', label: '7 days' }, { v: '30d', label: '30 days' }, { v: '90d', label: '90 days' }, { v: 'all', label: 'All' }];
const BUCKETS: { v: UsageBucket; label: string }[] = [{ v: 'day', label: 'Day' }, { v: 'week', label: 'Week' }];
const CHART_TYPES: { v: ChartType; label: string }[] = [{ v: 'line', label: 'Line' }, { v: 'bar', label: 'Bar' }];
const SPLITS: { v: UsageSplit; label: string }[] = [{ v: 'cli', label: 'CLI' }, { v: 'model', label: 'Model' }, { v: 'agent', label: 'Agent' }];
const TOTAL_LABEL: Record<UsageMeasure, string> = { cost: 'Total cost', input_tokens: 'Input tokens', output_tokens: 'Output tokens', cache_read_tokens: 'Cache read tokens', cache_write_tokens: 'Cache write tokens' };
const SPLIT_WORD: Record<UsageSplit, string> = { cli: 'CLI', model: 'model', agent: 'agent' };

function Seg<T extends string | number>({ label, value, options, onPick }: { label: string; value: T; options: { v: T; label: string }[]; onPick: (v: T) => void }) {
  return (
    <div className="us-ctl" role="group" aria-label={label}>
      <span className="us-ctl-l">{label}</span>
      <div className="seg">{options.map(o => <button key={String(o.v)} type="button" aria-pressed={value === o.v} onClick={() => onPick(o.v)}>{o.label}</button>)}</div>
    </div>
  );
}

export default function Usage() {
  const active = useLaunchpad(st => st.ui.view === 'usage');
  const raw = useLaunchpad(st => st.usage.data);
  const pending = useLaunchpad(st => st.usage.pending);
  const [period, setPeriod] = useState<UsagePeriod>('30d');
  const [bucket, setBucket] = useState<UsageBucket>('day');
  const [split, setSplit] = useState<UsageSplit>('cli');
  const [measure, setMeasure] = useState<UsageMeasure>('cost');
  const [chartType, setChartType] = useState<ChartType>(loadChartType);   // Line / Bar, remembered (lp.usageChart); a redraw only
  const pickChartType = (t: ChartType) => { setChartType(t); saveChartType(t); };
  const [session, setSession] = useState<string | null>(null);
  const [sort, setSort] = useState<SessionSort>({ key: 'time', dir: 'desc' });
  const all = useRef<UsageSession[]>([]);               // the sessions list as last sent for the whole period (it stays while the chart is narrowed)
  const [hidden, setHidden] = useState<string[]>([]);   // series switched off with their legend pill (keys); cleared when the split changes
  /* the server sends every bucket of the period; fillBuckets only adds any it skipped (zeros), so the lines always span the period */
  const data = useMemo(() => (raw ? fillBuckets(raw, raw.request?.bucket ?? bucket) : null), [raw]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ask while the screen is showing, and again when a request control changes (not the measure: every series has all five) */
  useEffect(() => { if (active) actions.usageGet({ period, bucket, split, session }); }, [active, period, bucket, split, session]);
  /* leaving the screen: the server stops pushing */
  useEffect(() => { if (active) return () => actions.usageStop(); }, [active]);
  useEffect(() => { setHidden([]); }, [split]);
  const toggleSeries = (key: string) => setHidden(h => (h.includes(key) ? h.filter(k => k !== key) : [...h, key]));
  if (data && !session) all.current = data.sessions;
  const sessions = session ? all.current : data?.sessions ?? [];
  const picked = session ? sessions.find(s => s.id === session) ?? null : null;
  const dSplit = data?.request?.split ?? split;         // the split the data on screen was grouped by (a newer request may be on its way)
  const legendColours = data ? coloursFor(dSplit, data.series) : [];
  const rows = useMemo(() => sortSessions(sessions, sort), [sessions, sort]);

  /* range null = nothing recorded at all (the log is empty); otherwise an empty period or session */
  const empty = !!data && (data.range === null || (!data.sessions.length && USAGE_MEASURES.every(m => !data.totals[m])));
  const forLog = !!data && data.range === null;
  const toggleSort = (key: SessionSort['key']) => setSort(s => (s.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' }));
  const ariaSort = (key: SessionSort['key']) => (sort.key === key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
  const csv = () => { if (data) downloadText(csvName(split, bucket, !!session), buildCsv(data)); };
  const chartLabel = `${MEASURE_LABEL[measure]} ${period === 'all' ? 'over everything recorded' : `over the last ${parseInt(period, 10)} days`}${session ? ', for one session' : ''}`;

  return (
    <ViewFrame id="viewUsage" label="Usage" title="Usage" bodyClass={null}
      sub="What the agents cost, by day or week, and the sessions behind it. Recorded from the moment this log started."
      tools={<Pill size="sm" id="usCsv" icon={<FileDown />} disabled={!data || empty} title="Save what the chart is showing as a CSV file" onClick={csv}>Download CSV</Pill>}>
      <div className="us-body">
        {!data ? <div className="us-note"><Loading>Loading usage…</Loading></div> : (
            <>
              <div className="us-controls">
                <Seg label="Period" value={period} options={PERIODS} onPick={setPeriod} />
                <Seg label="Bucket" value={bucket} options={BUCKETS} onPick={setBucket} />
                <Seg label="Split by" value={split} options={SPLITS} onPick={setSplit} />
                <label className="us-ctl"><span className="us-ctl-l">Measure</span>
                  <select className="field" id="usMeasure" value={measure} onChange={e => setMeasure(e.target.value as UsageMeasure)}>
                    {USAGE_MEASURES.map(m => <option key={m} value={m}>{MEASURE_LABEL[m]}</option>)}
                  </select>
                </label>
                <Seg label="Chart" value={chartType} options={CHART_TYPES} onPick={pickChartType} />
              </div>

              {empty ? (
                <Empty icon={<ChartColumnStacked />} title={forLog ? 'Nothing recorded yet.' : 'Nothing recorded in this period.'}>
                  {forLog ? 'Spend is recorded from now on.' : 'Pick a longer period to see earlier spend.'}
                </Empty>
              ) : (
            <>
              <ul className="us-totals" aria-label="Totals for the period">
                {/* the chosen measure first and large, the other four quieter beside it */}
                {[measure, ...USAGE_MEASURES.filter(x => x !== measure)].map(m => (
                  <li key={m} className={m === measure ? 'on' : ''} aria-current={m === measure ? 'true' : undefined}><span className="us-tl">{TOTAL_LABEL[m]}</span><b>{fmtValue(m, data.totals[m])}</b></li>
                ))}
              </ul>

              {picked || session ? (
                <div className="us-chipline">
                  <span className="chip rev" id="usSessionChip">Session: {picked ? `${picked.label || kindLabel(picked)} · ${startedText(picked.started_at)}` : session}
                    <button type="button" className="us-chipx" aria-label="Show all sessions again" onClick={() => setSession(null)}><X /></button></span>
                </div>
              ) : null}

              <div className={`us-chartwrap${pending > 0 ? ' busy' : ''}`}>
                <div className="us-chead">
                  <h2 className="us-ctitle">{MEASURE_LABEL[measure]} <span>per {bucket}, by {SPLIT_WORD[split]}</span></h2>
                  <ul className="us-legend" aria-label={`Series, by ${split}. Press one to hide or show it in the chart`}>
                    {data.series.map((s, i) => {
                      const tot = valuesOf(s, measure, data.buckets.length).reduce((a, b) => a + b, 0);
                      const on = !hidden.includes(s.key);
                      const tip = `${s.members.length ? `Includes: ${s.members.join(', ')}. ` : ''}${on ? 'Hide' : 'Show'} ${s.label} in the chart`;
                      return (
                        <li key={s.key}>
                          <button type="button" className={`us-pill${isOther(s) ? ' other' : ''}`} aria-pressed={on} title={tip} onClick={() => toggleSeries(s.key)}>
                            <i className="us-sw" style={{ background: legendColours[i], borderColor: legendColours[i] }} aria-hidden="true" /><span className="us-ln">{s.label}</span><span className="us-lv">{fmtValue(measure, tot)}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
                {hasData(data, measure) ? (
                  <Suspense fallback={<div className="us-chartwait"><Loading>Loading chart…</Loading></div>}>
                    <UsageChart data={data} measure={measure} bucket={data.request?.bucket ?? bucket} split={dSplit} label={chartLabel} hidden={hidden} type={chartType} />
                  </Suspense>
                ) : <div className="us-chartwait"><span className="us-note">Nothing to show for {MEASURE_LABEL[measure].toLowerCase()} in this view.</span></div>}
              </div>

              {data.error ? <p className="warn" role="alert">The usage log could not be read: {data.error}</p> : null}
              {data.skipped_lines ? <p className="us-foot">{data.skipped_lines} damaged line{data.skipped_lines === 1 ? '' : 's'} in the log {data.skipped_lines === 1 ? 'was' : 'were'} skipped.</p> : null}
              <p className="us-foot" id="usNote">Costs are the figures each CLI reports. On a subscription they are equivalent costs, not a bill.</p>

              <h2 className="us-h2">Sessions</h2>
              <div className="us-tablewrap">
                <table className="us-table" id="usSessions">
                  <thead><tr>
                    <th scope="col" aria-sort={ariaSort('time')}><button type="button" className="us-sortb" onClick={() => toggleSort('time')}>Started<ArrowUpDown /></button></th>
                    <th scope="col">Folder</th><th scope="col">Kind</th><th scope="col">State</th>
                    <th scope="col" className="num" aria-sort={ariaSort('cost')}><button type="button" className="us-sortb" onClick={() => toggleSort('cost')}>Cost<ArrowUpDown /></button></th>
                    <th scope="col" className="num">Tokens</th>
                  </tr></thead>
                  <tbody>
                    {rows.map(s => (
                      <tr key={s.id} className={s.id === session ? 'on' : ''} onClick={() => setSession(s.id === session ? null : s.id)}>
                        <td><button type="button" className="us-rowb" aria-pressed={s.id === session} title="Show only this session in the chart" onClick={e => { e.stopPropagation(); setSession(s.id === session ? null : s.id); }}>{startedText(s.started_at)}</button></td>
                        <td title={s.folder?.path}>{s.folder ? s.folder.name || folderName(s.folder.path) : 'No folder'}</td>
                        <td>{kindLabel(s)}{s.label && s.label !== kindLabel(s) ? <span className="us-sub">{s.label}</span> : null}</td>
                        <td><span className={`status ${s.running ? 'running' : 'done'}`}>{s.running ? 'Running' : 'Finished'}</span></td>
                        <td className="num">{fmtValue('cost', s.cost)}</td>
                        <td className="num" title={`input ${fmtValue('input_tokens', s.input_tokens)} · output ${fmtValue('output_tokens', s.output_tokens)} · cache read ${fmtValue('cache_read_tokens', s.cache_read_tokens)} · cache write ${fmtValue('cache_write_tokens', s.cache_write_tokens)}`}>
                          {fmtShort('input_tokens', s.input_tokens)} in · {fmtShort('output_tokens', s.output_tokens)} out · {fmtShort('cache_read_tokens', s.cache_read_tokens + s.cache_write_tokens)} cache
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.sessions_total && data.sessions_total > data.sessions.length ? <p className="us-foot">Showing the latest {data.sessions.length} of {data.sessions_total} sessions.</p> : null}
            </>
              )}
            </>
          )}
      </div>
    </ViewFrame>
  );
}
