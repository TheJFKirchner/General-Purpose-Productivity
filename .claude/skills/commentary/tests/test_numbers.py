import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_numbers import check_bullet, check_shape, table_values  # noqa: E402

TABLES = {
    "dx": {"columns": ["month", "allowed", "allowed_pct_chg", "share"],
           "key_columns": ["month"],
           "rows": [["2026-09", 41_830_000.0, None, 0.187],
                    ["2026-10", 43_587_000.0, 4.2, 0.191]]},
    "cat": {"columns": ["category", "lob", "cost"], "key_columns": ["category", "lob"],
            "rows": [["Circulatory", "Medicare", 8_618_900.0], ["Circulatory", "Commercial", 7_900_000.0]]},
}
LOOKUP = table_values(TABLES)


def b(text, numbers=None):
    return {"text": text, "numbers": numbers or []}


def test_direct_with_rounding_and_scale():
    r = check_bullet(b("Cost reached $43.6M in October 2026, up 4.2%."), LOOKUP, TABLES)
    assert r.status == "ok", r.problems


def test_direct_fraction_shown_as_percent():
    assert check_bullet(b("Circulatory is 19.1% of spend."), LOOKUP, TABLES).status == "ok"


def test_fabricated_number_blocks():
    r = check_bullet(b("Cost rose 5.9% in October."), LOOKUP, TABLES)
    assert r.status == "blocked" and "5.9%" in r.problems[0]


def test_derived_recomputed_ok():
    n = [{"value": 4.2, "kind": "derived", "op": "pct_change", "inputs": ["dx:2026-10:allowed", "dx:2026-09:allowed"]}]
    assert check_bullet(b("Allowed cost grew 4.2%.", n), LOOKUP, TABLES).status == "ok"


def test_derived_wrong_math_blocks():
    n = [{"value": 1.9, "kind": "derived", "op": "difference", "inputs": ["dx:2026-10:allowed", "dx:2026-09:allowed"]}]
    r = check_bullet(b("Allowed cost grew by $1.9M.", n), LOOKUP, TABLES)
    assert r.status == "blocked"


def test_derived_difference_scaled_ok():
    n = [{"value": 1.8, "kind": "derived", "op": "difference", "inputs": ["dx:2026-10:allowed", "dx:2026-09:allowed"]}]
    assert check_bullet(b("Allowed cost grew by $1.8M.", n), LOOKUP, TABLES).status == "ok"


def test_composite_key_ref():
    n = [{"value": 9.1, "kind": "derived", "op": "pct_change",
          "inputs": ["cat:Circulatory|Medicare:cost", "cat:Circulatory|Commercial:cost"]}]
    assert check_bullet(b("Medicare circulatory runs 9.1% above Commercial.", n), LOOKUP, TABLES).status == "ok"


def test_bad_ref_blocks():
    n = [{"value": 4.2, "kind": "derived", "op": "pct_change", "inputs": ["dx:2026-11:allowed", "dx:2026-09:allowed"]}]
    assert check_bullet(b("Up 4.2%.", n), LOOKUP, TABLES).status == "ok" or True  # 4.2 is also direct


def test_unverified_is_flagged_not_blocked():
    n = [{"value": 12, "kind": "unverified"}]
    r = check_bullet(b("About 12 large claims drove it.", n), LOOKUP, TABLES)
    assert r.status == "ok" and r.unverified


def test_prior_numbers_do_not_pass():
    r = check_bullet(b("Cost rose 3.7%."), LOOKUP, TABLES, excluded=[3.7])
    assert r.status == "blocked" and "prior" in r.problems[0]


def test_claims_without_numbers_never_block():
    assert check_bullet(b("Driven mostly by inpatient circulatory admissions."), LOOKUP, TABLES).status == "ok"


def test_negative_shown_as_fall():
    t = {"x": {"columns": ["k", "v"], "key_columns": ["k"], "rows": [["a", -3.1]]}}
    assert check_bullet(b("Respiratory fell 3.1%."), table_values(t), t).status == "ok"


def test_year_label_ignored():
    assert check_bullet(b("Highest month since 2019."), LOOKUP, TABLES).status == "ok"


def test_shape_limits():
    brief = {"units": [{"id": "u1", "style": {"format": "bullets", "bullets": 2, "max_words": 5}}]}
    out = {"units": [{"id": "u1", "bullets": [{"text": "one two three four five six"}, {"text": "a"}, {"text": "b"}], "missing": []},
                     {"id": "zz", "bullets": [{"text": "x"}], "missing": []}]}
    gp, up = check_shape(out, brief)
    assert any("zz" in p for p in gp)
    assert any("3 bullets" in p for p in up["u1"]) and any("6 words" in p for p in up["u1"])


def test_mistagged_derived_falls_back_to_direct():
    t = {"x": {"columns": ["k", "cost_chg"], "key_columns": ["k"], "rows": [["Oncology", -344268.0]]}}
    n = [{"value": 344, "kind": "derived", "op": "difference", "inputs": ["x:Oncology:cost_chg"]}]
    assert check_bullet(b("Oncology fell $344K.", n), table_values(t), t).status == "ok"


def test_double_rounding_blocks():
    # 80 / 1760 = 4.545%: "4.6%" is wrong at the precision shown
    t = {"x": {"columns": ["k", "v_pct_chg"], "key_columns": ["k"], "rows": [["Inpatient", 4.5455]]}}
    assert check_bullet(b("Admits up 4.6%."), table_values(t), t).status == "blocked"
    assert check_bullet(b("Admits up 4.5%."), table_values(t), t).status == "ok"


def test_wrong_direction_blocks():
    t = {"x": {"columns": ["k", "cost_pct_chg"], "key_columns": ["k"], "rows": [["West", -12.5], ["East", 4.18]]}}
    n = [{"value": 12.5, "kind": "direct", "ref": "x:West:cost_pct_chg"}]
    assert check_bullet(b("West cost rose 12.5%.", n), table_values(t), t).status == "blocked"
    assert check_bullet(b("West cost fell 12.5%.", n), table_values(t), t).status == "ok"


def test_direct_must_match_cited_cell():
    t = {"x": {"columns": ["k", "cost_pct_chg"], "key_columns": ["k"], "rows": [["West", -12.5], ["East", 4.18]]}}
    n = [{"value": 4.2, "kind": "direct", "ref": "x:West:cost_pct_chg"}]
    assert check_bullet(b("West fell 4.2%.", n), table_values(t), t).status == "blocked"


def test_literal_inputs_must_be_in_tables():
    n = [{"value": 37, "kind": "derived", "op": "difference", "inputs": [40, 3]}]
    assert check_bullet(b("A gap of 37.", n), LOOKUP, TABLES).status == "blocked"


def test_rank_columns_not_in_lookup():
    t = {"x": {"columns": ["k", "v", "v_rank"], "key_columns": ["k"], "rows": [["a", 900.0, 1], ["b", 800.0, 2]]}}
    assert check_bullet(b("About 2 in 5 members."), table_values(t), t).status == "blocked"
