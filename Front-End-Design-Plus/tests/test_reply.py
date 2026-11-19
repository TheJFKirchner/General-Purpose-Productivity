"""The plain-text reply parser."""
import random

from whiteboard.reply import ReplyParser, parse

REPLY = """@card chart G1 | Revenue by region, horizontal bars
```js
const c = lib.init(el);
c.setOption({yAxis: {type: 'category'}});
```
@card table - | Top 10 orders
```
el.innerHTML = '<table></table>';
```
@say G2 horizontal bars, G3 a table of the top orders.
"""


def cards(events):
    return [e for e in events if e["kind"] == "card"]


def test_full_reply():
    evs = parse(REPLY)
    assert [e["kind"] for e in evs] == ["card", "card", "text"]
    a, b = cards(evs)
    assert (a["card_kind"], a["parent"], a["title"], a["fix"]) == ("chart", "G1", "Revenue by region, horizontal bars", None)
    assert a["code"] == "const c = lib.init(el);\nc.setOption({yAxis: {type: 'category'}});"
    assert (b["card_kind"], b["parent"], b["title"]) == ("table", None, "Top 10 orders")
    assert evs[2]["text"] == "G2 horizontal bars, G3 a table of the top orders."


def test_streamed_in_random_chunks_gives_the_same_events():
    rng = random.Random(7)
    for _ in range(20):
        p, evs, i = ReplyParser(), [], 0
        while i < len(REPLY):
            n = rng.randint(1, 15)
            evs += p.feed(REPLY[i:i + n])
            i += n
        evs += p.finish()
        assert evs == parse(REPLY)


def test_fix_header():
    (e,) = parse("@fix g3 | Sales, fixed\n```js\nel.textContent = 'ok';\n```\n")
    assert (e["kind"], e["fix"], e["title"], e["code"]) == ("card", "G3", "Sales, fixed", "el.textContent = 'ok';")


def test_lenient_cases():
    # header fields optional; Windows line endings; unclosed last block still accepted
    evs = parse("@card | Bare title\r\n```js\r\nel.textContent = 1;\r\n")
    assert [(e["card_kind"], e["parent"], e["title"], e["code"]) for e in cards(evs)] == [
        ("chart", None, "Bare title", "el.textContent = 1;")]
    # a code block with no header becomes an untitled chart card
    (e,) = parse("```js\nel.textContent = 2;\n```")
    assert e["kind"] == "card" and e["title"] == "" and e["card_kind"] == "chart"


def test_malformed_parts_become_notes_or_text():
    evs = parse("Here you go:\n@card chart - | Lost\n@card chart - | Kept\n```js\nx();\n```\n"
                "@card chart - | Empty\n```js\n```\n@say done")
    kinds = [(e["kind"], e.get("title") or e.get("text")) for e in evs]
    assert kinds[0] == ("text", "Here you go:")
    assert kinds[1][0] == "note" and "Lost" in kinds[1][1] and "without code" in kinds[1][1]
    assert kinds[2] == ("card", "Kept")
    assert kinds[3][0] == "note" and "empty code" in kinds[3][1]
    assert kinds[4] == ("text", "done")


def test_trailing_header_without_code_is_a_note():
    evs = parse("@say one\n@card chart - | Dangling")
    assert [e["kind"] for e in evs] == ["text", "note"]


def test_plain_prose_is_all_text():
    evs = parse("I cannot draw that.\nTry another column.")
    assert [e["text"] for e in evs] == ["I cannot draw that.", "Try another column."]
