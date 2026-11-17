#!/usr/bin/env python3
"""Make fake claims data for testing the analysis skill. Everything is invented.

Usage: make_fake_claims.py <output folder>

Writes:
  claims_system_extract.csv   source A: an extract from the claims system
  finance_warehouse.db        source B: a SQLite stand-in for the finance warehouse (table fin_claims)

Planted, so a good analysis has something to find:
  - about 750 claims paid in the last week of March are missing from B (late load)
  - about 150 voided claims are still in B but not in A
  - Medicare paid amounts in B are rounded to whole dollars (small differences)
  - about 80 claims at two providers were reprocessed: B has a different amount (large differences)
  - B uses other names, codes, a different id format and a different date format
  - paid amounts jump in May: one provider's high-cost Medicare claims
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)

N = 20000
providers = pd.DataFrame({
    "provider_id": [f"P{n:04d}" for n in range(1, 41)],
    "provider_name": [f"{a} {b}" for a in ["Northside", "Lakeside", "Riverbend", "Summit", "Harbor", "Prairie",
                                           "Cedar", "Granite"]
                      for b in ["Medical Group", "Surgical", "Family Care", "Imaging", "Clinic"]],
})
lob = rng.choice(["Commercial", "Medicare", "Medicaid"], N, p=[0.55, 0.30, 0.15])
paid_date = pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 181, N), unit="D")
prov = rng.integers(0, 40, N)
billed = np.round(rng.lognormal(6.2, 0.9, N), 2)
paid = np.round(billed * rng.uniform(0.45, 0.85, N), 2)

a = pd.DataFrame({
    "claim_id": [f"CLM-{n:07d}" for n in range(1, N + 1)],
    "member_id": [f"M{n:06d}" for n in rng.integers(1, 6000, N)],
    "provider_id": providers["provider_id"].values[prov],
    "provider_name": providers["provider_name"].values[prov],
    "line_of_business": lob,
    "service_date": (paid_date - pd.to_timedelta(rng.integers(5, 45, N), unit="D")).strftime("%Y-%m-%d"),
    "paid_date": paid_date.strftime("%Y-%m-%d"),
    "billed_amount": billed,
    "paid_amount": paid,
})

# May spike: Lakeside Surgical (P0007), Medicare, high-cost claims
m = pd.DataFrame({
    "claim_id": [f"CLM-{n:07d}" for n in range(N + 1, N + 221)],
    "member_id": [f"M{n:06d}" for n in rng.integers(1, 6000, 220)],
    "provider_id": "P0007", "provider_name": "Lakeside Surgical", "line_of_business": "Medicare",
    "service_date": "2026-04-20",
    "paid_date": (pd.to_datetime("2026-05-04") + pd.to_timedelta(rng.integers(0, 24, 220), unit="D")).strftime("%Y-%m-%d"),
    "billed_amount": np.round(rng.uniform(18000, 42000, 220), 2),
})
m["paid_amount"] = np.round(m["billed_amount"] * 0.7, 2)
a = pd.concat([a, m], ignore_index=True)

# ---- source B, built from A then altered
b = a.copy()
late = b["paid_date"].between("2026-03-25", "2026-03-31")
b = b[~late].copy()                                              # late load: missing from B

mcr = b["line_of_business"] == "Medicare"
b.loc[mcr, "paid_amount"] = b.loc[mcr, "paid_amount"].round(0)   # rounding

reproc_pool = b.index[b["provider_id"].isin(["P0012", "P0031"])]
reproc = rng.choice(reproc_pool, 80, replace=False)
b.loc[reproc, "paid_amount"] = np.round(b.loc[reproc, "paid_amount"] * rng.uniform(0.3, 0.8, 80), 2)

voids = pd.DataFrame({
    "claim_id": [f"CLM-{n:07d}" for n in range(900001, 900151)],
    "member_id": [f"M{n:06d}" for n in rng.integers(1, 6000, 150)],
    "provider_id": providers["provider_id"].values[rng.integers(0, 40, 150)],
    "line_of_business": rng.choice(["Commercial", "Medicare", "Medicaid"], 150),
    "paid_date": (pd.to_datetime("2026-01-01") + pd.to_timedelta(rng.integers(0, 181, 150), unit="D")).strftime("%Y-%m-%d"),
    "paid_amount": np.round(rng.lognormal(5.8, 0.8, 150), 2),
})
b["status"], voids["status"] = "PD", "VD"
b = pd.concat([b, voids], ignore_index=True)

fin = pd.DataFrame({
    "CLAIM_NO": b["claim_id"].str.replace("CLM-", "", regex=False),
    "MBR_ID": b["member_id"],
    "PROV_ID": b["provider_id"],
    "LOB_CD": b["line_of_business"].map({"Commercial": "COM", "Medicare": "MCR", "Medicaid": "MCD"}),
    "PAID_DT": pd.to_datetime(b["paid_date"]).dt.strftime("%m/%d/%Y"),
    "PAID_AMT": b["paid_amount"],
    "CLM_STATUS": b["status"],
}).sample(frac=1, random_state=3)

a.sample(frac=1, random_state=5).to_csv(out / "claims_system_extract.csv", index=False)
db = out / "finance_warehouse.db"
db.unlink(missing_ok=True)
with sqlite3.connect(db) as con:
    fin.to_sql("fin_claims", con, index=False)
print(f"A: {len(a):,} claims, ${a['paid_amount'].sum():,.0f}   B: {len(fin):,} rows, ${fin['PAID_AMT'].sum():,.0f}")
print(f"wrote {out}")
