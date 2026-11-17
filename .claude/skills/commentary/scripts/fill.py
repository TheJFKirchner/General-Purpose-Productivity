#!/usr/bin/env python3
"""The fill action: put saved commentary into the deliverable.

Decks and reports: one-time static replace of {{commentary:<unit_id>}} in each
file listed in `deliverable_files`, written to <name>_filled<ext>. Supports
.pptx, .html/.htm, .md, .txt and other text files.

Dashboards: placeholders stay live (see runtime.py). For a standalone HTML
export, --export bakes in the latest commentary for every dimension combination
the export still lets the reader filter by, plus a small in-file lookup.

Usage:
  fill.py <plan>                                  decks / reports
  fill.py <plan> --drop-unverified                leave unverified bullets out
  fill.py <plan> --export dashboard.html [--fix line_of_business=Medicare] [--out export.html]
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PLACEHOLDER_RE, PlanError, load_plan  # noqa: E402
from runtime import CommentaryRuntime  # noqa: E402
from store import open_store  # noqa: E402


def shown_bullets(store, plan, as_of, drop_unverified) -> dict[str, list[str]]:
    out = {}
    for u in plan["units"]:
        r = store.latest(u["id"], as_of, {})
        if not r or r["status"] != "ok":
            out[u["id"]] = []
            continue
        out[u["id"]] = [b["text"] for b in r["bullets"] if not (drop_unverified and b.get("unverified"))]
    return out


def style_of(plan, uid):
    for u in plan["units"]:
        if u["id"] == uid:
            return (u.get("style") or {}).get("format", "bullets")
    return "bullets"


# ---------------------------------------------------------------- renderers

def render_text(path: Path, text: str, bullets: dict, plan) -> str:
    ext = path.suffix.lower()

    def rep(m):
        uid = m.group(1)
        bs = bullets.get(uid, [])
        para = style_of(plan, uid) == "paragraph"
        if ext in (".html", ".htm"):
            if not bs:
                return ""
            if para:
                return f'<p class="commentary">{html.escape(" ".join(bs))}</p>'
            return '<ul class="commentary">' + "".join(f"<li>{html.escape(b)}</li>" for b in bs) + "</ul>"
        # markdown and plain text: keep the placeholder line's indentation
        line_start = text.rfind("\n", 0, m.start()) + 1
        indent = text[line_start:m.start()]
        indent = indent if indent.strip() == "" else ""
        if not bs:
            return ""
        if para:
            return " ".join(bs)
        mark = "- " if ext in (".md", ".markdown") else "• "
        return ("\n" + indent).join(mark + b for b in bs)

    return PLACEHOLDER_RE.sub(rep, text)


def render_pptx(src: Path, dst: Path, bullets: dict, plan) -> list[str]:
    from pptx import Presentation

    prs = Presentation(str(src))
    seen = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            tf = shape.text_frame
            for p in list(tf.paragraphs):
                m = PLACEHOLDER_RE.search(p.text)
                if not m:
                    continue
                uid = m.group(1)
                seen.append(uid)
                bs = bullets.get(uid, [])
                if style_of(plan, uid) == "paragraph" and bs:
                    bs = [" ".join(bs)]
                # keep the placeholder paragraph's formatting; write first bullet into it
                runs = p.runs
                first_run = runs[0] if runs else None
                for r in runs[1:]:
                    r._r.getparent().remove(r._r)
                if first_run is None:
                    first_run = p.add_run()
                first_run.text = bs[0] if bs else ""
                anchor = p._p
                for b in bs[1:]:
                    new_p = copy.deepcopy(p._p)
                    anchor.addnext(new_p)
                    anchor = new_p
                    rs = new_p.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}r")
                    for extra in rs[1:]:
                        extra.getparent().remove(extra)
                    t = rs[0].find("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
                    t.text = b
    prs.save(str(dst))
    return seen


# ---------------------------------------------------------------- export

EXPORT_JS = """
<script id="commentary-data" type="application/json">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('commentary-data').textContent);
  var esc = function (s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; };
  window.Commentary = {
    data: D,
    update: function (filters) {
      document.querySelectorAll('[data-commentary-unit]').forEach(function (el) {
        var uid = el.getAttribute('data-commentary-unit');
        var dims = D.dims[uid] || [];
        var key = dims.map(function (d) { return d + '=' + filters[d]; }).join('|');
        var bs = (D.rows[uid] || {})[key] || [];
        el.innerHTML = bs.length ? '<ul class="commentary">' + bs.map(function (b) { return '<li>' + esc(b) + '</li>'; }).join('') + '</ul>' : '';
      });
    }
  };
  if (window.__commentaryFilters) window.Commentary.update(window.__commentaryFilters);
  document.dispatchEvent(new CustomEvent('commentary-ready'));
})();
</script>
"""


def export_dashboard(plan, plan_dir, store, src: Path, out: Path, fixed: dict, shell_path: Path):
    rows = list(store.rows())  # runtime picks the latest version per key; failed latest → blank
    if fixed:
        rows = [r for r in rows if all(str(r.get(d, "all")) in (str(v), "all") for d, v in fixed.items())]
    rt = CommentaryRuntime.from_plan(shell_path, rows)
    data = rt.to_export()
    text = src.read_text()
    text = PLACEHOLDER_RE.sub(lambda m: f'<div class="commentary-slot" data-commentary-unit="{m.group(1)}"></div>', text)
    js = EXPORT_JS.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    text = text.replace("</body>", js + "\n</body>") if "</body>" in text else text + js
    out.write_text(text)
    n = sum(len(v) for v in data["rows"].values())
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--as-of")
    ap.add_argument("--drop-unverified", action="store_true")
    ap.add_argument("--export", help="dashboard HTML to export with commentary baked in")
    ap.add_argument("--out")
    ap.add_argument("--fix", action="append", default=[], help="dim=value the export no longer lets readers change")
    args = ap.parse_args(argv)
    try:
        plan, plan_dir = load_plan(args.plan)
    except PlanError as e:
        print(f"SHELL ERROR: {e}")
        return 2

    if plan.get("medium") == "dashboard":
        if not args.export:
            print("Dashboards resolve placeholders at run time (runtime.py). Use --export for a standalone HTML file.")
            return 0
        store = open_store(plan, plan_dir)
        src = (plan_dir / args.export).resolve()
        out = Path(args.out).resolve() if args.out else src.with_name(src.stem + "_export.html")
        fixed = dict(kv.split("=", 1) for kv in args.fix)
        n = export_dashboard(plan, plan_dir, store, src, out, fixed, Path(args.plan).resolve())
        print(f"Export written: {out} ({n} commentary rows baked in)")
        return 0

    store = open_store(plan, plan_dir)
    rows = store.rows()
    if not rows:
        print("No commentary saved yet. Run generate first.")
        return 1
    as_of = args.as_of or (plan_dir and max(str(r["as_of"]) for r in rows))
    bullets = shown_bullets(store, plan, as_of, args.drop_unverified)
    blank = [u for u, b in bullets.items() if not b]
    for f in plan.get("deliverable_files") or []:
        src = (plan_dir / f).resolve()
        dst = src.with_name(src.stem + "_filled" + src.suffix)
        if src.suffix.lower() == ".pptx":
            render_pptx(src, dst, bullets, plan)
        else:
            dst.write_text(render_text(src, src.read_text(), bullets, plan))
        print(f"Filled: {dst}")
    if blank:
        print(f"Left blank (failed or missing): {', '.join(blank)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
