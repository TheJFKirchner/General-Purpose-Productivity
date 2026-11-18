"""Scripted demo on agentlib's fake engine (zero tokens): `python -m app.launch --fake`.

Walks the whole V1 loop so the UI can be reviewed without spending anything:
- planner: question round -> explore (Explorer) -> write_plan (4-step draft) -> waits for Approve
- folder agent: "Demo shop" has .claude/agents/copy-reviewer.md (purpose reviewing, read-only); the draft's step 4
  names it, so the plan card, Missions and the Crew tab show a folder agent with its own count. In a folder without
  it (e.g. "Demo clinic") step 4 falls back to the Builder and the report says so
- copy-reviewer reads, greps, tries one Write (refused: read-only, no card) and reports
- Crew "Draft for me": the fake agent drafter turns any sentence into a filled form (purpose guessed from the words);
  agent_create / agent_remove are plain code and work as in the real app (files in the demo folders)
- orchestrator: run_builder 1, 2, 3, 4 -> write_report
- step 1: reads, a write inside the project, a flight-log entry, one TIMED question (auto-answers at the timeout)
- step 2: one BLOCKING question (the run waits), an edit, a write outside the project (refused)
- step 3: an allowed shell command, then `git push` (permission card, no timer)
- plenty of Read/Grep/Glob/Bash calls so the activity feed looks alive
- planner shows five visual sets (VISUAL_SETS): ECharts by default (bar, stacked bar, line), Chart.js, D3, a
  "matplotlib" set drawn in ECharts and labelled "styled like matplotlib", and design briefs (colour palette, hero
  card); any later message naming a library ("show me plotly") adds a set in it (Plotly / Bokeh draw for real when
  installed, else the labelled ECharts fallback); tweaks ("same but horizontal") and retries go to the fake visual agent
- the planner starts on Sonnet and promotes itself to Opus on the first turn (criteria met); any later message gets
  an edit-based revision (rename + one added step) instead of a full rewrite
- after the run, "Send to planner" makes the planner write a revised plan (round 2) that can be approved again
- builder permission cards are timed (45 s in the demo; unanswered = denied); the autopilot switch skips them
- CLI chat: permission cards (Bash, Write, Edit), a Claude-style question, plan proposal in Plan mode
- fake built-ins never touch disk: "(fake) ran Write" is all that happens
- undefined roles: the draft's step 2 carries role "frontend-dev" (tallied when it ends); seed_tally() puts sample
  entries in the demo's own temp tally (DEMO_ROLES: one below the threshold, two reviewable, one with a failed use;
  their session folders are made up, so the reviewer says they are gone); the fake Role Reviewer walks all three
  verdicts: frontend-dev -> keep, copy-editor -> not_yet, data-migrator -> one question card, then define (the
  drafter then fills the form from the case)
- workflows: "Demo shop" holds a sample workflow (DEMO_WORKFLOW: Explorer, Builder, copy-reviewer, a sign-off review
  with a checklist, a closing summary-email stage) with its method pages and data, and the shipped example
  (app/workflows/example-workflow.json), both in the primary demo folder so they show without ticking anything. seed_workflow_run() starts the sample with its first three stages
  already finished, so the card and Missions show a run waiting at the sign-off; approving runs the last stage on the
  fake Builder; Run / Test run work as in the real app (workflow_stage_turn scripts the stage agents)
- Settings > Connections: Claude Code's test finds the real program and version (read-only) and sends its one
  request to the fake engine; Cursor's is the real install check. MCP library: seed_mcp() fills the demo's temp home
  with three servers (two local demo servers that really pass their test, one URL server that fails), assignments
  for the Builder and copy-reviewer, and a sample Claude Code setup to import from (never the real home folder).
  Agents run on the fake engine, which cannot take MCP servers, so assignments do nothing in the demo
- Usage screen: seed_usage() writes five weeks of made-up usage-log lines (usage_history: plans, CLI chats, workflow
  runs, reviews, drafting; Sonnet / Opus / Haiku; one CLI) into the demo's own temp home; the demo's own fake calls are
  logged on top of it (CLI "Fake engine (demo)")
"""
from __future__ import annotations

import re
from pathlib import Path

from agentlib import fake

PLAN = {
    "name": "Demo: refresh the project landing page",
    "goal": "Rewrite the landing page copy, wire it into the page and publish it. Audience: new visitors. "
            "Output: an updated page plus a short changelog entry.",
    "steps": [
        {"title": "Draft the landing page copy", "details": "Write the new headline, intro and three feature "
         "blurbs as markdown in demo-output/landing.md.", "done_when": "landing.md has all five pieces.", "skills": ["house-style"]},   # a skill in the Demo shop folder
        {"title": "Wire the copy into the page", "details": "Replace the old hero text with the new copy; keep "
         "the existing styles.", "done_when": "The page shows the new copy.", "after": [1],
         "role": "frontend-dev"},                                    # an undefined role: tallied when the step ends
        {"title": "Run checks and publish", "details": "Run the test suite, then push the change.",
         "done_when": "Tests pass and the change is pushed.", "after": [2]},
        {"title": "Review the new copy", "details": "Read demo-output/landing.md and check tone, length and "
         "spelling against the brief; list anything to fix.", "done_when": "A short list of findings (or none).",
         "after": [1], "agent": "copy-reviewer"},
    ],
}

FOLDER_AGENT_NAME = "copy-reviewer"
FOLDER_AGENT_FILE = """---
name: copy-reviewer
description: Reviews written copy (landing pages, release notes) for tone, length and spelling, and lists what to fix.
purpose: reviewing
model: haiku
tools: Read, Grep, Glob
---
- Read the copy the step names; check tone, length and spelling against the brief.
- List each problem as one line: where, what, suggested fix.
- Do not rewrite the copy yourself.
"""

VISUAL_BRIEF = "Monthly visitors for the landing page, Jan-Dec, new vs returning"
VISUAL_OPTIONS = ["Bar", "Stacked bar", "Line"]
# the demo planner's visual sets: (brief, option labels, library asked for)
VISUAL_SETS = [
    (VISUAL_BRIEF, VISUAL_OPTIONS, None),                                              # default: ECharts
    ("Sign-ups by channel, last quarter", ["Doughnut", "Grouped bars"], "Chart.js"),   # another bundled library
    ("Page views by site section", ["Bubble chart", "Bars with labels"], "D3"),
    ("Weekly visitors, as the analytics notebook shows them", ["Line with markers", "Bar"], "matplotlib"),  # fallback
    ("Landing page look: colours and hero", ["Colour palette", "Hero card"], None),    # design briefs
]
DEMO_LIBRARY_WORDS = re.compile(r"(?i)\b(plotly|bokeh|chart\.?js|d3|echarts|matplotlib|seaborn|recharts|altair)\b")

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_NEW = [820, 932, 901, 934, 1290, 1330, 1320, 1180, 1250, 1400, 1520, 1610]
_RET = [420, 480, 510, 530, 610, 700, 690, 650, 720, 760, 810, 900]
_PAL = ["#3B3FB6", "#E8664A", "#4BAE7F", "#7C80E0", "#F2B33D", "#22243A"]
_MPL = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]          # matplotlib's default colour cycle


def _js(obj) -> str:
    import json as _json
    return _json.dumps(obj).replace("<", "\\u003c")


def _wrap(caption: str, inner: str) -> str:
    return ('<div style="font-family:system-ui,sans-serif">'
            f'<div style="font-size:12px;color:#5E6278;margin:4px 8px">{caption}</div>{inner}</div>')


def _palette(caption: str) -> str:
    names = [("Indigo", "#3B3FB6"), ("Lilac", "#B9B7E6"), ("Coral", "#E8664A"), ("Green", "#4BAE7F"),
             ("Ground", "#F4F3FA"), ("Ink", "#22243A")]
    sw = "".join(f'<div style="min-width:0"><div style="height:56px;border-radius:10px;background:{c};'
                 f'border:1px solid #E4E3F0"></div><div style="font-size:12px;margin-top:4px;color:#22243A">{n}</div>'
                 f'<div style="font:11px ui-monospace,monospace;color:#5E6278">{c}</div></div>' for n, c in names)
    return _wrap(caption, '<div style="padding:8px 10px"><div style="display:grid;grid-template-columns:'
                 f'repeat(auto-fill,minmax(84px,1fr));gap:10px 8px">{sw}</div>'
                 '<div style="margin-top:14px;display:flex;gap:10px;align-items:center;background:#F4F3FA;'
                 'padding:12px;border-radius:12px"><button style="background:#3B3FB6;color:#fff;border:0;'
                 'border-radius:999px;padding:8px 16px;font-weight:600">Get started</button>'
                 '<button style="background:#fff;color:#3B3FB6;border:1px solid #B9B7E6;border-radius:999px;'
                 'padding:8px 16px">Learn more</button><span style="color:#E8664A;font-size:13px;font-weight:600">'
                 '3 items need you</span><span style="color:#1F6B47;font-size:13px">Saved</span></div></div>')


def _hero(caption: str) -> str:
    art = ('<svg viewBox="0 0 120 120" style="width:120px;height:120px;flex:none"><circle cx="60" cy="60" r="44" '
           'fill="#B9B7E6"/><circle cx="60" cy="60" r="16" fill="#E8664A"/><ellipse cx="60" cy="60" rx="58" ry="18" '
           'fill="none" stroke="#fff" stroke-width="3" transform="rotate(-20 60 60)"/></svg>')
    return _wrap(caption, '<div style="margin:6px 10px;border-radius:20px;padding:26px;display:flex;flex-wrap:wrap;'
                 'gap:18px;align-items:center;color:#fff;background:linear-gradient(135deg,#3B3FB6,#5A5ED0 60%,#7C80E0)">'
                 '<div style="flex:1 1 220px;min-width:0"><div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;'
                 'opacity:.8">New this spring</div><div style="font:700 28px/1.15 system-ui;margin:6px 0">Plan it in '
                 'minutes, ship it by Friday</div><div style="font-size:14px;opacity:.9;max-width:34ch">One calm '
                 'place for plans, runs and reports. No setup, no tabs to juggle.</div><div style="margin-top:14px;'
                 'display:flex;gap:8px"><span style="background:#E8664A;padding:9px 18px;border-radius:999px;'
                 'font-weight:600">Start free</span><span style="border:1px solid rgba(255,255,255,.6);'
                 'padding:9px 18px;border-radius:999px">See a demo</span></div></div>' + art + '</div>')


def _echarts(caption: str, label: str, change: str, styled: str | None) -> str:
    horizontal = "horizontal" in change.lower()
    low = label.lower()
    stacked = low.startswith("stacked")
    kind = "line" if low.startswith("line") else "bar"
    mpl = bool(styled and styled.lower() == "matplotlib")
    series = [{"name": "New", "type": kind, "data": _NEW}, {"name": "Returning", "type": kind, "data": _RET}]
    for s in series:
        if stacked:
            s["stack"] = "total"
        if kind == "line":
            s.update({"symbol": "circle", "symbolSize": 6} if mpl else {"smooth": True})
    cat = {"type": "category", "data": _MONTHS}
    val = {"type": "value"}
    option = {"color": _MPL if mpl else ["#3B3FB6", "#E8664A"], "tooltip": {"trigger": "axis"},
              "legend": {"top": 0}, "grid": {"left": 48, "right": 16, "top": 36, "bottom": 28},
              "xAxis": val if horizontal else cat, "yAxis": cat if horizontal else val, "series": series}
    if mpl:                                       # matplotlib's look: boxed axes, ticks out, no grid, DejaVu-ish type
        box = {"show": True, "lineStyle": {"color": "#000"}}
        for ax in ("xAxis", "yAxis"):
            option[ax] = dict(option[ax], axisLine=box, axisTick={"inside": False}, splitLine={"show": False},
                              axisLabel={"color": "#000"})
        option.update({"textStyle": {"fontFamily": "DejaVu Sans, Verdana, sans-serif"}, "backgroundColor": "#fff",
                       "legend": {"top": 0, "right": 16, "orient": "vertical", "borderColor": "#ccc",
                                  "borderWidth": 1}})
    return _wrap(caption, '<div id="chart" style="width:100%;height:320px"></div>'
                 f'<script>var c=echarts.init(document.getElementById("chart"));c.setOption({_js(option)});'
                 'window.addEventListener("resize",function(){c.resize();});</script>')


def _chartjs(caption: str, label: str) -> str:
    if label.lower().startswith("doughnut"):
        cfg = {"type": "doughnut", "data": {"labels": ["Search", "Social", "Email", "Referral", "Direct"],
                                            "datasets": [{"data": [412, 268, 190, 96, 150],
                                                          "backgroundColor": _PAL[:5]}]},
               "options": {"responsive": True, "maintainAspectRatio": False,
                           "plugins": {"legend": {"position": "right"}}}}
    else:
        cfg = {"type": "bar", "data": {"labels": ["Jul", "Aug", "Sep"], "datasets": [
            {"label": "Search", "data": [130, 138, 144], "backgroundColor": _PAL[0]},
            {"label": "Social", "data": [80, 92, 96], "backgroundColor": _PAL[1]},
            {"label": "Email", "data": [58, 62, 70], "backgroundColor": _PAL[2]}]},
               "options": {"responsive": True, "maintainAspectRatio": False}}
    return _wrap(caption, '<div style="position:relative;height:310px;padding:0 8px"><canvas id="c"></canvas></div>'
                 f'<script>new Chart(document.getElementById("c"),{_js(cfg)});</script>')


def _d3(caption: str, label: str) -> str:
    data = [{"k": k, "v": v} for k, v in (("Home", 940), ("Pricing", 610), ("Docs", 520), ("Blog", 380),
                                           ("About", 210), ("Careers", 120))]
    head = (f'var data={_js(data)},pal={_js(_PAL)},W=520,H=300;'
            'var svg=d3.select("#d").append("svg").attr("viewBox","0 0 "+W+" "+H).attr("width","100%")'
            '.attr("height",H).style("font","11px system-ui");')
    if label.lower().startswith("bubble"):
        body = ('var root=d3.pack().size([W,H]).padding(4)(d3.hierarchy({children:data}).sum(function(d){return d.v;}));'
                'var g=svg.selectAll("g").data(root.leaves()).join("g").attr("transform",function(d){return '
                '"translate("+d.x+","+d.y+")";});g.append("circle").attr("r",function(d){return d.r;})'
                '.attr("fill",function(d,i){return pal[i%pal.length];}).attr("fill-opacity",0.88);'
                'g.append("text").attr("text-anchor","middle").attr("dy","0.35em").attr("fill","#fff")'
                '.text(function(d){return d.data.k;});')
    else:
        body = ('var x=d3.scaleBand().domain(data.map(function(d){return d.k;})).range([44,W-10]).padding(0.25);'
                'var y=d3.scaleLinear().domain([0,d3.max(data,function(d){return d.v;})]).nice().range([H-24,14]);'
                'svg.append("g").attr("transform","translate(0,"+(H-24)+")").call(d3.axisBottom(x));'
                'svg.append("g").attr("transform","translate(44,0)").call(d3.axisLeft(y).ticks(5));'
                'svg.selectAll("rect.b").data(data).join("rect").attr("class","b").attr("x",function(d){return x(d.k);})'
                '.attr("y",function(d){return y(d.v);}).attr("width",x.bandwidth()).attr("height",function(d){return '
                'H-24-y(d.v);}).attr("rx",3).attr("fill","#3B3FB6");'
                'svg.selectAll("text.l").data(data).join("text").attr("class","l").attr("x",function(d){return '
                'x(d.k)+x.bandwidth()/2;}).attr("y",function(d){return y(d.v)-4;}).attr("text-anchor","middle")'
                '.text(function(d){return d.v;});')
    return _wrap(caption, f'<div id="d"></div><script>{head}{body}</script>')


def _plotly(caption: str, label: str) -> str:
    kind = {"type": "bar"} if label.lower().startswith("bar") else {"type": "scatter", "mode": "lines+markers"}
    data = [dict(kind, x=_MONTHS, y=_NEW, name="New"), dict(kind, x=_MONTHS, y=_RET, name="Returning")]
    layout = {"height": 310, "margin": {"l": 44, "r": 10, "t": 24, "b": 32}, "legend": {"orientation": "h"}}
    return _wrap(caption, '<div id="p" style="width:100%;height:310px"></div>'
                 f'<script>Plotly.newPlot("p",{_js(data)},{_js(layout)},{{displaylogo:false,responsive:true}});'
                 '</script>')


def _bokeh(caption: str, label: str) -> str:
    xs = list(range(1, 13))
    glyph = ('p.vbar({x:{field:"x"},top:{field:"y"},width:0.7,source:src,fill_color:"#3B3FB6",line_color:null});'
             if label.lower().startswith("bar") else
             'p.line({field:"x"},{field:"y"},{source:src,line_width:2,line_color:"#3B3FB6"});'
             'p.scatter({field:"x"},{field:"y"},{source:src,size:7,fill_color:"#3B3FB6",line_color:"#fff"});')
    return _wrap(caption, '<div id="b" style="width:100%;height:310px"></div><script>var plt=Bokeh.Plotting;'
                 f'var src=new Bokeh.ColumnDataSource({{data:{{x:{_js(xs)},y:{_js(_NEW)}}}}});'
                 'var p=plt.figure({title:"Monthly visitors",sizing_mode:"stretch_width",height:290,'
                 'tools:"pan,wheel_zoom,reset"});'
                 f'{glyph}plt.show(p,document.getElementById("b"));</script>')


def sample_visual(label: str, change: str = "", library: str = "ECharts", styled: str | None = None) -> str:
    """Made-up HTML for one demo option (what the visual agent would return); `change` marks a tweak."""
    caption = label + (f" (revised: {change})" if change else "") + (f" · styled like {styled}" if styled else "")
    low = label.lower()
    if "palette" in low:
        return _palette(caption)
    if "hero" in low:
        return _hero(caption)
    lib = library.lower().replace(".", "")
    if lib == "chartjs":
        return _chartjs(caption, label)
    if lib == "d3":
        return _d3(caption, label)
    if lib == "plotly":
        return _plotly(caption, label)
    if lib == "bokeh":
        return _bokeh(caption, label)
    return _echarts(caption, label, change, styled)


def visual_turn(msg: str) -> list:
    """Fake visual agent: draws the option named in the message (or revises it) with the library it names."""
    m = re.search(r"Option(?: to draw)?: (.+)", msg)
    label = m.group(1).strip() if m else "Bar"
    ch = re.search(r"(?:Change requested|Also apply this change): (.+)", msg)
    lib = re.search(r"Library: (.+?) \(global", msg)
    styled = re.search(r"styled like (.+?):", msg)
    html = sample_visual(label, ch.group(1).strip() if ch else "", lib.group(1) if lib else "ECharts",
                         styled.group(1) if styled else None)
    return [fake.spend(0.002), fake.say("```html\n" + html + "\n```")]


PLAN_ROUND_2 = {
    "name": "Demo: landing page, round 2",
    "goal": "Act on the report: tighten the headline and re-run the checks.",
    "steps": [
        {"title": "Tighten the headline", "details": "Shorten the headline in demo-output/landing.md to six words.",
         "done_when": "The headline is six words or fewer."},
        {"title": "Re-run the checks", "details": "Run the tests again.", "done_when": "Tests pass.", "after": [1]},
    ],
}

BRIEFS = {
    1: "Draft the copy in demo-output/landing.md. Tone: plain and friendly. Use the flight log for context.",
    2: "Put step 1's copy into the page. Keep the existing styles; do not restructure the page.",
    3: "Run the tests; push only if they pass.",
    4: "Review step 1's copy in demo-output/landing.md: tone, length, spelling. Findings only, no edits.",
}


def draft_fields(text: str) -> dict:
    """What the fake agent drafter returns for a sentence (purpose guessed from its words)."""
    low = text.lower()
    purpose = ("reviewing" if re.search(r"review|check|audit|proofread|lint", low) else
               "exploring" if re.search(r"find|explore|search|look|map|summar", low) else "building")
    words = [w for w in re.findall(r"[a-z0-9]+", low) if w not in {"a", "an", "the", "that", "which", "and", "to",
                                                                     "for", "of", "my", "our", "agent", "i", "want",
                                                                     "check", "checks", "review", "reviews", "find",
                                                                     "finds", "where", "look", "looks", "at", "in"}]
    name = "-".join(words[:2] + [{"reviewing": "reviewer", "exploring": "finder", "building": "builder"}[purpose]])
    read_only = purpose != "building"
    return {"name": name or "helper", "description": text.strip().rstrip(".")[:150] + ".",
            "purpose": purpose, "model": "haiku" if read_only else "sonnet",
            "tools": ["Read", "Grep", "Glob"] if read_only else ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
            "instructions": "- Read only what the step needs.\n- " + ("Report each problem as one line: where, what, fix."
                            if purpose == "reviewing" else "List the files that matter, one line each."
                            if purpose == "exploring" else "Make the change, keep it small, and say what you changed.")}


# ---------------------------------------------------------------- undefined roles (sample tally + fake reviewer)
# role -> uses: (step title, step text, outcome, questions, assumptions, timed out, skills)
DEMO_ROLES = {
    "release-checker": [("Check the release notes", "Read CHANGELOG.md and check every entry has a date.", "done", 0, 0, 0, [])],
    "frontend-dev": [
        ("Add the pricing table", "Build the pricing table in the shop page with the house styles; keep it "
         "responsive on phones.", "done", 1, 1, 0, ["house-style"]),
        ("Fix the basket layout", "Fix the basket layout on narrow screens; do not change the colours.",
         "done", 0, 0, 0, ["house-style"]),
        ("Restyle the footer", "Restyle the footer links; keep it responsive on phones.", "done", 0, 1, 0, [])],
    "copy-editor": [
        ("Tidy the about page", "Shorten the about page to three paragraphs.", "done", 0, 0, 0, ["house-style"]),
        ("Proofread the FAQ", "Proofread the FAQ for spelling.", "done", 0, 0, 0, [])],
    "data-migrator": [
        ("Move orders to the new table", "Copy orders into orders_v2 in batches of 500; keep the old table until "
         "counts match; never drop data.", "done", 1, 0, 0, []),
        ("Backfill customer ids", "Backfill customer_id on orders_v2 from the customers table in batches of 500; "
         "check counts after each batch.", "failed", 3, 2, 1, []),
        ("Migrate the stock table", "Copy stock into stock_v2 in batches of 500; compare counts; never drop data.",
         "done", 2, 1, 0, []),
        ("Migrate the returns table", "Copy returns into returns_v2 in batches of 500; check counts after each "
         "batch.", "done", 1, 0, 0, [])],
}


def seed_tally(tally, store) -> None:
    """Sample undefined roles for the demo, in the demo's own temp tally only (never a real one). Session ids are made
    up: the reviewer says their folders are gone and works from the tally lines and samples."""
    from .tally import in_temp
    if tally.path is None or not in_temp(tally.path) or tally.entries():
        return
    dirs = store.directories()
    shop = dirs[0] if dirs else {"dir_id": None, "path": "", "name": "Demo shop"}
    for k, (role, uses) in enumerate(DEMO_ROLES.items()):
        for i, (title, text, outcome, questions, assumptions, timed_out, skills) in enumerate(uses, 1):
            tally.record_use(role, sample=f"### Step {i}: {title}\n{text}", use={
                "dir_id": shop["dir_id"], "folder": shop["name"], "project": shop["path"],
                "session_id": f"20261101-0900{k}{i}-demo", "run": 1, "step": i, "title": title, "skills": skills,
                "outcome": outcome, "questions": questions, "assumptions": assumptions, "timed_out": timed_out})


# ---------------------------------------------------------------- usage history (sample, temp only)
USAGE_DAYS = 35                      # made-up history: five weeks up to today
# model id -> $ per million tokens (input, output, cache read, cache write); made-up but believable
USAGE_MODELS = {"claude-sonnet-4-5": (3.0, 15.0, 0.30, 3.75), "claude-opus-4-5": (5.0, 25.0, 0.50, 6.25),
                "claude-haiku-4-5": (1.0, 5.0, 0.10, 1.25)}
USAGE_PLANS = ("Refresh the landing page", "Order export to CSV", "Fix the checkout totals", "Tidy the product pages",
               "Newsletter sign-up form", "Speed up the search page", "Returns policy page", "Stock alert emails")
USAGE_ROLES = ("frontend-dev", "copy-editor", "data-migrator")


def usage_history(dirs: list[dict], today=None, seed: int = 17) -> list[dict]:
    """Believable made-up usage-log lines for the demo (app/usagelog.py line format): plan sessions (planner on Sonnet,
    sometimes promoted to Opus; orchestrator, builders, Explorer, Visualizer, the copy-reviewer folder agent), CLI
    chats, workflow runs, role reviews and drafting calls over USAGE_DAYS days, more on weekdays. One CLI only (the
    others are not usable), so the variety is in models and agents."""
    import datetime as dt
    import random
    from .agents import crew
    from .usagelog import VERSION
    rng = random.Random(seed)
    today = today or dt.date.today()
    dirs = dirs or [{"dir_id": None, "path": "", "name": "Demo shop"}]
    rows: list[dict] = []
    now = dt.datetime.now()

    def call(t, sid, kind, label, d, role, agent, model, size=1.0, step=None, stage=None, run_folder=None):
        rates = USAGE_MODELS[model]
        u = {"input_tokens": int(rng.randint(6, 60) * size), "output_tokens": int(rng.randint(400, 3500) * size),
             "cache_read_tokens": int(rng.randint(15_000, 160_000) * size),
             "cache_write_tokens": int(rng.randint(1_500, 25_000) * size)}
        cost = sum(u[k] * r for k, r in zip(("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"),
                                            rates)) / 1e6
        rows.append({"v": VERSION, "ts": t.astimezone().isoformat(timespec="seconds"), "session": sid, "kind": kind,
                     "label": label, "dir_id": d["dir_id"], "folder": d["path"], "folder_name": d["name"],
                     "run_folder": run_folder, "role": role, "agent": agent, "step": step, "stage": stage,
                     "model": model, "cli": "claude", "engine": "claude", "cost": round(cost, 6), **u})
        return t + dt.timedelta(minutes=rng.randint(1, 9), seconds=rng.randint(0, 59))

    for back in range(USAGE_DAYS - 1, -1, -1):
        day = today - dt.timedelta(days=back)
        weekday = day.weekday() < 5
        for k in range(rng.randint(2, 5) if weekday else rng.randint(0, 2)):
            t = dt.datetime.combine(day, dt.time(rng.randint(8, 18), rng.randint(0, 59)))
            if t > now:
                continue
            d = dirs[rng.randrange(len(dirs))]
            sid = f"{t.strftime('%Y%m%d-%H%M%S')}-demo{k}"
            kind = rng.choices(("plan", "chat", "workflow", "review", "other"), (5, 4, 2, 1, 1))[0]
            folder = Path(d["path"]) / ".launchpad" / sid if d["path"] else None
            rf = str(folder) if folder else None
            if kind == "plan":
                label = rng.choice(USAGE_PLANS)
                top = rng.random() < 0.4
                for i in range(rng.randint(2, 5)):
                    t = call(t, sid, kind, label, d, "planner", crew.display("planner"),
                             "claude-opus-4-5" if top and i else "claude-sonnet-4-5", 0.6, run_folder=rf)
                if rng.random() < 0.5:
                    t = call(t, sid, kind, label, d, "astronaut", crew.display("astronaut"), "claude-haiku-4-5", 0.8,
                             run_folder=rf)
                if rng.random() < 0.3:
                    t = call(t, sid, kind, label, d, "visual", crew.display("visual"), "claude-haiku-4-5", 0.4,
                             run_folder=rf)
                if rng.random() < 0.8:                                          # approved and run
                    steps = rng.randint(2, 4)
                    for n in range(1, steps + 1):
                        t = call(t, sid, kind, label, d, "orchestrator", crew.display("orchestrator"),
                                 "claude-sonnet-4-5", 0.3, run_folder=rf)
                        worker = "Copy reviewer" if n == steps and rng.random() < 0.4 else crew.display("builder")
                        for _ in range(rng.randint(1, 3)):
                            t = call(t, sid, kind, label, d, "builder", worker, "claude-sonnet-4-5", 1.2, step=n,
                                     run_folder=rf)
            elif kind == "chat":
                model = "claude-opus-4-5" if rng.random() < 0.3 else "claude-sonnet-4-5"
                for _ in range(rng.randint(2, 8)):
                    t = call(t, sid, kind, "CLI chat", d, "pilot", crew.display("pilot"), model, 0.9, run_folder=rf)
            elif kind == "workflow":
                wid = f"{t.strftime('%Y%m%d-%H%M%S')}-{rng.randrange(16**4):04x}"
                sid = f"wf-{wid}"
                label = f"Weekly stock report, run {wid}"
                for n, (agent, stage, model) in enumerate((
                        (crew.display("astronaut"), "Gather this week's numbers", "claude-haiku-4-5"),
                        (crew.display("builder"), "Write the report", "claude-sonnet-4-5"),
                        ("Copy reviewer", "Check the wording", "claude-sonnet-4-5")), 1):
                    t = call(t, sid, kind, label, d, "builder", agent, model, 1.0, step=n, stage=stage,
                             run_folder=str(Path(d["path"]) / "reports" / wid) if d["path"] else None)
            elif kind == "review":
                sid = f"reviewer-{rng.randrange(16**8):08x}"
                role = rng.choice(USAGE_ROLES)
                for _ in range(rng.randint(1, 2)):
                    t = call(t, sid, kind, f"Role review: {role}", d, "reviewer", crew.display("role_reviewer"),
                             "claude-sonnet-4-5", 0.7)
            else:
                sid = f"drafter-{rng.randrange(16**8):08x}"
                call(t, sid, kind, "Agent drafting", d, "drafter", crew.display("drafter"), "claude-haiku-4-5", 0.2)
    return rows


def seed_usage(log, store) -> None:
    """Made-up usage history for the Usage screen, in the demo's own temp home only (never a real log); the demo home
    is wiped at every --fake launch, so it is always five weeks up to today."""
    from .tally import in_temp
    if log.folder is None or not in_temp(log.folder) or log.files():
        return
    log.append_many(usage_history(store.directories()))


# ---------------------------------------------------------------- MCP library + Claude Code import (sample, temp only)
DEMO_MCP_SERVER = Path(__file__).resolve().parent / "demo_mcp_server.py"


def demo_mcp_servers() -> list[dict]:
    """The demo's sample MCP library: two real local servers (app/demo_mcp_server.py: their background test passes,
    zero tokens, no network) and one URL server nothing answers (its test fails; masked header)."""
    import sys
    return [
        {"name": "notes", "kind": "command",
         "config": {"command": sys.executable, "args": [str(DEMO_MCP_SERVER), "--set", "notes"], "env": {}}},
        {"name": "glossary", "kind": "command",
         "config": {"command": sys.executable, "args": [str(DEMO_MCP_SERVER), "--set", "glossary"],
                    "env": {"GLOSSARY_TOKEN": "demo-token-not-real"}}},
        {"name": "warehouse", "kind": "url",
         "config": {"url": "http://127.0.0.1:9/mcp", "headers": {"Authorization": "Bearer demo-not-a-real-token"}}},
    ]


DEMO_MCP_ASSIGNMENTS = {"launchpad-builder": ["notes"], FOLDER_AGENT_NAME: ["glossary", "warehouse"]}


def seed_mcp(lib, folders: list[Path], claude_home: Path) -> None:
    """The demo's MCP library (in its own temp home only, never a real one; reset to the sample on every launch) and a
    sample Claude Code setup to import
    from (claude_home/.claude.json: one user server, one local-scope server for the first demo folder; the first demo
    folder's .mcp.json: one project server). Import commands are made up and URLs end in .invalid, so testing an
    imported server fails fast and never downloads or sends anything."""
    import json
    from .tally import in_temp
    if lib.path is None or not in_temp(lib.path) or not in_temp(claude_home):
        return
    for name in lib.names():                    # every launch starts from the fresh sample (temp home only)
        lib.remove(name)
    if not lib.names():
        for s in demo_mcp_servers():
            lib.save(s)
        for agent, names in DEMO_MCP_ASSIGNMENTS.items():
            lib.set_agent(agent, names)
    claude_home.mkdir(parents=True, exist_ok=True)
    shop = Path(folders[0]) if folders else None
    projects = {}
    if shop is not None:
        projects[shop.resolve().as_posix()] = {"mcpServers": {
            "shop-db": {"type": "stdio", "command": "shop-db-mcp", "args": ["--read-only"], "env": {}}}}
        (shop / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "figma": {"type": "http", "url": "https://mcp.figma.invalid/mcp",
                      "headers": {"Authorization": "Bearer ${FIGMA_TOKEN}"}}}}, indent=1), encoding="utf-8")
    (claude_home / ".claude.json").write_text(json.dumps({
        "mcpServers": {
            "github": {"type": "stdio", "command": "github-mcp-demo", "args": [],
                       "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"}},
            "notes": {"type": "stdio", "command": "notes-mcp", "args": []}},
        "projects": projects}, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- workflows (sample workflow + a run waiting at its review)
DEMO_WORKFLOW_SLUG = "monthly-sales-report"
DEMO_WORKFLOW = {
    "format": 1, "name": "Monthly sales report",
    "description": "Builds the month's sales figures from the order export, has the copy reviewer prepare a memo, "
                   "stops for the sales lead's sign-off, then writes the summary email.",
    "output_folder": "reports/monthly-sales", "unattended_default": False,
    "inputs": [
        {"name": "month_end", "label": "Month end", "kind": "date", "required": True, "default": "2026-10-31",
         "options": [], "help": "Last day of the month the report covers."},
        {"name": "orders_file", "label": "Order export", "kind": "file", "required": True,
         "default": "data/orders-2026-10.csv", "options": [], "help": "CSV export from the shop."},
        {"name": "region", "label": "Region", "kind": "choice", "required": True, "default": "All",
         "options": ["All", "North", "South"], "help": ""}],
    "files": ["docs/sales-report-method.md"],
    "stages": [
        {"kind": "agent", "title": "Find the inputs", "agent": "launchpad-astronaut",
         "instruction": "Find the order export named in the inputs and last month's report, and say what each holds.",
         "files": []},
        {"kind": "agent", "title": "Build the figures", "agent": "launchpad-builder",
         "instruction": "Total the orders for the month by product line and region, excluding refunds, as the method "
                        "says. Save the table as figures.csv in the run folder and put the table in your result.",
         "files": ["docs/figure-rules.md"]},
        {"kind": "agent", "title": "Prepare the review memo", "agent": FOLDER_AGENT_NAME,
         "instruction": "Check the figures against the method: what you verified, what looks off, and questions for "
                        "the sales lead.", "files": []},
        {"kind": "review", "title": "Sales lead sign-off", "checklist": [
            {"text": "Totals tie to the order export", "kind": "tick"},
            {"text": "Refunds are excluded", "kind": "tick"},
            {"text": "Anything unusual this month?", "kind": "answer"}]},
        {"kind": "agent", "title": "Write the summary email", "agent": "launchpad-builder",
         "instruction": "Write a five-line summary email of the month's sales for the team, from the figures and "
                        "the reviewer's notes.", "files": []}],
}
DEMO_WORKFLOW_FILES = {
    f"workflows/{DEMO_WORKFLOW_SLUG}.json": None,                          # filled from DEMO_WORKFLOW
    "docs/sales-report-method.md": "# Sales report method (made up)\n- Month = calendar month of the order date\n"
                                   "- Refunds are excluded\n- Totals in pounds, two decimals\n",
    "docs/figure-rules.md": "# Figure rules (made up)\n- One row per product line and region\n- Round at the end\n",
    "data/orders-2026-10.csv": "date,product,region,amount,refund\n2026-10-02,Mugs,North,24.00,0\n"
                               "2026-10-09,Prints,South,61.50,0\n2026-10-15,Mugs,South,12.00,1\n",
}
DEMO_SEED_RESULTS = {
    0: "- `data/orders-2026-10.csv`: the October order export (date, product, region, amount, refund flag); 3 rows.\n"
       "- No earlier report was found in `reports/monthly-sales/`; this is the first run.",
    1: "| Product line | North | South | Total |\n|---|---|---|---|\n| Mugs | 24.00 | 0.00 | 24.00 |\n"
       "| Prints | 0.00 | 61.50 | 61.50 |\n| **Total** | **24.00** | **61.50** | **85.50** |\n\n"
       "One refunded order (Mugs, South, 12.00) was excluded. Table saved as `figures.csv` in the run folder.",
    2: "## Verified\n- Totals add up to 85.50 across both regions.\n- The refunded order is left out, as the method says.\n\n"
       "## Looks off\n- South had no mug sales apart from the refund; worth a glance.\n\n"
       "## Questions for the sales lead\n- Should the refunded order appear as a note in the email?",
}


def workflow_files() -> dict[str, str]:
    """Files the demo puts in "Demo shop" for its sample workflow (the workflow file, its method pages, the data)."""
    import json as _json
    return {k: (_json.dumps(DEMO_WORKFLOW, indent=2) + "\n" if v is None else v) for k, v in DEMO_WORKFLOW_FILES.items()}


def example_workflow_file() -> tuple[str, str]:
    """The shipped example workflow (app/workflows/example-workflow.json), for "Demo shop" beside the sample."""
    src = Path(__file__).resolve().parent / "workflows" / "example-workflow.json"
    return "workflows/example-weekly-status.json", src.read_text(encoding="utf-8")


async def seed_workflow_run(hub) -> None:
    """--fake: start the sample workflow with its first three stages already finished, so the card and Missions
    show a believable run waiting at the sales lead's sign-off. Best-effort: a missing folder just skips it."""
    try:
        wid = next((w["id"] for w in hub.workflows.scan()[0] if w["slug"] == DEMO_WORKFLOW_SLUG), None)
        if wid is None:
            return
        await hub.workflows.start(wid, {"month_end": "2026-10-31", "orders_file": "data/orders-2026-10.csv",
                                        "region": "All"}, test=False, unattended=False, seed_results=DEMO_SEED_RESULTS)
    except Exception as e:  # noqa: BLE001 -- the demo must start even if the sample run cannot be made
        await hub.system(f"Demo: the sample workflow run was not seeded ({type(e).__name__}: {e})")


def _run_folder(msg: str) -> str:
    m = re.search(r"Run folder \(write any data files here\): (.+)", msg)
    return m.group(1).strip() if m else "."


def workflow_stage_turn(msg: str, who: str) -> list:
    """Fake agents in a workflow stage: a few believable tool calls, then submit_report with a markdown result."""
    m = re.search(r"stage \d+ of \d+: (.+?)(?: \(test run\))?$", msg, re.M)
    title = m.group(1).strip() if m else "Stage"
    folder = _run_folder(msg)
    note = re.search(r"- (.+?) at review \"(.+?)\": (.+)", msg)
    redo = f"\n\nRe-done after {note.group(1)}'s note: {note.group(3)}" if note else ""
    if who == "astronaut":
        return [fake.call("Glob", {"pattern": "data/*.csv"}), fake.call("Read", {"file_path": "data/orders-2026-10.csv"}),
                fake.spend(0.002), fake.call("submit_report", {
                    "result": DEMO_SEED_RESULTS[0] + redo, "status": "done", "issues": [], "assumptions": []})]
    if who == "reviewer":
        return [fake.call("Read", {"file_path": "docs/sales-report-method.md"}), fake.spend(0.003),
                fake.call("submit_report", {"result": DEMO_SEED_RESULTS[2] + redo, "status": "done",
                                            "issues": [], "assumptions": []})]
    if "email" in title.lower():
        return [fake.call("Read", {"file_path": "docs/sales-report-method.md"}), fake.spend(0.006),
                fake.call("Write", {"file_path": f"{folder}/summary-email.md", "content": "October sales"}),
                fake.call("submit_report", {"result": (
                    "**Subject: October sales**\n\nOctober sales came to 85.50 across both regions: Mugs 24.00 "
                    "(North), Prints 61.50 (South). One refunded order of 12.00 was left out. Nothing unusual "
                    "beyond the quiet month for mugs in the South. Full table attached (figures.csv)." + redo),
                    "status": "done", "issues": [], "assumptions": ["The team reads amounts in pounds"],
                    "files": ["summary-email.md"]})]
    return [fake.call("Read", {"file_path": "data/orders-2026-10.csv"}), fake.call("Bash", {"command": "python -c \"print(85.5)\""}),
            fake.call("Write", {"file_path": f"{folder}/figures.csv", "content": "line,north,south\n"}),
            fake.call("ask_question", {"title": "Round to whole pounds?", "body": "The method says two decimals; "
                      "the old report used whole pounds.", "recommended": "Two decimals, as the method says",
                      "options": ["Two decimals, as the method says", "Whole pounds"], "blocking": False}),
            fake.spend(0.01), fake.call("submit_report", {"result": DEMO_SEED_RESULTS[1] + redo, "status": "done",
                                                          "issues": [], "assumptions": [], "files": ["figures.csv"]})]


def _section(test: str, finding: str, strength: str, quote: str = "", source: str = "") -> dict:
    return {"test": test, "finding": finding, "strength": strength,
            "evidence": [{"quote": quote, "source": source}] if quote else []}


def reviewer_reply(msg: str) -> dict:
    """The fake Role Reviewer's structured reply for one turn (the role is named in the brief)."""
    m = re.search(r"Role under review: (\S+)", msg)
    role = m.group(1) if m else ""
    final = msg.startswith("Answers from the user")
    empty = {"name": "", "purpose": "", "description": "", "instructions": ""}
    if role == "data-migrator" or (final and "batches" in msg):
        if not final:
            return {"tests": [_section("value", "Steps repeat the same safety rules.", "moderate",
                                       "in batches of 500; keep the old table until counts match", "sample S1"),
                              _section("logic", "Is the batch rule always wanted? Asked below.", "weak"),
                              _section("history", "Four uses in one folder.", "moderate", "uses: 4", "tally"),
                              _section("fixes", "One step failed.", "moderate", "ended failed", "tally U2"),
                              _section("independent", "Depends on the answer.", "weak")],
                    "history_thin": False, "verdict": "not_yet", "reason": "Waiting for one answer.",
                    "skill_notes": "", "proposal": empty,
                    "questions": [{"test": "logic", "question": "Should every migration run in batches of 500?",
                                   "why": "The steps repeat it, but no skill states it.",
                                   "recommended": "Yes, always in batches of 500"}]}
        return {"tests": [
            _section("value", "Every migration step restates the same safety rules; an agent would hold them once.",
                     "moderate", "in batches of 500; keep the old table until counts match", "sample S1"),
            _section("logic", "Batch size, count checks and never dropping data appear in each step and in no skill.",
                     "strong", "check counts after each batch", "tally U2"),
            _section("history", "Four uses in one folder; the session folders are gone, so only tally lines and "
                                "samples were read.", "moderate", "U1-U4 data-migrator", "tally"),
            _section("fixes", "One step failed with three questions, one timed out.", "moderate",
                     "ended failed | questions 3 | assumptions 2 | timed out 1", "tally U2"),
            _section("independent", "The rules are procedure, not style: a subagent that always follows them is the "
                                    "right fix.", "moderate", "Yes, always in batches of 500", "user answer")],
            "history_thin": False, "verdict": "define",
            "reason": "Logic beyond any skill is strong and the failed backfill shows its cost.", "skill_notes": "",
            "proposal": {"name": "data-migrator", "purpose": "building",
                         "description": "Moves table data to a new table safely, in batches, checking counts.",
                         "instructions": "- Copy in batches of 500.\n- Check counts after each batch.\n"
                                         "- Never drop the old table or data."},
            "questions": []}
    if role == "frontend-dev":
        return {"tests": [
            _section("value", "The Builder did these steps without trouble.", "weak", "ended done", "tally U1"),
            _section("logic", "The repeated rule (stay responsive) belongs in the house-style skill.", "weak",
                     "keep it responsive on phones", "sample S1"),
            _section("history", "Steady use, all done.", "moderate", "uses: 3", "tally"),
            _section("fixes", "Nothing failed or was sent back.", "none"),
            _section("independent", "A better skill is the fix, not a subagent.", "moderate")],
            "history_thin": False, "verdict": "keep",
            "reason": "No failures and the only repeated rule fits the skill.",
            "skill_notes": "- Layouts stay responsive on phones.\n- Keep the existing colours unless the step says so.",
            "proposal": empty, "questions": []}
    return {"tests": [
        _section("value", "Too few uses to tell.", "none"), _section("logic", "No repeated instructions.", "none"),
        _section("history", "Two uses; history is thin.", "weak", "uses: 2", "tally"),
        _section("fixes", "Nothing failed.", "none"), _section("independent", "Keep counting.", "weak")],
        "history_thin": True, "verdict": "not_yet", "reason": "History is thin; keep counting.", "skill_notes": "",
        "proposal": empty, "questions": []}


def _project_files(project: Path, k: int = 3) -> list[str]:
    picks = [p for p in ("CLAUDE.md", "README.md", "docs/decisions.md", "app/server.py") if (project / p).is_file()]
    if len(picks) < k:
        for p in sorted(project.iterdir()):
            if p.is_file() and not p.name.startswith(".") and p.name not in picks:
                picks.append(p.name)
            if len(picks) >= k:
                break
    return picks[:k]


def _local_identity(git, repo: Path) -> None:
    """A neutral identity in the demo's own scratch repo only (so Commit works on a machine with none set)."""
    git(repo, "config", "--local", "user.name", "Launchpad Demo")
    git(repo, "config", "--local", "user.email", "demo@example.invalid")


def make_demo_repos(base: Path, shop: Path, clinic: Path) -> None:
    """Two small repos for the Repos panel, built in the demo's own temp folders (never a real repo): "shop-site"
    inside Demo shop (linked to a local bare remote, one commit ahead, three changed files) and Demo clinic itself
    (no remote: shows "Not linked", clean). Best-effort: without git installed the demo just has no repos."""
    import shutil
    import subprocess
    exe = shutil.which("git")
    if exe is None:
        return
    ident = ["-c", "user.name=Demo", "-c", "user.email=demo@example.invalid", "-c", "commit.gpgsign=false"]

    def git(where: Path, *args: str) -> None:
        subprocess.run([exe, "-C", str(where), *ident, *args], check=True, capture_output=True, stdin=subprocess.DEVNULL,
                       timeout=60, env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"})

    try:
        site, bare = shop / "shop-site", base / "remotes" / "shop-site.git"
        site.mkdir(parents=True)
        bare.mkdir(parents=True)
        git(bare, "init", "-q", "--bare", "-b", "main")
        git(site, "init", "-q", "-b", "main")
        _local_identity(git, site)
        (site / "index.html").write_text("<h1>Demo shop</h1>\n<p>Welcome.</p>\n", encoding="utf-8")
        (site / "styles.css").write_text("body { font-family: sans-serif; }\n", encoding="utf-8")
        (site / "notes.txt").write_text("todo: pricing page\n", encoding="utf-8")
        git(site, "add", "-A")
        git(site, "commit", "-q", "-m", "First version of the shop page")
        git(site, "remote", "add", "origin", str(bare))
        git(site, "push", "-q", "-u", "origin", "main")
        (site / "styles.css").write_text("body { font-family: sans-serif; color: #222; }\n", encoding="utf-8")
        git(site, "commit", "-q", "-am", "Darker text")                         # one commit ahead of the remote
        (site / "index.html").write_text("<h1>Demo shop</h1>\n<p>Welcome.</p>\n<p>Free delivery over 50.</p>\n", encoding="utf-8")
        (site / "pricing.md").write_text("# Pricing\n\n- Small: 9.00\n- Large: 14.00\n", encoding="utf-8")
        (site / "notes.txt").unlink()
        git(clinic, "init", "-q", "-b", "main")
        _local_identity(git, clinic)
        git(clinic, "add", "-A")
        git(clinic, "commit", "-q", "-m", "Clinic scripts")
    except (OSError, subprocess.SubprocessError):
        pass                                            # a half-made demo repo is fine; the panel shows what exists


def install(project: Path) -> None:
    """Register fake scripts for the four Launchpad agents (names from their app/agents/<folder>/agent.md files)."""
    project = Path(project).resolve()
    files = _project_files(project) or ["(none)"]

    # ---------------------------------------------------------------- planner
    round_1 = [
        {"id": "audience", "question": "Who is the page for?", "why": "Sets the tone of the copy.",
         "options": ["New visitors", "Existing users", "Both"], "recommended": "New visitors"},
        {"id": "scope", "question": "Copy only, or layout changes too?", "why": "Layout work adds a step.",
         "options": ["Copy only", "Copy and layout"], "recommended": "Copy only"},
        {"id": "publish", "question": "Publish at the end of the run?", "why": "Publishing needs a push.",
         "recommended": "Yes, after tests pass"},
    ]

    edited = {"done": False}

    def planner_later(msg: str) -> list:
        pick = re.search(r'\[Launchpad\] Visual pick: set \S+ ".*?" -> "(.+?)" \(saved: (.+?)\)', msg)
        if pick:
            return [fake.spend(0.004), fake.say(f"Noted: the **{pick.group(1)}** look ({pick.group(2)}). "
                                               "I will point the builder at that file.")]
        if "[Launchpad] The run finished" in msg:          # send-back: a revised draft to approve again
            return [fake.spend(0.004), fake.say("The run is done: copy drafted, wired in, tests run. One assumption "
                                               "was made by the timer. I drafted a short round 2 from the report; "
                                               "approve it to run it."),
                    fake.call("write_plan", PLAN_ROUND_2)]
        lib = DEMO_LIBRARY_WORDS.search(msg)
        if lib:                                           # "show me plotly": a set in that library (or its fallback)
            return [fake.spend(0.003), fake.call("show_visuals", {
                "brief": f"Monthly visitors, new vs returning, in {lib.group(1)}",
                "options": ["Line with markers", "Bar"], "library": lib.group(1)}),
                fake.say(f"Two {lib.group(1)} looks are in the panel.")]
        if not edited["done"]:                            # any other message: an edit-based revision
            edited["done"] = True
            return [fake.spend(0.004), fake.call("edit_plan", {"edits": [
                {"op": "rename", "name": "Demo: refresh the landing page and changelog"},
                {"op": "add_step", "title": "Write the changelog entry", "details": "Add one line to CHANGELOG.md "
                 "describing the new landing page.", "done_when": "The entry is in CHANGELOG.md.", "after": [3]}]}),
                fake.say("Renamed the plan and added a changelog step at the end.")]
        return [fake.say("(demo) I am a scripted planner. Press New session to replay the demo.")]

    fake.script("launchpad-planner", [
        [fake.spend(0.006),
         fake.call("promote_planner", {"reason": "Multi-part change (copy, page, publishing) with choices to weigh."}),
         fake.spend(0.012), fake.say("Happy to plan that. Three quick questions first."), fake.ask(round_1)],
        [fake.spend(0.02), fake.say("Thanks. A few design questions first: looks for the charts (ECharts, "
                                    "Chart.js, D3, and the notebook's matplotlib style) and for the page itself "
                                    "(palette, hero card). Pick any in the panel if you like; otherwise I assume "
                                    "nothing.")]
        + [fake.call("show_visuals", {"brief": b, "options": o, **({"library": lib} if lib else {})})
           for b, o, lib in VISUAL_SETS]
        + [fake.say("Meanwhile, sending the Explorer to look around the project."),
           fake.call("explore", {"question": "Where are the project's main docs and entry point?"}),
           fake.call("write_plan", PLAN),
           fake.say("Draft plan saved: 4 steps; the copy review goes to this folder's **copy-reviewer**. Review it "
                    "and press Approve to launch.")],
    ] + [planner_later] * 50)

    # ---------------------------------------------------------------- astronaut
    def astronaut(msg: str) -> list:
        if msg.startswith('Workflow "'):                  # a workflow stage (app/workflows/runner.py)
            return workflow_stage_turn(msg, "astronaut")
        links = [{"path": f, "answer": f"{f} explains how this part of the project is organised."} for f in files
                 if f != "(none)"]
        if links:
            links[0]["line"] = 1
        return [fake.call("Glob", {"pattern": "**/*.md"}), fake.call("Read", {"file_path": files[0]}),
                fake.spend(0.002),
                fake.output({"links": links, "routing_notes": "Glob on **/*.md returned many files; a narrower "
                                                             "pattern would have saved one call."})]

    fake.script("launchpad-astronaut", [astronaut])
    fake.script("launchpad-visual", [visual_turn])

    # ---------------------------------------------------------------- orchestrator
    plan_size = {"steps": len(PLAN["steps"])}

    def orchestrator(msg: str) -> list:
        if msg.startswith("Run the approved plan"):       # kickoff lists the steps: "1. title" lines
            section = msg.split("Steps:", 1)[1].split("---", 1)[0]
            plan_size["steps"] = len(re.findall(r"(?m)^\d+\. ", section))
        m = re.search(r"Step (\d+) result", msg)
        nxt = int(m.group(1)) + 1 if m else 1
        if nxt <= plan_size["steps"]:
            return [fake.spend(0.008), fake.say(f"Starting step {nxt}."),
                    fake.call("run_builder", {"step": nxt, "brief": BRIEFS.get(nxt, "Do this step as the plan says.")})]
        return [fake.spend(0.01), fake.call("write_report", {
            "summary": "All steps ran. The landing copy was drafted, wired into the page, reviewed by the copy "
                       "reviewer and the change was pushed after the tests passed.",
            "built": ["demo-output/landing.md: new landing copy", "Landing page hero: shows the new copy",
                      "Pushed change: published after tests", "Copy review: two small findings"],
            "issues": ["A write outside the project was refused in step 2 (no impact)."]})]

    fake.script("launchpad-orchestrator", [orchestrator] * 20)

    # ---------------------------------------------------------------- builder
    def builder(msg: str) -> list:
        if msg.startswith('Workflow "'):                  # a workflow stage (app/workflows/runner.py)
            return workflow_stage_turn(msg, "builder")
        m = re.search(r"Build step (\d+)", msg)
        n = int(m.group(1)) if m else 1
        if "round 2" in msg or n >= 4:                    # revised plans and added steps: quick, no cards
            return [fake.call("Read", {"file_path": "demo-output/landing.md"}),
                    fake.call("Edit", {"file_path": "demo-output/landing.md", "old_string": "New", "new_string": "Fresh"}),
                    fake.call("Bash", {"command": "python -m pytest -q"}), fake.spend(0.01),
                    fake.call("submit_report", {"built": [{"item": f"Round 2 step {n}", "does": "Done quickly"}],
                                                "assumptions": [], "issues": [], "notes_for_orchestrator": "Done.",
                                                "routing_notes": "", "status": "done"})]
        if n == 1:
            return [
                fake.call("Read", {"file_path": files[0]}),
                fake.call("Glob", {"pattern": "**/*.html"}),
                fake.call("Grep", {"pattern": "hero|tagline", "path": "."}),
                fake.call("Read", {"file_path": files[-1]}),
                fake.call("Bash", {"command": "ls demo-output"}),
                fake.call("Write", {"file_path": "demo-output/landing.md", "content": "# New landing copy"}),
                fake.call("Edit", {"file_path": "demo-output/landing.md", "old_string": "New", "new_string": "Fresh"}),
                fake.call("add_to_flight_log", {"path": files[-1], "why": "Holds the project rules the copy must respect."}),
                fake.call("ask_question", {"title": "Headline length?", "body": "Short punchy headline or a "
                          "descriptive one?", "recommended": "Short (under 8 words)",
                          "options": ["Short (under 8 words)", "Descriptive (one sentence)"], "blocking": False}),
                fake.spend(0.03),
                fake.call("submit_report", {
                    "built": [{"item": "demo-output/landing.md", "does": "Holds the new headline, intro and feature blurbs"}],
                    "assumptions": ["Tone is plain and friendly, as the brief said"], "issues": [],
                    "notes_for_orchestrator": "Copy ready for step 2.",
                    "routing_notes": "Read the whole CLAUDE.md when only the rules section was needed.",
                    "status": "done"}),
            ]
        if n == 2:
            return [
                fake.call("ask_question", {"title": "Replace or keep the old tagline?", "body": "The page has a "
                          "tagline under the hero. Replacing it changes the brand line.", "recommended": "Keep it",
                          "options": ["Keep it", "Replace it"], "blocking": True}),
                fake.call("Grep", {"pattern": "class=\"hero\"", "path": "demo-output"}),
                fake.call("Read", {"file_path": "demo-output/landing.md"}),
                fake.call("Edit", {"file_path": "demo-output/page.html", "old_string": "old", "new_string": "new"}),
                fake.call("Bash", {"command": "python -m http.server --help"}),
                fake.call("Write", {"file_path": "../outside-launchpad.txt", "content": "should be refused"}),
                fake.spend(0.04),
                fake.call("submit_report", {
                    "built": [{"item": "demo-output/page.html hero", "does": "Shows the new copy with the old styles"}],
                    "assumptions": [], "issues": [], "notes_for_orchestrator": "Page updated.",
                    "routing_notes": "", "status": "done"}),
            ]
        return [
            fake.call("Glob", {"pattern": "tests/**/*.py"}),
            fake.call("Bash", {"command": "python -m pytest -q"}),
            fake.call("Bash", {"command": "git status --short"}),
            fake.call("Bash", {"command": "git push origin main"}),
            fake.spend(0.02),
            fake.call("submit_report", {
                "built": [{"item": "Test run", "does": "All tests passed"},
                          {"item": "git push", "does": "Published the change (if you allowed it)"}],
                "assumptions": [], "issues": [], "notes_for_orchestrator": "Done.",
                "routing_notes": "Two shell calls; fine.", "status": "done"}),
        ]

    def builder_nudge(msg: str) -> list:
        return [fake.call("submit_report", {"built": [], "assumptions": [], "issues": ["Stopped early"],
                                            "notes_for_orchestrator": "", "routing_notes": "", "status": "blocked"})]

    fake.script("launchpad-builder", [builder, builder_nudge])

    # ---------------------------------------------------------------- folder agent (copy-reviewer, read-only)
    def copy_reviewer(msg: str) -> list:
        if msg.startswith('Workflow "'):
            return workflow_stage_turn(msg, "reviewer")
        return [fake.call("Read", {"file_path": "demo-output/landing.md"}),
                fake.call("Grep", {"pattern": "teh|recieve|seperate", "path": "demo-output"}),
                fake.call("Write", {"file_path": "demo-output/landing.md", "content": "fixed"}),   # refused: read-only
                fake.spend(0.004),
                fake.call("submit_report", {
                    "built": [{"item": "Copy review of demo-output/landing.md", "does": "Two findings listed below"}],
                    "assumptions": [], "issues": ["Headline is 9 words; the brief asked for under 8",
                                                  "Second feature blurb repeats the intro"],
                    "notes_for_orchestrator": "Copy is fine to ship after the two small fixes.",
                    "routing_notes": "", "status": "done"})]

    fake.script(FOLDER_AGENT_NAME, [copy_reviewer, builder_nudge])

    # ---------------------------------------------------------------- agent drafter (Crew: "Draft for me")
    def drafter(msg: str) -> list:
        text = msg.split("does this:", 1)[-1].strip()
        fields = draft_fields(text)
        for key, label in (("name", "name"), ("purpose", "purpose"), ("description", "description")):
            m = re.search(rf"Reviewer's proposed {label}: (.+)", msg)          # define path: the case as context
            if m and m.group(1).strip() != "(none)":
                fields[key] = m.group(1).strip()
        m = re.search(r"Instructions the agent needs beyond the skill:\n(.+?)(?:\nWhy the reviewer|\nThe user wants)", msg, re.S)
        if m and m.group(1).strip() != "(none)":
            fields["instructions"] = m.group(1).strip()
        return [fake.spend(0.0004), fake.output(fields)]

    fake.script("launchpad-drafter", [drafter] * 50)

    # ---------------------------------------------------------------- Role Reviewer (Crew: Review)
    def role_reviewer(msg: str) -> list:
        paths = re.findall(r"^- (?:Builder definition|step report|run report): (\S+?)(?: \(|$)", msg, re.M)
        reads = [fake.call("Read", {"file_path": p}) for p in paths[:3]]
        return reads + [fake.spend(0.006), fake.output(reviewer_reply(msg))]

    fake.script("launchpad-role-reviewer", [role_reviewer, role_reviewer])

    # ---------------------------------------------------------------- CLI chat (role key pilot)
    question = {"question": "Which tone should the notes use?", "header": "Tone",
                "options": [{"label": "Plain", "description": "Short sentences"},
                            {"label": "Friendly", "description": "Warmer wording"}], "multiSelect": False}

    def pilot(msg: str) -> list:
        if "plan" in msg.lower():                  # switch to Plan mode first, then say "plan"
            return [fake.say("Let me look around before proposing anything."),
                    fake.call("Read", {"file_path": files[0]}), fake.call("Grep", {"pattern": "TODO"}),
                    fake.plan("1. Create notes/pilot-demo.md with a short summary of the project.\n"
                              "2. Add a line to it listing the open TODOs."),
                    fake.call("Write", {"file_path": "notes/pilot-demo.md", "content": "# Notes"}),
                    fake.call("Edit", {"file_path": "notes/pilot-demo.md", "old_string": "# Notes",
                                       "new_string": "# Project notes"}),
                    fake.spend(0.01), fake.say("Plan carried out (or held back if you rejected it).")]
        return [fake.say("Sure, taking a look."),
                fake.call("Read", {"file_path": files[0]}), fake.call("Glob", {"pattern": "**/*.md"}),
                fake.call("Grep", {"pattern": "def |function "}),
                fake.call("Bash", {"command": "npm test"}),
                fake.call("Write", {"file_path": "notes/pilot-demo.md", "content": "# Notes"}),
                fake.call("Edit", {"file_path": "notes/pilot-demo.md", "old_string": "Notes", "new_string": "Project notes"}),
                fake.call("AskUserQuestion", {"questions": [question]}),
                fake.spend(0.012),
                fake.say("Done. Try **Accept edits** (edits stop asking) or **Plan** mode and send a message "
                         "containing \"plan\" to see a plan proposal.")]

    fake.script("launchpad-pilot", [pilot] * 50)
