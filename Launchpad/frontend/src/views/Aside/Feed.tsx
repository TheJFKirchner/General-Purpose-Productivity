/* Activity feed (right-hand panel on the Missions tab): every tool call, newest first, with run / agent filters.
   Ported from prototype/launchpad-orbit.html 2321-2404 (onActivity, feedRowEl, feedSummary, updateFeedFilters,
   applyHL, selectAgent). Hover sets the shared highlight through data-hover-agent; click pins the agent. */
import { memo, useEffect } from 'react';
import { actions, sel, useComputed, useLaunchpad, type Activity } from '../../store';
import { REDUCED, clock, cleanName, toolCat, toolShort } from '../../lib/format';
import { Empty } from '../../components';
import { Search, Terminal } from '../../components/icons';

export function Feed() {
  const v = useComputed(st => {
    const acts = st.acts;
    const n = acts.length, run = acts.filter(a => a.status === 'started').length, den = acts.filter(a => a.status === 'denied').length;
    const rows = sel.feedRows(st).map(a => {
      const s = a.session_id != null ? st.sessions[a.session_id] : null;
      return { a, hidden: !sel.feedVisible(st, a), where: s ? sel.sLabel(s) : 'no run' };
    });
    return {
      n, sum: `${n} call${n === 1 ? '' : 's'}${run ? ` · ${run} running` : ''}${den ? ` · ${den} denied` : ''}`,
      runOpts: sel.feedRunOptions(st), agentOpts: sel.feedAgentOptions(st), rows,
      shown: rows.some(r => !r.hidden),
    };
  });
  const feedRun = useLaunchpad(st => st.ui.feedRun);
  const feedAgent = useLaunchpad(st => st.ui.feedAgent);
  const hov = useLaunchpad(st => st.ui.hov);
  const pinned = useLaunchpad(st => st.ui.sel);
  const eff = hov || pinned;

  /* an agent filter whose agent is no longer in the list (run filter changed) goes back to "All agents" */
  useEffect(() => {
    if (feedAgent && !v.agentOpts.some(o => o.value === feedAgent)) actions.setFeedAgent('');
  }, [feedAgent, v.agentOpts]);

  return (
    <div className="feed card" id="feedCard" aria-label="Activity feed">
      <div className="fl-head"><h2>Activity</h2><span className="fl-sum" id="feedSum">{v.sum}</span></div>
      <div className="feed-filters">
        <label className="sr" htmlFor="feedRun">Filter by run</label>
        <select className="field" id="feedRun" value={feedRun} onChange={e => actions.setFeedRun(e.target.value)}>
          <option value="">All runs</option>
          {v.runOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <label className="sr" htmlFor="feedAgent">Filter by agent</label>
        <select className="field" id="feedAgent" value={feedAgent} onChange={e => actions.setFeedAgent(e.target.value)}>
          <option value="">All agents</option>
          {v.agentOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div className="feed-list" id="feedList">
        {v.rows.map(r => (
          <FeedRow key={r.a.id} a={r.a} hidden={r.hidden} where={r.where}
            hl={!!eff && eff === r.a.agent_id} pin={!!pinned && pinned === r.a.agent_id} />
        ))}
        {v.shown ? null : (
          <Empty id="feedEmpty" icon={v.n ? <Search /> : <Terminal />} title={v.n ? 'No matches' : 'No tool calls yet'}>
            {v.n ? 'No calls match these filters.' : 'They appear here, newest first, as agents work.'}
          </Empty>
        )}
      </div>
    </div>
  );
}

const FeedRow = memo(function FeedRow({ a, hidden, where, hl, pin }: { a: Activity; hidden: boolean; where: string; hl: boolean; pin: boolean }) {
  const meta = [cleanName(a.name) || a.agent_id, a.chat_id != null ? 'Claude Code' : where, a.step != null ? `step ${a.step}` : '', clock(a.ts)].filter(Boolean).join(' · ');
  const stt = a.status === 'started' ? <i className="live" title="running" />
    : a.status === 'denied' ? 'denied' : a.status === 'failed' ? 'failed'
    : a.auto ? <span className="autotag" title="Approved by Autopilot (no card)">auto</span> : null;
  return (
    <button type="button" hidden={hidden} data-hover-agent={a.agent_id} data-id={a.id}
      className={`act ${a.status}${hl ? ' hl' : ''}${pin ? ' pin' : ''}${REDUCED ? '' : ' new'}`}
      aria-label={`${a.name || a.agent_id} ${toolShort(a.tool)} ${a.summary || ''} ${a.status}`}
      onClick={() => actions.selectAgent(a.agent_id)}>
      <span className={`tl ${toolCat(a.tool)}`} title={a.tool}>{toolShort(a.tool)}</span>
      <span className="sm" title={a.summary}>{a.summary || ''}</span>
      <span className="stt">{stt}</span>
      <span className="mt">{meta}</span>
    </button>
  );
});
