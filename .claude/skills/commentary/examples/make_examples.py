#!/usr/bin/env python3
"""Build the mock inputs for the three example deliverables.

  deck_pptx/               healthcare cost deck (.pptx), 3 generators incl. an executive summary
  report_html/             support operations report (.html), parquet + csv tables
  dashboard_programmatic/  claims dashboard commentary with no dashboard UI: period and
                           line-of-business dimensions, two data snapshots (2026-09, 2026-10)
                           to simulate refreshes, commentary saved as one output file per snapshot
  broken_shell/            (with --broken) a shell with deliberate mistakes, for tests

Writes inputs only: data/, commentary_shell.json and the unfilled deliverable.
Generated outputs are removed; README.md, commentary_plan.md and demo_calls.py are kept.
All numbers are synthetic and seeded.

Usage: make_examples.py [root] [--broken] [--only=<folder>]
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ROOT = Path(ARGS[0] if ARGS else Path(__file__).resolve().parent)
KEEP = {"README.md", "demo_calls.py", "commentary_plan.md"}
rng = np.random.default_rng(7)
MONTHS = pd.period_range("2025-11", "2026-10", freq="M").astype(str).tolist()


def fresh(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    for p in d.iterdir():
        if p.name in KEEP:
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    (d / "data").mkdir()
    return d


def dump(d: Path, plan: dict):
    (d / "commentary_shell.json").write_text(json.dumps(plan, indent=2))


# ------------------------------------------------------------------ deck

def deck():
    global rng
    rng = np.random.default_rng(11)
    d = fresh("deck_pptx")
    base = 41_500_000
    trend = np.linspace(0, 0.06, 12) + rng.normal(0, 0.008, 12)
    members = (182_000 + np.arange(12) * 350 + rng.integers(-500, 500, 12)).astype(int)
    allowed = (base * (1 + trend)).round(0)
    allowed[-1] = round(allowed[-2] * 1.042)  # October jump the deck is about
    pd.DataFrame({"month": MONTHS, "allowed_cost": allowed, "members": members,
                  "pmpm": (allowed / members).round(2)}).to_csv(d / "data/dx_by_month.csv", index=False)

    # categories and care settings tie exactly to the monthly total
    oct_total, sep_total = allowed[-1], allowed[-2]

    def split(names, shares, growth):
        sep = np.round(np.array(shares) / sum(shares) * sep_total)
        sep[-1] += sep_total - sep.sum()
        octo = sep * (1 + np.array(growth))
        octo = np.round(octo * oct_total / octo.sum())
        octo[-1] += oct_total - octo.sum()
        return sep, octo

    cats = ["Circulatory", "Musculoskeletal", "Oncology", "Respiratory", "Mental health", "Other"]
    sep, octo = split(cats, [7.9, 6.4, 5.8, 3.9, 3.1, 13.2], [0.091, 0.034, 0.062, -0.041, 0.118, 0.012])
    df = pd.DataFrame({"category": cats, "allowed_oct": octo, "allowed_sep": sep})
    df.loc[len(df)] = ["Total", df.allowed_oct.sum(), df.allowed_sep.sum()]
    df.to_csv(d / "data/dx_by_category.csv", index=False)

    settings = ["Inpatient", "Outpatient", "Professional", "Emergency room"]
    sep, octo = split(settings, [14.1, 11.8, 12.2, 2.2], [0.071, 0.052, 0.008, 0.013])
    pd.DataFrame({"setting": settings, "allowed_oct": octo, "allowed_sep": sep,
                  "admits_or_visits_oct": [1_840, 21_400, 96_300, 4_120],
                  "admits_or_visits_sep": [1_760, 20_900, 95_800, 4_080]}).to_csv(d / "data/dx_by_setting.csv", index=False)

    # top conditions: plausible month-over-month moves, about a quarter of total spend
    conds = ["Heart failure", "Breast cancer", "Osteoarthritis knee", "Major depression", "COPD",
             "Type 2 diabetes", "Lung cancer", "Sepsis", "Chronic kidney disease", "Atrial fibrillation"]
    cpp_oct = np.array([9_800, 14_200, 7_600, 2_100, 4_300, 1_900, 21_500, 18_700, 6_200, 5_400])
    move = np.array([0.031, 0.064, -0.022, 0.018, -0.047, 0.012, 0.087, 0.143, 0.009, 0.041])
    patients = rng.integers(400, 1_600, 10)
    patients = np.round(patients * (0.25 * oct_total) / (patients * cpp_oct).sum()).astype(int)
    pd.DataFrame({"condition": conds, "patients_oct": patients, "cost_per_patient_oct": cpp_oct,
                  "cost_per_patient_sep": np.round(cpp_oct / (1 + move)).astype(int)}
                 ).to_csv(d / "data/top_conditions.csv", index=False)

    classes = ["GLP-1", "Oncology specialty", "Immunology biologics", "Insulins", "Generics (all)"]
    pd.DataFrame({"drug_class": classes,
                  "spend_oct": [3_420_000, 2_910_000, 2_480_000, 610_000, 1_150_000],
                  "spend_sep": [3_050_000, 2_870_000, 2_530_000, 640_000, 1_140_000],
                  "scripts_oct": [3_980, 410, 1_210, 2_900, 61_200]}).to_csv(d / "data/rx_by_class.csv", index=False)

    slides = [
        ("Executive summary", "exec_summary"),
        ("Diagnosis cost trend", "dx_trend"),
        ("Where the growth came from: categories", "dx_category"),
        ("Care setting", "dx_setting"),
        ("Top conditions by cost per patient", "dx_conditions"),
        ("Pharmacy mix", "rx_mix"),
    ]
    from pptx import Presentation
    from pptx.util import Pt
    prs = Presentation()
    for title, uid in slides:
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        body = s.placeholders[1].text_frame
        body.text = "{{commentary:" + uid + "}}"
        body.paragraphs[0].runs[0].font.size = Pt(18)
    prs.save(d / "cost_review.pptx")

    st = lambda n, w: {"format": "bullets", "bullets": n, "max_words": w}  # noqa: E731
    dump(d, {
        "deliverable": "q3_cost_review",
        "medium": "deck",
        "deliverable_files": ["cost_review.pptx"],
        "generators": {
            "1": {"audience": "finance leadership", "samples": ["samples/exec_tone.txt"]},
            "2": {"audience": "finance leadership"},
            "3": {"audience": "executive committee", "inputs": "commentary", "samples": ["samples/exec_tone.txt"]},
        },
        "units": [
            {"id": "exec_summary", "generator": 3, "placement": "slide 1", "covers": "the three things the committee must know about October cost", "tables": [], "style": st(3, 22)},
            {"id": "dx_trend", "generator": 1, "placement": "slide 2", "covers": "how October diagnosis cost and PMPM moved versus September and the 12-month trend", "tables": ["data/dx_by_month.csv"], "style": st(3, 25)},
            {"id": "dx_category", "generator": 1, "placement": "slide 3", "covers": "which diagnosis categories drove the month-over-month change", "tables": ["data/dx_by_category.csv"], "style": st(3, 25)},
            {"id": "dx_setting", "generator": 1, "placement": "slide 4", "covers": "whether the increase is price or volume, by care setting", "tables": ["data/dx_by_setting.csv"], "style": st(3, 25)},
            {"id": "dx_conditions", "generator": 1, "placement": "slide 5", "covers": "which top conditions had the largest change in cost per patient", "tables": ["data/top_conditions.csv"], "style": st(2, 25)},
            {"id": "rx_mix", "generator": 2, "placement": "slide 6", "covers": "what drove the change in pharmacy spend, by drug class", "tables": ["data/rx_by_class.csv"], "style": st(3, 25)},
        ],
    })


# ------------------------------------------------------------------ report

def report():
    global rng
    rng = np.random.default_rng(12)
    d = fresh("report_html")
    weeks = pd.date_range("2026-08-03", periods=13, freq="W-MON").strftime("%Y-%m-%d").tolist()
    tickets = (5200 + np.cumsum(rng.normal(60, 140, 13))).round(0).astype(int)
    tickets[-3:] += [900, 1400, 1100]  # a launch spike
    pd.DataFrame({"week_start": weeks, "tickets": tickets,
                  "median_first_response_hours": np.round(np.r_[np.full(10, 3.1) + rng.normal(0, .2, 10), [5.8, 7.2, 6.1]], 1),
                  "csat": np.round(np.r_[np.full(10, .88) + rng.normal(0, .01, 10), [.83, .79, .81]], 3)}
                 ).to_parquet(d / "data/tickets_by_week.parquet", index=False)
    pd.DataFrame({"channel": ["Email", "Chat", "Phone", "Community forum"],
                  "tickets_oct": [9_800, 11_300, 3_900, 1_700], "tickets_sep": [9_100, 8_200, 3_800, 1_600],
                  "csat_oct": [0.84, 0.78, 0.89, 0.81]}).to_parquet(d / "data/by_channel.parquet", index=False)
    pd.DataFrame({"team": ["Billing", "Accounts", "Integrations", "Mobile app", "Enterprise"],
                  "open_backlog": [410, 280, 1_190, 860, 140], "backlog_4w_ago": [390, 300, 520, 410, 150],
                  "oldest_ticket_days": [9, 6, 23, 17, 4]}).to_csv(d / "data/backlog_by_team.csv", index=False)
    pd.DataFrame({"metric": ["median_first_response_hours", "csat"], "target": [4.0, 0.85],
                  "direction": ["at or below", "at or above"]}).to_csv(d / "data/sla_targets.csv", index=False)
    (d / "support_report.html").write_text(REPORT_HTML)
    dump(d, {
        "deliverable": "support_ops_oct",
        "medium": "report",
        "deliverable_files": ["support_report.html"],
        "generators": {"1": {"audience": "head of customer support and their team leads"},
                       "2": {"audience": "head of customer support"}},
        "units": [
            {"id": "volume", "generator": 1, "placement": "section: volume and response times", "covers": "how ticket volume, first response time and CSAT moved over the last weeks, and when the change started", "tables": ["data/tickets_by_week.parquet"], "style": {"format": "bullets", "bullets": 3, "max_words": 28}},
            {"id": "channels", "generator": 1, "placement": "section: channels", "covers": "which channels absorbed the extra volume and how their CSAT compares", "tables": ["data/by_channel.parquet"], "style": {"format": "bullets", "bullets": 2, "max_words": 28}},
            {"id": "backlog", "generator": 2, "placement": "section: backlog by team", "covers": "which teams' backlogs grew most in four weeks and how old their oldest tickets are", "tables": ["data/backlog_by_team.csv"], "style": {"format": "paragraph", "bullets": 1, "max_words": 70}},
            # targets live in a table, so every number about them can be checked
            {"id": "sla", "generator": 2, "placement": "section: SLA position", "covers": "whether median first response time and CSAT are inside their targets, by how much, and for how many weeks they have been outside", "tables": ["data/tickets_by_week.parquet", "data/sla_targets.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 25}},
        ],
    })


# ------------------------------------------------------------------ dashboard

def dashboard():
    global rng
    rng = np.random.default_rng(13)
    d = fresh("dashboard_programmatic")
    lobs = {"Commercial": (98_000, 395), "Medicare": (41_000, 1_120), "Medicaid": (44_000, 470)}
    rows = []
    for lob, (mem, pm) in lobs.items():
        drift = {"Commercial": 0.004, "Medicare": 0.009, "Medicaid": -0.002}[lob]
        for i, m in enumerate(MONTHS):
            members = int(mem + i * 120 + rng.integers(-300, 300))
            pmpm = round(pm * (1 + drift) ** i * (1 + rng.normal(0, 0.012)), 2)
            rows.append({"paid_month": m, "line_of_business": lob, "members": members,
                         "pmpm": pmpm, "allowed_cost": round(members * pmpm, 0)})
    full = pd.DataFrame(rows)
    full.loc[(full.paid_month == "2026-10") & (full.line_of_business == "Medicare"), "pmpm"] *= 1.06
    full["allowed_cost"] = (full.members * full.pmpm).round(0)

    cats = ["Circulatory", "Musculoskeletal", "Oncology", "Respiratory", "Mental health"]
    cat_rows = []
    for lob in lobs:
        for m in MONTHS[-4:]:
            for c in cats:
                tot = full[(full.paid_month == m) & (full.line_of_business == lob)].allowed_cost.iloc[0]
                share = {"Circulatory": .19, "Musculoskeletal": .15, "Oncology": .13, "Respiratory": .09, "Mental health": .08}[c]
                cat_rows.append({"paid_month": m, "line_of_business": lob, "category": c,
                                 "allowed_cost": round(tot * share * (1 + rng.normal(0, .03)), 0)})
    cat = pd.DataFrame(cat_rows)

    def snapshot(upto: str, sub: str):
        sd = d / sub
        sd.mkdir(parents=True, exist_ok=True)
        f = full[full.paid_month <= upto]
        f.to_csv(sd / "claims_by_lob.csv", index=False)
        tot = f.groupby("paid_month", as_index=False)[["members", "allowed_cost"]].sum()
        tot["pmpm"] = (tot.allowed_cost / tot.members).round(2)
        tot.to_csv(sd / "claims_total.csv", index=False)
        c = cat[cat.paid_month <= upto]
        c = c[c.paid_month.isin(sorted(c.paid_month.unique())[-3:])]
        c.to_csv(sd / "category_by_lob.csv", index=False)

    snapshot("2026-09", "snapshots/2026-09")
    snapshot("2026-10", "snapshots/2026-10")
    for f in (d / "snapshots/2026-09").iterdir():
        shutil.copy(f, d / "data" / f.name)

    dump(d, {
        "deliverable": "dx_cost_dashboard",
        "medium": "dashboard",
        "as_of": {"table": "claims_total", "field": "paid_month", "rule": "max"},
        "show_unverified": False,
        "generators": {
            "1": {"audience": "finance leadership", "use_prior": True, "dimensions": ["paid_month"],
                  "samples": ["samples/exec_tone.txt"]},
            "2": {"audience": "line-of-business finance leads", "use_prior": True,
                  "dimensions": ["paid_month", "line_of_business"]},
        },
        "units": [
            {"id": "overview", "generator": 1, "placement": "tab: overview / header", "covers": "how total allowed cost and PMPM moved this month versus last month and the trend since November", "tables": ["data/claims_total.csv"], "style": {"format": "bullets", "bullets": 3, "max_words": 25}},
            {"id": "lob_trend", "generator": 2, "placement": "tab: line of business / trend", "covers": "how this line of business's PMPM and membership moved versus last month", "tables": ["data/claims_by_lob.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 25}},
            {"id": "lob_categories", "generator": 2, "placement": "tab: line of business / categories", "covers": "which diagnosis categories changed most this month for this line of business", "tables": ["data/category_by_lob.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 25}},
        ],
    })


REPORT_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Support operations: October 2026</title>
<style>
 :root{--ink:#1f2328;--muted:#59636e;--line:#d0d7de;--bg:#ffffff;--accent:#0b5cad}
 body{font-family:system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--bg);margin:0}
 main{max-width:760px;margin:0 auto;padding:32px 16px 64px}
 h1{font-size:28px;margin:0 0 4px} .sub{color:var(--muted);margin:0 0 28px}
 h2{font-size:18px;margin:28px 0 8px;padding-top:16px;border-top:1px solid var(--line)}
 .commentary{margin:8px 0;padding-left:20px;line-height:1.5} p.commentary{padding-left:0}
 .commentary li{margin:4px 0} .note{color:var(--muted);font-size:13px}
</style></head>
<body><main>
<h1>Support operations</h1>
<p class="sub">October 2026 &middot; prepared for the head of customer support</p>

<h2>Volume and response times</h2>
{{commentary:volume}}

<h2>Channels</h2>
{{commentary:channels}}

<h2>Backlog by team</h2>
{{commentary:backlog}}

<h2>SLA position</h2>
{{commentary:sla}}

<p class="note">Commentary is AI-generated from the aggregated tables behind this report and number-checked.</p>
</main></body></html>
"""





# ------------------------------------------------------------------ broken plan

def broken():
    global rng
    rng = np.random.default_rng(14)
    d = fresh("broken_shell")
    pd.DataFrame({"month": MONTHS, "cost": rng.integers(1e6, 2e6, 12)}).to_csv(d / "data/ok_table.csv", index=False)
    pd.DataFrame({"provider": [f"P{i:03d}" for i in range(60)], "cost": rng.integers(1e4, 9e4, 60)}).to_csv(d / "data/providers_60.csv", index=False)
    (d / "outside.csv").write_text("a,b\n1,2\n")
    (d / "page.md").write_text("{{commentary:good}}\n{{commentary:no_covers}}\n{{commentary:ghost}}\n{{commentary:too_big}}\n{{commentary:outside}}\n")
    dump(d, {
        "deliverable": "broken",
        "medium": "report",
        "deliverable_files": ["page.md"],
        "generators": {"1": {"audience": "testers"}},
        "units": [
            {"id": "good", "generator": 1, "placement": "s1", "covers": "monthly cost trend", "tables": ["data/ok_table.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 20}},
            {"id": "no_covers", "generator": 1, "placement": "s2", "covers": "", "tables": ["data/ok_table.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 20}},
            {"id": "too_big", "generator": 1, "placement": "s3", "covers": "provider cost ranking", "tables": ["data/providers_60.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 20}},
            {"id": "outside", "generator": 1, "placement": "s4", "covers": "anything", "tables": ["outside.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 20}},
            {"id": "orphan", "generator": 9, "placement": "s5", "covers": "x", "tables": ["data/ok_table.csv"], "style": {"format": "bullets", "bullets": 2, "max_words": 20}},
        ],
    })


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    for name, build in (("deck_pptx", deck), ("report_html", report), ("dashboard_programmatic", dashboard)):
        if only in (None, name):
            build()
    if "--broken" in sys.argv:
        broken()
    print(f"example inputs written to {ROOT}")
