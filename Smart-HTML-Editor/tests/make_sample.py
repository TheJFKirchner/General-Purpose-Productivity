"""Write a sample report like the big ones the editor is for: prose, KPI tiles, an embedded JSON data
blob, a large data table, an SVG chart and an embedded image. All numbers are made up.

    python tests/make_sample.py [out.html] [--rows 2000]
"""
import base64
import json
import random
import sys
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("--")]
rows = int(sys.argv[sys.argv.index("--rows") + 1]) if "--rows" in sys.argv else 2000
if "--rows" in sys.argv:
    args = [a for a in args if a != str(rows)]
out = Path(args[0] if args else Path(__file__).with_name("sample_report.html"))
rnd = random.Random(7)
regions = ["North", "South", "East", "West", "Central"]
data = [{"region": rnd.choice(regions), "month": f"2026-{m:02d}", "revenue": round(rnd.uniform(1e4, 9e5), 2),
         "units": rnd.randint(10, 9000)} for m in range(1, 13) for _ in range(rows // 12 + 1)][:rows]
table_rows = "\n".join(
    f"        <tr><td>{d['region']}</td><td>{d['month']}</td><td>${d['revenue']:,.2f}</td><td>{d['units']:,}</td></tr>"
    for d in data)
points = " ".join(f"{20 + i * 40},{180 - rnd.randint(10, 160)}" for i in range(12))
png = base64.b64encode(bytes(range(256)) * 40).decode()

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Quarterly Sales Report</title>
  <style>
    :root {{
      --accent: #2563eb;
      --text: #1f2937;
      --muted: #6b7280;
      --card-bg: #ffffff;
      --page-bg: #f3f4f6;
      --font: "Segoe UI", system-ui, sans-serif;
    }}
    body {{ margin: 0; background: var(--page-bg); color: var(--text); font-family: var(--font); }}
    header.top {{ background: var(--accent); color: white; padding: 24px 32px; }}
    header.top h1 {{ margin: 0; font-size: 28px; }}
    main {{ padding: 24px 32px; display: grid; gap: 20px; }}
    .card {{ background: var(--card-bg); border-radius: 10px; padding: 18px 22px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .card h2 {{ margin-top: 0; color: var(--accent); font-size: 18px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
    .kpi .value {{ font-size: 30px; font-weight: 700; }}
    .kpi .label {{ color: var(--muted); font-size: 13px; text-transform: uppercase; }}
    table.data {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    table.data th, table.data td {{ border-bottom: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }}
    .scroll {{ max-height: 320px; overflow: auto; }}
  </style>
</head>
<body>
  <header class="top">
    <h1>Quarterly Sales Report</h1>
    <p class="subtitle">Prepared for the regional leadership team &amp; finance</p>
  </header>
  <main id="app">
    <section class="card" id="summary">
      <h2>Summary</h2>
      <p>Revenue grew 12.4% to $4.2M this quarter, led by the <b>North</b> region. Units sold rose to 48,210.</p>
      <p class="note">All figures are preliminary until the close on 2026-10-15.</p>
    </section>
    <section class="kpis">
      <div class="card kpi"><div class="label">Revenue</div><div class="value">$4.2M</div></div>
      <div class="card kpi"><div class="label">Units</div><div class="value">48,210</div></div>
      <div class="card kpi"><div class="label">Margin</div><div class="value">31%</div></div>
    </section>
    <section class="card" id="trend">
      <h2>Monthly trend</h2>
      <svg width="480" height="200" viewBox="0 0 480 200"><polyline fill="none" stroke="#2563eb" stroke-width="3" points="{points}"/><text x="10" y="15">$900K</text></svg>
      <img alt="Company logo" src="data:image/png;base64,{png}" width="40">
    </section>
    <section class="card" id="detail">
      <h2>Detail by region</h2>
      <div class="scroll">
      <table class="data">
        <thead><tr><th>Region</th><th>Month</th><th>Revenue</th><th>Units</th></tr></thead>
        <tbody>
{table_rows}
        </tbody>
      </table>
      </div>
    </section>
  </main>
  <footer class="card" style="margin: 0 32px 32px">Contact: sales-ops team</footer>
  <script type="application/json" id="raw-data">{json.dumps(data)}</script>
  <script>
    const rows = JSON.parse(document.getElementById('raw-data').textContent);
    console.log('loaded', rows.length, 'rows');
  </script>
</body>
</html>
"""
out.write_text(page, encoding="utf-8")
print(f"wrote {out} ({len(page):,} chars, {rows:,} rows)")
