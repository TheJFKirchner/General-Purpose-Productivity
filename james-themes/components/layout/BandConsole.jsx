import { useState } from 'react';
import '../foundation/groundwork.css';
import './layout.css';
import { RailMenu } from './RailMenu.jsx';
import { CommandBand } from './CommandBand.jsx';
import { SpotlightCard } from '../cards/SpotlightCard.jsx';
import { ChartSlate } from '../cards/ChartSlate.jsx';
import { PlanTile } from '../cards/PlanTile.jsx';
import { TwinTrend } from '../charts/TwinTrend.jsx';

// Whole page. t = theme chart.js object. measures[0] leads first; clicking a PlanTile swaps the lead.
export function BandConsole({ t, brand = 'Claims', sub, menu = [], kicker = 'Overview', headline, actions = [], measures, motion = true, children }) {
  const [lead, setLead] = useState(0);
  const m = measures[lead];
  return (
    <div className="jt-shell">
      <RailMenu brand={brand} sub={sub} items={menu} />
      <div className="jt-content">
        <CommandBand kicker={kicker} headline={headline} actions={actions}>
          <SpotlightCard m={m} motion={motion} />
          <ChartSlate label="This year against last year">
            <TwinTrend t={t} labels={m.labels} cur={m.cur} prior={m.prior} fmt={m.fmt} motion={motion} label={`${m.label}, this year against last year`} />
          </ChartSlate>
        </CommandBand>
        <div className="jt-below"><div className="col">
          <section className="jt-tiles">
            {measures.map((x, i) => (i === lead ? null : <PlanTile key={x.id} m={x} bars={t.bars} motion={motion} onLead={() => setLead(i)} />))}
          </section>
          {children}
        </div></div>
      </div>
    </div>
  );
}
