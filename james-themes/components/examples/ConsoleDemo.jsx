// Full working page: every component wired, sample data. Theme via ?t=cigna-light|cigna-dark|evernorth-light|evernorth-dark
import { createRoot } from 'react-dom/client';
import '../../cigna-light/tokens.css';
import '../../cigna-dark/tokens.css';
import '../../evernorth-light/tokens.css';
import '../../evernorth-dark/tokens.css';
import cl from '../../cigna-light/chart.js';
import cd from '../../cigna-dark/chart.js';
import el from '../../evernorth-light/chart.js';
import ed from '../../evernorth-dark/chart.js';
import { BandConsole } from '../layout/BandConsole.jsx';
import { FindingPanel } from '../layout/FindingPanel.jsx';
import { PanelPair } from '../layout/PanelPair.jsx';
import { SlabButton } from '../controls/SlabButton.jsx';
import { LedgerTable } from '../tables/LedgerTable.jsx';
import { PlanSplit } from '../charts/PlanSplit.jsx';
import { MixStack } from '../charts/MixStack.jsx';
import { RankRail } from '../charts/RankRail.jsx';
import { useLinkGlow } from '../behaviors/useLinkGlow.js';

const T = { 'cigna-light':cl, 'cigna-dark':cd, 'evernorth-light':el, 'evernorth-dark':ed };
const name = new URLSearchParams(location.search).get('t') || 'cigna-light', t = T[name];
document.body.dataset.theme = name;

const labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const money = (v) => '$' + Math.round(v), pct = (v) => v.toFixed(1) + '%', one = (v) => v.toFixed(1);
const measures = [
  { id:'cost', label:'Cost per member per month', actual:459, plan:448, lastYear:428, min:400, max:480, fmt:money, delta:'+7.2%', up:true, good:false, note:'$11 over plan', sentence:'Up from $428 last year. Plan was $448.', labels,
    cur:[412,418,409,421,430,426,438,441,436,447,452,459], prior:[398,401,404,399,408,411,409,415,418,421,424,428] },
  { id:'mlr', label:'Medical loss ratio', actual:86.4, plan:85, lastYear:85.1, min:80, max:90, fmt:pct, delta:'+1.3 pts', up:true, good:false, note:'1.4 pts over plan', sentence:'Up from 85.1% last year. Plan was 85.0%.', labels,
    cur:[84.9,85.2,84.8,85.3,85.6,85.4,85.9,86.0,85.8,86.1,86.3,86.4], prior:[83.9,84.1,84.0,84.3,84.4,84.3,84.6,84.8,84.7,84.9,85.0,85.1] },
  { id:'adm', label:'Inpatient admissions per 1,000', actual:61.2, plan:62.5, lastYear:62, min:55, max:66, fmt:one, delta:'\u22120.8', up:false, good:true, note:'1.3 under plan', sentence:'Down from 62.0 last year. Plan was 62.5.', labels,
    cur:[62.1,62.4,62.0,61.9,62.2,61.8,61.7,61.9,61.5,61.4,61.3,61.2], prior:[62.9,63.0,62.8,62.7,62.9,62.6,62.5,62.6,62.3,62.2,62.1,62.0] },
];
const variance = [{ name:'Commercial large group', value:9 }, { name:'Commercial small group', value:14 }, { name:'Individual', value:27 }, { name:'Medicare Advantage', value:-4 }];
const mix = { Inpatient:[131,137,142,148], Outpatient:[113,116,118,121], Professional:[92,93,95,96], Pharmacy:[66,69,71,74], Other:[11,11,12,14] };
const ledger = [
  { line:'Commercial large group', members:'82,400', cost:'$412', trend:'+5.8%', mlr:84.1 },
  { line:'Commercial small group', members:'41,900', cost:'$438', trend:'+7.1%', mlr:86.9 },
  { line:'Individual', members:'28,600', cost:'$471', trend:'+9.4%', mlr:91.2 },
  { line:'Medicare Advantage', members:'31,400', cost:'$600', trend:'+8.3%', mlr:87.5 },
];
const columns = [{ key:'line', label:'Line of business' }, { key:'members', label:'Members' }, { key:'cost', label:'Cost per member per month' }, { key:'trend', label:'Trend' },
  { key:'mlr', label:'Medical loss ratio', fmt:pct, meter:{ min:70, max:95, flag:(v) => v > 90 } }];

function Demo() {
  const [active, setActive] = useLinkGlow();
  return (
    <BandConsole t={t} sub="Sample data" headline="Cost per member is up 7.2%, led by inpatient" measures={measures}
      menu={[{ label:'Overview', href:'#overview', current:true }, { label:'Cost', href:'#cost' }, { label:'Plan', href:'#plan' }]}
      actions={[{ label:'Share', kind:'line' }, { label:'Export', kind:'solid' }]}>
      <PanelPair>
        <FindingPanel finding="Individual is furthest over plan" measure="Cost per member per month against plan, by line of business">
          <PlanSplit t={t} rows={variance} min={-10} max={30} label="Over and under plan" active={active} onActive={setActive} />
        </FindingPanel>
        <FindingPanel finding="Every category grew each quarter" measure="Cost per member per month by quarter and service category">
          <MixStack t={t} labels={['Q1','Q2','Q3','Q4']} series={mix} max={500} label="Quarterly mix" />
        </FindingPanel>
      </PanelPair>
      <FindingPanel finding="Individual is the only line above a 90% loss ratio" measure="By line of business, December"
        actions={<><SlabButton kind="sec">Download table</SlabButton><SlabButton kind="pri">View all lines</SlabButton></>}>
        <LedgerTable columns={columns} rows={ledger} active={active} onActive={setActive} />
      </FindingPanel>
      <FindingPanel finding="Individual has the largest overrun" measure="Lines over plan, ranked">
        <RankRail t={t} rows={variance.filter((r) => r.value > 0)} max={34} highlight="Individual" fmt={(v) => '+$' + v} label="Ranked overrun" />
      </FindingPanel>
    </BandConsole>
  );
}
createRoot(document.getElementById('root')).render(<Demo />);
