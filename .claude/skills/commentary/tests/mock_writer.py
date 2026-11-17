#!/usr/bin/env python3
"""Stand-in writer for offline pipeline tests (COMMENTARY_WRITER_CMD).

Reads the brief on stdin. For each unit, writes bullets that quote the first
numeric cell of its first table (always verifiable). If MOCK_BAD_FIRST is set
and the brief is not a retry, the first unit gets a fabricated number so the
retry path runs. If MOCK_ALWAYS_BAD is set, it always fabricates. Units given
last period's commentary (use_prior) end their bullets with "(had prior)".
"""
import json
import os
import sys

brief = json.load(sys.stdin)
units = []
for i, u in enumerate(brief["units"]):
    if "tables" in brief and u["tables"]:
        t = brief["tables"][u["tables"][0]]
        val = next(v for row in t["rows"] for v in row if isinstance(v, (int, float)) and not isinstance(v, bool))
    else:
        val = None
    text = f"The first figure is {val:,}." if val is not None else "Summary without figures."
    bad = (os.environ.get("MOCK_ALWAYS_BAD") or (os.environ.get("MOCK_BAD_FIRST") and "retry" not in brief)) and i == 0
    if bad:
        text = "The figure is 987654321."
    elif u.get("prior"):
        text += " (had prior)"
    n = u["style"]["bullets"] if u["style"]["format"] == "bullets" else 1
    units.append({"id": u["id"], "bullets": [{"text": text, "numbers": []} for _ in range(n)], "missing": []})
print(json.dumps({"units": units}))
