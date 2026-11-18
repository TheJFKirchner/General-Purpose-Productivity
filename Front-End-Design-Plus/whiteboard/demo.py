"""Scripted agent for the fake engine (--fake or WHITEBOARD_FAKE=1): zero tokens, no sign-in.

Each message gets a canned answer built from the real column names:
- mentions a card ID (G3)      -> one iteration of it (parent set), drawn as a line
- no ID, but a current visual   -> one iteration of the current visual (round-0 card from --existing)
- a card error report           -> the fix, replacing the same ID
- anything else                 -> two cards: a chart and a table
Good enough to click through the page; not a stand-in for the real agent.
"""
from __future__ import annotations

import json
import re

from .agent import AGENT_NAME
from .data import Table

DEMO_TURNS = 500


def _pick(table: Table) -> tuple[str, str | None]:
    cols = table.columns
    x = next((c["name"] for c in cols if c["type"] in ("string", "date")), cols[0]["name"] if cols else "x")
    y = next((c["name"] for c in cols if c["type"] == "number" and c["name"] != x), None)
    return x, y


def chart_code(library: str, table: Table, mark: str = "bar") -> str:
    x, y = _pick(table)
    head = (f"const X = {json.dumps(x)}, Y = {json.dumps(y)};\n"
            "const sums = {};\n"
            "rows.forEach(r => { const k = String(r[X]); sums[k] = (sums[k] || 0) + (Y ? Number(r[Y]) || 0 : 1); });\n"
            "const labels = Object.keys(sums), values = labels.map(k => sums[k]);\n")
    m = json.dumps(mark)
    body = {
        "echarts": f"const chart = lib.init(el);\nchart.setOption({{tooltip: {{}}, xAxis: {{type: 'category', data: labels}},"
                   f" yAxis: {{type: 'value'}}, series: [{{type: {m}, data: values}}]}});\n",
        "plotly": f"lib.newPlot(el, [{{type: {json.dumps('bar' if mark == 'bar' else 'scatter')}, x: labels, y: values}}],"
                  " {margin: {t: 20}}, {responsive: true});\n",
        "chartjs": "const c = document.createElement('canvas');\nel.appendChild(c);\n"
                   f"new lib(c, {{type: {m}, data: {{labels, datasets: [{{label: Y || 'count', data: values}}]}}}});\n",
        "vegalite": "lib(el, {data: {values: labels.map((k, i) => ({k, v: values[i]}))},"
                    f" mark: {m}, encoding: {{x: {{field: 'k', type: 'nominal', title: X}},"
                    " y: {field: 'v', type: 'quantitative', title: Y || 'count'}}});\n",
        "d3": "const w = el.clientWidth || 400, h = el.clientHeight || 260, max = Math.max(...values, 1);\n"
              "const svg = lib.select(el).append('svg').attr('width', w).attr('height', h);\n"
              "svg.selectAll('rect').data(values).join('rect')\n"
              "  .attr('x', (d, i) => i * w / values.length + 2).attr('width', w / values.length - 4)\n"
              "  .attr('y', d => h - d / max * (h - 10)).attr('height', d => d / max * (h - 10)).attr('fill', '#2f6db5');\n",
        "html": "const max = Math.max(...values, 1);\n"
                "labels.forEach((k, i) => {\n"
                "  const row = document.createElement('div');\n"
                "  row.style.cssText = 'display:flex;align-items:center;gap:6px;margin:2px 0;font:12px sans-serif';\n"
                "  const name = document.createElement('span'); name.textContent = k; name.style.width = '30%';\n"
                "  const bar = document.createElement('span');\n"
                "  bar.style.cssText = `background:#2f6db5;height:12px;width:${values[i] / max * 60}%`;\n"
                "  row.append(name, bar); el.appendChild(row);\n"
                "});\n",
    }[library]
    return head + body


def table_code() -> str:
    return ("const cols = Object.keys(rows[0] || {});\n"
            "const t = document.createElement('table');\n"
            "t.style.cssText = 'border-collapse:collapse;font:12px sans-serif';\n"
            "const hr = t.insertRow();\n"
            "cols.forEach(c => { const th = document.createElement('th'); th.textContent = c; hr.appendChild(th); });\n"
            "rows.slice(0, 50).forEach(r => { const tr = t.insertRow();"
            " cols.forEach(c => { tr.insertCell().textContent = r[c] == null ? '' : r[c]; }); });\n"
            "el.appendChild(t);\n")


def install(library: str, table: Table) -> None:
    from agentlib import fake

    x, y = _pick(table)

    def turn(message: str):
        fix = re.search(r"Card (G\d+) failed to render", message)
        if fix:
            return [fake.call("add_card", {"title": "Fixed", "code": chart_code(library, table),
                                           "replaces": fix.group(1)}),
                    fake.say(f"(demo) Fixed {fix.group(1)}.")]
        request = message.split("\n\n", 1)[-1]
        ref = re.search(r"\bG(\d+)\b", request, re.I)
        current = re.search(r"\bG(\d+) \"[^\"]*\" \([^)]*the current visual", message)
        if ref or current:  # a named card, else the current visual (session from --existing)
            parent = f"G{(ref or current).group(1)}"
            return [fake.call("add_card", {"title": f"{parent} as a line", "parent": parent,
                                           "code": chart_code(library, table, "line")}),
                    fake.say(f"(demo) Added a line version of {parent}.")]
        what = f"{y or 'count'} by {x}"
        return [fake.say("(demo) Two cards coming. "),
                fake.call("add_card", {"title": what.capitalize(), "kind": "chart",
                                       "code": chart_code(library, table)}),
                fake.call("add_card", {"title": "First 50 rows", "kind": "table", "code": table_code()}),
                fake.say("One chart and one table.")]

    fake.script(AGENT_NAME, [turn] * DEMO_TURNS)
