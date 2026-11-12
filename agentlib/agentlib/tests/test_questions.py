import pytest

from agentlib import QuestionShapeError
from agentlib.questions import format_answers, parse_answers, parse_questions

Q = {"id": "trend_years", "question": "Which years?", "why": "Brief names no period.",
     "options": ["Last 3 years", "Last 5 years"], "recommended": "Last 5 years"}


def test_parse_questions_ok():
    qs = parse_questions({"questions": [Q, {"id": "region", "question": "Which region?", "why": "Unclear."}]})
    assert [q.id for q in qs] == ["trend_years", "region"]
    assert qs[0].recommended == "Last 5 years" and qs[1].options == []


@pytest.mark.parametrize("bad", [
    {},
    {"questions": []},
    {"questions": [{"id": "a", "question": "q"}]},                              # no why
    {"questions": [Q, Q]},                                                       # duplicate id
    {"questions": [{**Q, "options": ["only one"]}]},                             # 1 option
    {"questions": [{**Q, "colour": "red"}]},                                     # unknown field
])
def test_parse_questions_rejects(bad):
    with pytest.raises(QuestionShapeError):
        parse_questions(bad)


def test_parse_answers_kinds_and_skips():
    qs = parse_questions({"questions": [Q, {"id": "region", "question": "Which?", "why": "x"}]})
    a = parse_answers({"trend_years": "Last 5 years"}, qs)
    assert [(x.id, x.kind) for x in a] == [("trend_years", "recommended"), ("region", "skipped")]
    a = parse_answers([{"id": "trend_years", "answer": "Last 3 years"}, {"id": "region", "answer": "EMEA"}], qs)
    assert [x.kind for x in a] == ["option", "free_text"]


@pytest.mark.parametrize("given", [
    {"id": "trend_years", "kind": "recommended"},                     # no answer key at all
    {"id": "trend_years", "kind": "recommended", "answer": None},
    {"id": "trend_years", "kind": "recommended", "answer": True},
    {"id": "trend_years", "kind": "recommended", "answer": ""},
])
def test_recommended_without_text_uses_recommendation(given):
    qs = parse_questions({"questions": [Q]})
    from agentlib import Answer
    for item in (given, Answer(given["id"], given.get("answer"), "recommended")):
        [a] = parse_answers([item], qs)
        assert (a.answer, a.kind) == ("Last 5 years", "recommended")
    assert "(your recommendation)" in format_answers(parse_answers([given], qs))


def test_recommended_without_recommendation_is_skipped():
    qs = parse_questions({"questions": [{"id": "region", "question": "Which?", "why": "x"}]})
    [a] = parse_answers([{"id": "region", "kind": "recommended"}], qs)
    assert a.kind == "skipped" and a.answer is None


def test_parse_answers_unknown_id():
    qs = parse_questions({"questions": [Q]})
    with pytest.raises(QuestionShapeError):
        parse_answers({"nope": "x"}, qs)


def test_format_answers():
    qs = parse_questions({"questions": [Q]})
    text = format_answers(parse_answers({"trend_years": "Last 5 years"}, qs))
    assert "trend_years: Last 5 years (your recommendation)" in text
