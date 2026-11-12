"""The shared shape of ask_user questions and answers (material questions, not permissions).

- Question: id, question, why, options (0 or 2-4), recommended, multi_select
- Answer:   id, answer (str, or list[str] for multi_select), kind = option | recommended | free_text | skipped
- parse_questions(): validates the tool input the model sent -> list[Question] (QuestionShapeError if bad;
  the engine returns that error to the model so it can fix the call)
- parse_answers(): accepts Answer objects, dicts, or a plain {id: "text"} mapping; missing ids -> skipped;
  kind="recommended" with no answer (None / True / "") -> the question's recommended text (skipped if it has none)
- format_answers(): the message sent back to the agent (template: prompts/answers.md)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

from . import prompt_files
from .errors import QuestionShapeError

AnswerKind = Literal["option", "recommended", "free_text", "skipped"]
ANSWER_KINDS = ("option", "recommended", "free_text", "skipped")

_STR = {"type": "string"}
QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {**_STR, "description": "short snake_case label"},
        "question": _STR,
        "why": {**_STR, "description": "why this blocks you"},
        "options": {"type": "array", "items": _STR, "description": "2-4 choices; omit if open-ended"},
        "recommended": {**_STR, "description": "your suggested answer"},
        "multi_select": {"type": "boolean"},
    },
    "required": ["id", "question", "why"],
    "additionalProperties": False,
}
ASK_USER_SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": QUESTION_SCHEMA, "minItems": 1}},
    "required": ["questions"],
    "additionalProperties": False,
}


@dataclass
class Question:
    id: str
    question: str
    why: str
    options: list[str] = field(default_factory=list)
    recommended: str | None = None
    multi_select: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Answer:
    id: str
    answer: str | list[str] | None
    kind: AnswerKind

    def to_dict(self) -> dict:
        return asdict(self)


def _text(v: Any, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise QuestionShapeError(f"{what} must be a non-empty string")
    return v.strip()


def parse_questions(args: dict | None) -> list[Question]:
    raw = (args or {}).get("questions")
    if not isinstance(raw, list) or not raw:
        raise QuestionShapeError("'questions' must be a non-empty list")
    out: list[Question] = []
    seen: set[str] = set()
    for i, q in enumerate(raw, 1):
        if not isinstance(q, dict):
            raise QuestionShapeError(f"question {i} must be an object")
        extra = set(q) - set(QUESTION_SCHEMA["properties"])
        if extra:
            raise QuestionShapeError(f"question {i} has unknown fields: {sorted(extra)}")
        qid = _text(q.get("id"), f"question {i} 'id'")
        if qid in seen:
            raise QuestionShapeError(f"duplicate question id '{qid}'")
        seen.add(qid)
        opts = q.get("options") or []
        if not isinstance(opts, list) or not all(isinstance(o, str) and o.strip() for o in opts):
            raise QuestionShapeError(f"'{qid}' options must be a list of strings")
        if opts and not 2 <= len(opts) <= 4:
            raise QuestionShapeError(f"'{qid}' needs 2-4 options (or none), got {len(opts)}")
        rec = q.get("recommended")
        out.append(Question(
            id=qid,
            question=_text(q.get("question"), f"'{qid}' question"),
            why=_text(q.get("why"), f"'{qid}' why"),
            options=[o.strip() for o in opts],
            recommended=rec.strip() if isinstance(rec, str) and rec.strip() else None,
            multi_select=bool(q.get("multi_select", False)),
        ))
    return out


def questions_from_dicts(items: Iterable[dict | Question]) -> list[Question]:
    """Rebuild saved questions (e.g. Reply.questions stored as JSON before an app restart)."""
    return [q if isinstance(q, Question) else Question(**q) for q in items]


def _infer_kind(q: Question, ans: str | list[str]) -> AnswerKind:
    if isinstance(ans, list):
        return "option" if all(a in q.options for a in ans) else "free_text"
    if q.recommended and ans == q.recommended:
        return "recommended"
    return "option" if ans in q.options else "free_text"


def parse_answers(answers: Any, questions: list[Question]) -> list[Answer]:
    """Normalise answers against the open questions. Unknown ids raise; unanswered ids become skipped."""
    by_id = {q.id: q for q in questions}
    given: dict[str, Answer] = {}
    if isinstance(answers, dict) and "answers" not in answers:
        items = [{"id": k, "answer": v} for k, v in answers.items()]
    elif isinstance(answers, dict):
        items = answers["answers"]
    else:
        items = list(answers or [])
    for item in items:
        a = item.to_dict() if isinstance(item, Answer) else dict(item)
        qid = a.get("id")
        if qid not in by_id:
            raise QuestionShapeError(f"answer for unknown question id '{qid}'")
        q = by_id[qid]
        val, kind = a.get("answer"), a.get("kind")
        if kind == "recommended" and (val is None or val is True or val == ""):
            val = q.recommended                  # "accept the recommendation"; no recommendation -> skipped
        if kind == "skipped" or val is None or val == "" or val == []:
            given[qid] = Answer(qid, None, "skipped")
            continue
        if isinstance(val, list) and not q.multi_select:
            raise QuestionShapeError(f"'{qid}' is single-choice; got a list")
        if kind is None:
            kind = _infer_kind(q, val)
        if kind not in ANSWER_KINDS:
            raise QuestionShapeError(f"'{qid}' kind must be one of {ANSWER_KINDS}")
        given[qid] = Answer(qid, val, kind)
    return [given.get(q.id, Answer(q.id, None, "skipped")) for q in questions]


def format_answers(answers: list[Answer]) -> str:
    lines = []
    for a in answers:
        if a.kind == "skipped":
            lines.append(f"- {a.id}: SKIPPED")
        else:
            val = ", ".join(a.answer) if isinstance(a.answer, list) else a.answer
            lines.append(f"- {a.id}: {val}" + (" (your recommendation)" if a.kind == "recommended" else ""))
    return prompt_files.fill("answers", answers="\n".join(lines))
