"""05 - ask_user: the agent parks with questions; the app answers later (even after a restart).

Run:  python examples/05_ask_user.py          (fake engine, free)
      python examples/05_ask_user.py --live   (LIVE: uses your Claude login, costs tokens; haiku)

No raw SDK equivalent: ask_user is agentlib's own tool (agentlib/questions.py, prompts/ask_user_tool.md).
It is for material questions (scope, data, decisions), not tool permissions (see 06).
"""
import asyncio
import json
import sys

from agentlib import Agent

LIVE = "--live" in sys.argv
ENGINE = "claude" if LIVE else "fake"

if not LIVE:
    from agentlib import fake
    fake.script("reporter", [
        # Turn 1: the model calls ask_user. Question shape: id, question, why, options (0 or 2-4),
        # recommended, multi_select. The turn ends right after the call; later steps never run.
        [fake.ask([{"id": "period", "question": "Which period should the report cover?",
                    "why": "The request names no period.",
                    "options": ["Last 3 years", "Last 5 years"], "recommended": "Last 5 years"}]),
         fake.say("never reached")],
        # Turn 2: a step can be fn(message) -> steps; here it echoes what the model actually receives.
        lambda message: [fake.say("Model received:\n" + message)],
    ])

agent = Agent(
    "reporter",
    instructions=("You write one-line trend summaries. If the user has not said which period to cover, "
                  "ask with ask_user (one question, id 'period') before doing anything else."),
    engine=ENGINE, model="haiku",
    # tools=None (default) -> all given custom tools + ask_user. With an explicit tools list,
    # include "ask_user" yourself. include_ask_user=False turns it off when tools is None.
)


async def main() -> None:
    # --- Request: one-shot ask. The agent parks.
    r1 = await agent.ask("Write the sales trend summary.")
    print("status:", r1.status)                         # needs_input
    for q in r1.questions:
        print(f"  [{q.id}] {q.question} options={q.options} recommended={q.recommended!r}")

    # --- Save what you need to answer later (DB, JSON file, web session...).
    saved = json.dumps({"session_id": r1.session_id, "total_cost_usd": r1.total_cost_usd,
                        "questions": [q.to_dict() for q in r1.questions]})

    # --- Later / after a restart: resume and answer. questions= is required when the session object
    # that saw the questions is gone (inside the same session, s.pending_questions is used instead).
    state = json.loads(saved)
    async with agent.session(resume=state["session_id"], cost_base=state["total_cost_usd"]) as s:
        r2 = await s.answer({"period": "Last 3 years"}, questions=state["questions"])
        # Other accepted answer shapes (unanswered ids become "skipped"; unknown ids raise QuestionShapeError):
        #   [agentlib.Answer("period", "Last 3 years", "option")]
        #   {"answers": [{"id": "period", "answer": "Last 3 years"}]}
        #   [{"id": "period", "answer": True, "kind": "recommended"}]    -> uses q.recommended
        #   {}                                                            -> every question skipped
        # To watch the answer turn live instead: async for ev in s.answer_stream(answers, questions=...)
    print("status:", r2.status)
    print(r2.text)


asyncio.run(main())
