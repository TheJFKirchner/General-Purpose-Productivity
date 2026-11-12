// Extras demo: pictorial visuals, rank chart, pivot table and CSV downloads. Cigna Light. Sample data.
import { createRoot } from 'react-dom/client';
import '../foundation/groundwork.css';
import '../layout/layout.css';
import '../../cigna-light/tokens.css';
import t from '../../cigna-light/chart.js';
import { FindingPanel } from '../layout/FindingPanel.jsx';
import { PanelPair } from '../layout/PanelPair.jsx';
import { TileAtlas } from '../pictorial/TileAtlas.jsx';
import { BodyLens } from '../pictorial/BodyLens.jsx';
import { CapsuleCount } from '../pictorial/CapsuleCount.jsx';
import { STATE_NAMES } from '../pictorial/usTiles.js';
import { RankClimb } from '../charts/RankClimb.jsx';
import { LedgerTable } from '../tables/LedgerTable.jsx';
import { PivotLedger } from '../tables/PivotLedger.jsx';

document.body.dataset.theme = 'cigna-light';
const regions = { Northeast:'ME NH VT MA RI CT NY NJ PA DE MD DC', Southeast:'VA WV NC SC GA FL AL MS TN KY', Midwest:'OH MI IN IL WI MN IA MO ND SD NE KS', 'South Central':'TX OK AR LA', Mountain:'MT ID WY CO UT NV AZ NM', Pacific:'WA OR CA AK HI' };
const regionList = Object.fromEntries(Object.entries(regions).map(([r, s]) => [r, s.split(' ')]));
const baseT = { Northeast:6.4, Southeast:8.6, Midwest:6.9, 'South Central':9.3, Mountain:5.8, Pacific:7.4 };
const hash = (n) => { let h = 0; for (let i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i) * 8) % 9973; return (h / 9973) * 2 - 1; };
const values = {}; Object.entries(regionList).forEach(([r, list]) => list.forEach((s) => { values[s] = Math.round((baseT[r] + hash(STATE_NAMES[s]) * 1.6) * 10) / 10; }));
const ranks = [{ name:'South Central', ranks:[3,2,1,1], note:'+9.3%' }, { name:'Southeast', ranks:[1,1,2,2], note:'+8.6%' }, { name:'Pacific', ranks:[2,3,3,3], note:'+7.4%' }, { name:'Midwest', ranks:[5,4,4,4], note:'+6.9%' }, { name:'Northeast', ranks:[4,5,5,5], note:'+6.4%' }, { name:'Mountain', ranks:[6,6,6,6], note:'+5.8%' }];
const body = [{ name:'Musculoskeletal', value:6.2, tone:9.4, spot:'knee' }, { name:'Cardiology', value:5.1, tone:7.9, spot:'chest-right' }, { name:'Oncology', value:4.8, tone:11.2, spot:'whole' }, { name:'Maternity', value:3.4, tone:4.1, spot:'pelvis' }, { name:'Behavioral', value:2.9, tone:8.6, spot:'head' }, { name:'Digestive', value:2.2, tone:5.2, spot:'abdomen' }, { name:'Respiratory', value:1.8, tone:3.9, spot:'chest-left' }];
const lob = ['Large group','Small group','Individual','Medicare Advantage'], cat = ['Inpatient','Outpatient','Professional','Pharmacy'], matrix = [[120,100,80,60],[60,52,40,32],[48,38,30,24],[75,55,42,38]];
const records = lob.flatMap((l, i) => cat.flatMap((c, j) => ['Q1','Q2','Q3','Q4'].map((q, k) => ({ line:l, category:c, quarter:q, paid:Math.round(matrix[i][j] / 4 * (0.94 + 0.04 * k) * 10) / 10, claims:Math.round(matrix[i][j] * (1.6 + j * 2.2) * (0.97 + 0.02 * k)) }))));
const stateCols = [{ key:'state', label:'State' }, { key:'region', label:'Region', align:'left' }, { key:'trend', label:'Cost trend', fmt:(v) => '+' + v.toFixed(1) + '%', meter:{ min:4, max:11, flag:(v) => v > 9.5 } }];
const regionOf = {}; Object.entries(regionList).forEach(([r, list]) => list.forEach((s) => { regionOf[s] = r; }));
const stateRows = Object.keys(values).sort((a, b) => values[b] - values[a]).slice(0, 8).map((s) => ({ state:STATE_NAMES[s], region:regionOf[s], trend:values[s] }));
const allStates = Object.keys(values).map((s) => ({ state:STATE_NAMES[s], region:regionOf[s], trend:values[s] }));
const SRC = 'Sample data \u00B7 paid through December \u00B7 incurred basis';

function Demo() {
  return (
    <div>
      <div className="jt-band" style={{ paddingBottom:28 }}><div style={{ maxWidth:1240, margin:'0 auto' }}>
        <div className="jt-lab" style={{ color:'var(--bandSoft)' }}>Extras demo</div><h1>Pictorial visuals, pivot table and downloads</h1>
      </div></div>
      <div style={{ maxWidth:1304, margin:'0 auto', padding:'24px 32px 72px', display:'flex', flexDirection:'column', gap:18 }}>
        <FindingPanel finding="South Central states sit at the top of the trend range" measure="Cost trend against last year by state; every state is the same size" source={SRC}
          download={{ filename:'state-trend.csv', sheets:[{ name:'All states', columns:stateCols.map(({ key, label }) => ({ key, label })), rows:allStates }, { name:'Region rank by quarter', columns:[{ key:'name', label:'Region' }, { key:'q1', label:'Q1' }, { key:'q4', label:'Q4' }], rows:ranks.map((r) => ({ name:r.name, q1:r.ranks[0], q4:r.ranks[3] })) }] }}>
          <TileAtlas t={t} values={values} scale={[4.2, 10.8]} regions={regionList} overall={{ name:'National', value:7.2 }} />
          <h3 style={{ margin:'20px 0 0', fontSize:15 }}>Eight highest states</h3>
          <LedgerTable columns={stateCols} rows={stateRows} csv="top-states.csv" />
        </FindingPanel>
        <PanelPair>
          <FindingPanel finding="South Central climbed from third to the highest trend" measure="Rank of each region by cost trend, quarter by quarter; 1 is the highest trend" source={SRC}>
            <RankClimb t={t} periods={['Q1','Q2','Q3','Q4']} rows={ranks} highlight="South Central" label="Region rank by quarter" />
          </FindingPanel>
          <FindingPanel finding="Specialty drugs are 2 of every 100 prescriptions and 51 of every 100 dollars" measure="Pharmacy, 100 capsules each: share of prescriptions beside share of cost" source={SRC}>
            <CapsuleCount groups={[{ title:'Of every 100 prescriptions', parts:[{ name:'Specialty', count:2 }, { name:'Brand', count:12 }, { name:'Generic', count:86 }], callout:{ value:2, text:'are specialty' } },
              { title:'Of every 100 dollars', parts:[{ name:'Specialty', count:51 }, { name:'Brand', count:32 }, { name:'Generic', count:17 }], callout:{ value:51, text:'go to specialty' } }]} />
          </FindingPanel>
        </PanelPair>
        <FindingPanel finding="Regroup the numbers yourself" measure="Paid dollars or claim counts by any two of line of business, service category and quarter" source={SRC}>
          <PivotLedger records={records} csv="pivot.csv" dimensions={[{ key:'line', label:'Line of business' }, { key:'category', label:'Service category' }, { key:'quarter', label:'Quarter' }]}
            measures={[{ key:'paid', label:'Paid, $ millions', fmt:(v) => '$' + v.toFixed(1) + 'M' }, { key:'claims', label:'Claims', fmt:(v) => Math.round(v).toLocaleString('en-US') }]} initial={{ row:'line', col:'category', measure:'paid' }} />
        </FindingPanel>
        <FindingPanel finding="Joints and heart carry the largest increases" measure="Shown only because this demo asks for it: BodyLens is restricted to explicit requests" source={SRC}>
          <BodyLens t={t} items={body} toneScale={[3, 12]} note="Darker circle means a higher trend. Oncology is not tied to one place, so it sits beside the figure." />
        </FindingPanel>
      </div>
    </div>
  );
}
createRoot(document.getElementById('root')).render(<Demo />);
