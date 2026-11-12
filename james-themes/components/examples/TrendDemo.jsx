// Trend-reporting demo: title cards, trend/comparison/contribution charts and features. Cigna Light. Sample data.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../foundation/groundwork.css';
import '../layout/layout.css';
import '../../cigna-light/tokens.css';
import t from '../../cigna-light/chart.js';
import { FindingPanel } from '../layout/FindingPanel.jsx';
import { PanelPair } from '../layout/PanelPair.jsx';
import { CardRow } from '../cards/CardRow.jsx';
import { SplitDial } from '../cards/SplitDial.jsx';
import { RangeCard } from '../cards/RangeCard.jsx';
import { StreakCard } from '../cards/StreakCard.jsx';
import { RankCard } from '../cards/RankCard.jsx';
import { DriverCard } from '../cards/DriverCard.jsx';
import { PeriodSwitch } from '../controls/PeriodSwitch.jsx';
import { FilterChips } from '../controls/FilterChips.jsx';
import { PaceLines } from '../charts/PaceLines.jsx';
import { PulseGrid } from '../charts/PulseGrid.jsx';
import { SlopeShift } from '../charts/SlopeShift.jsx';
import { GapDumbbell } from '../charts/GapDumbbell.jsx';
import { YearPair } from '../charts/YearPair.jsx';
import { PlanDrift } from '../charts/PlanDrift.jsx';
import { TrendBridge } from '../charts/TrendBridge.jsx';
import { DriverStrip } from '../charts/DriverStrip.jsx';
import { ParetoStack } from '../charts/ParetoStack.jsx';
import { FlowRibbon } from '../charts/FlowRibbon.jsx';
import { CompletionCap } from '../charts/CompletionCap.jsx';

document.body.dataset.theme = 'cigna-light';
const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const cur = [412,418,409,421,430,426,438,441,436,447,452,459], prior = [398,401,404,399,408,411,409,415,418,421,424,428];
const yoy = cur.map((v, i) => +((v / prior[i] - 1) * 100).toFixed(1));
const r3 = yoy.map((v, i) => { const a = yoy.slice(Math.max(0, i - 2), i + 1); return +(a.reduce((s, x) => s + x, 0) / a.length).toFixed(1); });
const pace = [{ key:'m', name:'Monthly', data:yoy }, { key:'r3', name:'Rolling 3 months', data:r3 }, { key:'r12', name:'Rolling 12 months', data:[4.1,4.2,4.2,4.4,4.5,4.6,4.8,5.0,5.1,5.2,5.4,5.5] }];
const band = { from:5, to:6 }, events = [{ at:'Jul', label:'Fee schedule change' }];
const cats = [{ name:'Inpatient', from:136, to:148, change:8.8 }, { name:'Outpatient', from:113, to:121, change:7.1 }, { name:'Professional', from:91, to:96, change:5.5 }, { name:'Pharmacy', from:69, to:74, change:7.2 }, { name:'Other', from:19, to:20, change:5.3 }];
const wob = (n) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };
const pulse = cats.map((c, i) => ({ name:c.name, change:c.change, data:months.map((m, j) => +(100 + c.change * 1.25 * (j / 11) + (j ? (wob(i * 20 + j) - 0.5) * 1.6 : 0)).toFixed(1)) }));
const lines = [{ name:'Commercial large group', actual:412, plan:403, lastYear:389 }, { name:'Commercial small group', actual:438, plan:424, lastYear:409 }, { name:'Individual', actual:471, plan:444, lastYear:431 }, { name:'Medicare Advantage', actual:600, plan:604, lastYear:554 }];
const monthly = [-2,1,-4,3,6,2,8,9,5,10,11,11];
const steps = [{ name:'Unit cost', value:14 }, { name:'Utilization', value:9 }, { name:'Mix', value:6 }, { name:'Other', value:2 }];
const conditions = [{ name:'Musculoskeletal', value:6.2 }, { name:'Cardiology', value:5.1 }, { name:'Oncology', value:4.8 }, { name:'Maternity', value:3.4 }, { name:'Behavioral', value:2.9 }, { name:'Digestive', value:2.2 }, { name:'Respiratory', value:1.8 }, { name:'All other', value:4.6 }];
const estimate = [0,0,0,0,0,0,0,0,0,17,42,99], paid = cur.map((v, i) => v - estimate[i]);
const money = (v) => '$' + v;
const paceTable = { columns:[{ key:'month', label:'Month' }, { key:'m', label:'Monthly', fmt:(v) => v + '%' }, { key:'r3', label:'Rolling 3', fmt:(v) => v + '%' }, { key:'r12', label:'Rolling 12', fmt:(v) => v + '%' }],
  rows:months.map((m, i) => ({ month:m, m:yoy[i], r3:r3[i], r12:pace[2].data[i] })) };
const SRC = 'Sample data \u00B7 paid through December \u00B7 incurred basis';

function Demo() {
  const [lead, setLead] = useState('r3');
  const [chips, setChips] = useState([{ key:'lob', label:'All lines of business' }, { key:'region', label:'National' }, { key:'period', label:'Jan to Dec' }]);
  return (
    <div>
      <div className="jt-band" style={{ paddingBottom:28 }}>
        <div style={{ maxWidth:1240, margin:'0 auto' }}>
          <div className="jt-lab" style={{ color:'var(--bandSoft)' }}>Trend demo</div>
          <h1 style={{ marginBottom:16 }}>Cost trend is 7.2%, above the pricing assumption</h1>
          <FilterChips chips={chips} onRemove={(k) => setChips(chips.filter((c) => c.key !== k))} />
        </div>
      </div>
      <div style={{ maxWidth:1304, margin:'0 auto', padding:'24px 32px 72px', display:'flex', flexDirection:'column', gap:18 }}>
        <CardRow>
          <SplitDial label="Cost trend" value="+7.2%" caption="What the trend is made of" parts={[{ name:'Unit cost', value:3.3 }, { name:'Utilization', value:2.1 }, { name:'Mix', value:1.4 }, { name:'Other', value:0.4 }]} />
          <RangeCard label="Inpatient admissions per 1,000" value="61.2" caption="Lowest point in the last 12 months" scale={[59.8, 64.1]} range={[61.2, 62.4]} current={61.2} rangeLabel="12-month range" />
          <StreakCard label="Cost against plan" headline="8 months" caption="over plan in a row, since May" periods={months.map((m, i) => ({ label:m[0], over:monthly[i] > 0 }))} />
          <RankCard label={'South Central \u00B7 cost trend'} value="+9.3%" caption="Highest of 6 regions" rank={1} of={6} note={'Next: Southeast +8.6% \u00B7 Lowest: Mountain +5.8%'} />
          <DriverCard sentence="Inpatient drove 39% of the cost increase" share={0.39} note="$12 of the $31 increase per member per month" />
        </CardRow>
        <PanelPair>
          <FindingPanel finding="Trend has run above the pricing assumption since July" measure="Cost trend against last year, percent. Green band is the pricing assumption, 5 to 6%"
            table={paceTable} source={SRC} commentary="Rolling 3-month trend crossed the top of the assumption band in the fourth quarter and is still rising."
            actions={<PeriodSwitch options={[{ key:'m', label:'Monthly' }, { key:'r3', label:'Rolling 3' }, { key:'r12', label:'Rolling 12' }]} value={lead} onChange={setLead} />}>
            <PaceLines t={t} labels={months} series={pace} lead={lead} band={band} events={events} min={0} max={8} label="Cost trend by month" />
          </FindingPanel>
          <FindingPanel finding="The last three months still lean on estimates" measure="Cost per member per month: paid so far, plus the estimate for claims not yet reported" source={SRC}>
            <CompletionCap t={t} labels={months} paid={paid} estimate={estimate} prior={prior} min={300} max={480} height={270} label="Paid and estimated cost by month" />
          </FindingPanel>
        </PanelPair>
        <FindingPanel finding="Inpatient and pharmacy are the two steep ones" measure="Cost per member per month by service category, same scale, indexed to January" source={SRC}>
          <PulseGrid t={t} labels={months} items={pulse} min={98} max={112} baseline={100} hotAbove={7.15} gate={{ min:5, max:9, step:0.5 }} label="Trend by service category" />
        </FindingPanel>
        <PanelPair>
          <FindingPanel finding="Every category rose; inpatient rose most" measure="Cost per member per month, last year to this year" source={SRC}>
            <SlopeShift t={t} rows={cats} fmt={money} max={160} label="Category cost, last year to this year" />
          </FindingPanel>
          <FindingPanel finding="Individual has the widest gap to plan" measure="Cost per member per month as a percent of plan, by line of business" source={SRC}>
            <GapDumbbell t={t} rows={lines} fmt={money} label="Actual against plan by line of business" />
          </FindingPanel>
        </PanelPair>
        <PanelPair>
          <FindingPanel finding="The gap to last year widened every quarter" measure="Cost per member per month by quarter, this year beside last year" source={SRC}>
            <YearPair t={t} labels={['Q1','Q2','Q3','Q4']} cur={[413,426,438,453]} prior={[401,406,414,424]} fmt={money} min={360} max={470} label="Quarterly cost, two years" />
          </FindingPanel>
          <FindingPanel finding="The overrun started in May and has not stopped" measure="Running total of cost over or under plan, dollars per member, year to date" source={SRC}>
            <PlanDrift t={t} labels={months} monthly={monthly} fmt={money} label="Running variance to plan" />
          </FindingPanel>
        </PanelPair>
        <PanelPair>
          <FindingPanel finding="Unit cost explains almost half of the increase" measure="Cost per member per month, last year to this year, by driver" source={SRC}>
            <TrendBridge t={t} start={{ name:'Last year', value:428 }} steps={steps} end={{ name:'This year', value:459 }} fmt={money} min={400} max={470} label="Cost bridge by driver" />
          </FindingPanel>
          <FindingPanel finding="Inpatient and outpatient are two thirds of the increase" measure="Share of the $31 increase in cost per member per month, by service category" source={SRC}>
            <DriverStrip t={t} parts={cats.map((c) => ({ name:c.name, value:c.to - c.from }))} fmt={money} label="Share of the increase by category" />
          </FindingPanel>
        </PanelPair>
        <FindingPanel finding="Three condition groups make up half of the increase" measure="Dollars of the increase per member per month by condition group, with running share" source={SRC}>
          <ParetoStack t={t} rows={conditions} top={3} restName="All other" max={10} label="Increase by condition group" />
        </FindingPanel>
        <FindingPanel finding="Large group inpatient is the single biggest flow" measure="Paid dollars from line of business to service category, millions" source={SRC}>
          <FlowRibbon t={t} sources={['Large group','Small group','Individual','Medicare Advantage']} targets={['Inpatient','Outpatient','Professional','Pharmacy']} matrix={[[120,100,80,60],[60,52,40,32],[48,38,30,24],[75,55,42,38]]} label="Dollars by line of business and service category" />
        </FindingPanel>
      </div>
    </div>
  );
}
createRoot(document.getElementById('root')).render(<Demo />);
