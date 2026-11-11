"""Tests for editor/htmldoc.py.  Run:  python -m pytest tests  (or  python tests/test_htmldoc.py)"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "editor"))
import htmldoc as h  # noqa: E402

SAMPLE = HERE / "sample_report.html"
if not SAMPLE.exists():
    subprocess.run([sys.executable, str(HERE / "make_sample.py"), str(SAMPLE)], check=True)
SRC = SAMPLE.read_text(encoding="utf-8")


def doc():
    return h.Doc(SRC, "sample_report.html")


def everything_the_model_sees(d):
    out = [d.page_summary(), d.theme_text(), d.page_rules_text(), d.outline("n0", depth=99, max_lines=100000)]
    for nd in d.node_list[1:]:
        out.append(d.outline(nd.id, depth=3))
        out.append(d.around(nd.id))
    for q in ("Revenue", "North", "e", "2026"):
        out.append(d.find_text(q, limit=1000))
    return "\n".join(out)


def test_no_data_reaches_the_model():
    d = doc()
    seen = everything_the_model_sees(d)
    data = json.loads(re.search(r'<script type="application/json" id="raw-data">(.*?)</script>', SRC, re.S).group(1))
    for row in data[:300]:
        assert f"{row['revenue']:,.2f}" not in seen
        assert str(row["revenue"]) not in seen
    for row in data:
        assert row["month"] not in seen
    for value in ("12.4%", "$4.2M", "48,210", "31%", "2026-10-15", "$900K", ">West<", '"West"', '"Central"'):
        assert value not in seen, value
    assert "base64" not in seen and "JSON.parse" not in seen


def test_only_the_clicked_cell_shows_text():
    d = doc()
    td = next(nd for nd in d.node_list if nd.tag == "td")
    assert "[cell value hidden]" in d.outline(td.parent.id)
    assert "[cell value hidden]" not in d.outline(td.id, reveal=td.id)


def test_numbers_become_tokens():
    d = doc()
    out = d.outline("n11", depth=3)
    assert 'Revenue grew {#1} to {#2} this quarter' in out
    assert "12.4%" not in out and "$4.2M" not in out


def test_set_text_keeps_numbers_and_rest_of_file():
    d = doc()
    r = d.find_text("Revenue grew").split()[0]
    d.set_text(r, "Sales rose {#1} to {#2} this quarter, led by the", allowed_digits="")
    assert "Sales rose 12.4% to $4.2M this quarter" in d.src
    before, after = SRC.split("Revenue grew", 1)[0], SRC.split("this quarter, led by the", 1)[1]
    assert d.src.startswith(before) and d.src.endswith(after)
    assert d.undo() and d.src == SRC


def test_typed_numbers_refused_unless_user_typed_them():
    d = doc()
    r = d.find_text("Revenue grew").split()[0]
    try:
        d.set_text(r, "Revenue grew 99% to {#2}", allowed_digits="make it nicer")
        raise AssertionError("should refuse")
    except h.EditError as e:
        assert "typed number" in str(e)
    d.set_text(r, "Revenue grew 99% to {#2}", allowed_digits="say it grew 99%")
    assert "Revenue grew 99% to $4.2M" in d.src


def test_partial_edit_with_old_text():
    d = doc()
    r = d.find_text("preliminary").split()[0]
    d.set_text(r, "provisional", old_text="preliminary", allowed_digits="")
    assert "All figures are provisional until the close on 2026-10-15." in d.src


def test_shift_keeps_positions_right_for_later_edits():
    d = doc()
    d.set_text(d.find_text("Summary").split()[0], "Executive summary of the quarter", allowed_digits="")
    d.set_style("n11", {"border": "2px solid var(--accent)"})
    d.set_text("t14", "For leadership")
    footer = next(nd for nd in d.node_list if nd.tag == "footer")
    d.set_style(footer.id, {"color": "#555"})
    fresh = h.Doc(d.src)
    for nd, nd2 in zip(d.node_list, fresh.node_list):
        assert (nd.id, nd.tag, nd.start, nd.tag_end, nd.close_start, nd.end) == (nd2.id, nd2.tag, nd2.start, nd2.tag_end, nd2.close_start, nd2.end)
    for rid, r in d.runs.items():
        r2 = fresh.runs[rid]
        assert (r.start, r.end) == (r2.start, r2.end)
    assert 'style="margin: 0 32px 32px; color: #555"' in d.src


def test_style_attr_theme_rule():
    d = doc()
    d.set_style("n8", {"color": "gold", "font-size": "32px"})
    assert '<h1 style="color: gold; font-size: 32px">' in d.src
    d.set_style("n8", {"color": None})
    assert '<h1 style="font-size: 32px">' in d.src
    d.set_attr("n9", "class", "subtitle lead")
    assert '<p class="subtitle lead">' in d.src
    d.set_theme_var("v1", "#dc2626")
    assert "--accent: #dc2626;" in d.src
    d.set_page_rule(".card h2", "text-transform: uppercase; letter-spacing: .05em")
    d.set_page_rule("body", "background: #fff")
    assert d.page_rules() == [(".card h2", "text-transform: uppercase; letter-spacing: .05em;"), ("body", "background: #fff;")]
    d.set_page_rule(".card h2", "")
    assert d.page_rules() == [("body", "background: #fff;")]
    assert d.src.index('<style id="she-custom">') > d.src.index("</footer>")
    for bad in ({"color": "red; x: y"}, {"background": "url(evil)"}, {"bad prop": "1"}):
        try:
            d.set_style("n8", bad)
            raise AssertionError(f"should refuse {bad}")
        except h.EditError:
            pass


def test_hidden_parts_are_not_editable():
    d = doc()
    svg = next(nd for nd in d.node_list if nd.tag == "svg")
    script = next(nd for nd in d.node_list if nd.tag == "script")
    for fn in (lambda: d.set_style(svg.id, {"color": "red"}),
               lambda: d.set_text(next(c for c in script.children).id, "x"),
               lambda: d.set_attr("n8", "onclick", "alert(1)")):
        try:
            fn()
            raise AssertionError("should refuse")
        except h.EditError:
            pass


def test_markup_view_and_replace():
    d = doc()
    p = d.node(d.find_text("Revenue grew").split()[2])  # "t21 in n13 <p> ..."
    view = d.view_markup(p.id)
    assert "{#1}" in view and "12.4" not in view and "<b>North</b>" in view
    d.replace_markup(p.id, view.replace("<b>North</b>", "<strong>North</strong>"), allowed_digits="")
    assert "led by the <strong>North</strong> region. Units sold rose to 48,210." in d.src
    for bad in ('<script>x</script>', '<b onclick="x">y</b>', '<a href="javascript:x">y</a>'):
        try:
            d.replace_markup(p.id, bad, allowed_digits="")
            raise AssertionError(f"should refuse {bad}")
        except h.EditError:
            pass
    try:
        d.view_markup("n32")
        raise AssertionError("section with a data table must be refused")
    except h.EditError as e:
        assert "table" in str(e) or "too big" in str(e)


def test_undo_in_place_and_after_reparse():
    d = doc()
    seq = d.struct_seq
    d.set_style("n8", {"color": "red"})
    d.set_text("t14", "Hello")
    d.set_theme_var("v1", "#000000")
    for _ in range(3):
        d.undo()
    assert d.src == SRC and d.struct_seq == seq, "simple edits undo without renumbering"
    fresh = h.Doc(d.src)
    assert all((a.start, a.end, a.tag_end, a.close_start) == (b.start, b.end, b.tag_end, b.close_start)
               for a, b in zip(d.node_list, fresh.node_list))
    d.set_page_rule("h1", "color: red")
    d.set_style("n8", {"color": "blue"})
    d.undo()
    d.undo()
    assert d.src == SRC


def test_crlf_and_entities():
    src = '<html><body>\r\n<p class="a">Fish &amp; chips\r\n cost 5</p>\r\n</body></html>'
    d = h.Doc(src)
    r = d.find_text("Fish").split()[0]
    assert d.show_text(d.runs[r]) == '"Fish & chips cost {#1}"'
    d.set_text(r, "Fish & chips\ncost {#1}", allowed_digits="")
    assert "Fish &amp; chips\r\ncost 5" in d.src


def test_implied_closing():
    d = h.Doc("<ul><li>One<li>Two</ul><p>A<div>B</div><table><tr><td>1<td>2<tr><td>3</table>")
    tags = [(nd.tag, nd.parent.tag) for nd in d.node_list[1:]]
    assert tags == [("ul", "#document"), ("li", "ul"), ("li", "ul"), ("p", "#document"), ("div", "#document"),
                    ("table", "#document"), ("tr", "table"), ("td", "tr"), ("td", "tr"), ("tr", "table"), ("td", "tr")]


def test_served_html_only_adds_ids():
    d = doc()
    served = d.served_html()
    assert re.sub(r' data-she-id="n\d+"( data-she-mask="")?', "", served) == SRC
    assert '<td data-she-id="' in served and 'data-she-mask=""' in served


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    sys.exit(1 if fails else 0)
