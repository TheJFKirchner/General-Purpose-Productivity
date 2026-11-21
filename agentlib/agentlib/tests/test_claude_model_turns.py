"""Claude engine: model_turn on events from AssistantMessage.message_id (stub client, no process, no tokens)."""
import asyncio

from agentlib import Agent
from agentlib.engines import claude as ce          # SDK types via the engine module (no direct SDK import)
from agentlib.engines.claude import ClaudeSession


class _Client:
    def __init__(self, messages):
        self.messages = messages

    async def query(self, message):
        return None

    async def receive_response(self):
        for m in self.messages:
            yield m

    async def disconnect(self):
        return None

    async def interrupt(self):
        return None


def _say(text, mid, parent=None):
    return ce.AssistantMessage(content=[ce.TextBlock(text)], model="claude-haiku", message_id=mid,
                               parent_tool_use_id=parent)


def _use(cid, mid, path="a.md"):
    return ce.AssistantMessage(content=[ce.ToolUseBlock(cid, "Read", {"file_path": path})], model="claude-haiku",
                               message_id=mid)


def _result_block(cid):
    return ce.UserMessage(content=[ce.ToolResultBlock(cid, "file text")])


def _done():
    return ce.ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                            session_id="sid", total_cost_usd=0.01, usage={"input_tokens": 5, "output_tokens": 3})


def _turn(s, messages):
    s._client = _Client(messages)

    async def go():
        q = asyncio.Queue()
        await s._turn("hi", q)
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out
    return asyncio.run(go())


def _session():
    return ClaudeSession(Agent("a", tools=["Read"], include_ask_user=False), resume=None, fork=False, cost_base=0)


def test_blocks_of_one_reply_share_a_number_and_late_results_keep_their_call_number():
    s = _session()
    evs = _turn(s, [
        _say("Reading two files", "m1"), _use("t1", "m1"), _use("t2", "m1", "b.md"),   # one reply, two calls
        _result_block("t1"),
        _use("t3", "m2", "c.md"),                                                      # next reply
        _result_block("t3"), _result_block("t2"),          # t2's result arrives after the next reply's call
        _say("Done.", "m3"), _done()])
    got = [(e.type, getattr(e, "id", None), e.model_turn) for e in evs[:-1]]
    assert got == [("text", None, 1), ("tool_call", "t1", 1), ("tool_call", "t2", 1), ("tool_result", "t1", 1),
                   ("tool_call", "t3", 2), ("tool_result", "t3", 2), ("tool_result", "t2", 1), ("text", None, 3)]
    reply = evs[-1].reply
    assert [(c.id, c.model_turn) for c in reply.tool_calls] == [("t1", 1), ("t2", 1), ("t3", 2)]
    assert reply.api_calls == 3


def test_numbers_run_on_over_the_session():
    s = _session()
    _turn(s, [_use("t1", "m1"), _result_block("t1"), _say("ok", "m2"), _done()])
    evs = _turn(s, [_use("t2", "m3"), _result_block("t2"), _done()])
    assert [e.model_turn for e in evs[:-1]] == [3, 3]


def test_without_message_id_a_new_reply_starts_after_tool_results():
    s = _session()
    evs = _turn(s, [_say("Reading", None), _use("t1", None), _use("t2", None), _result_block("t1"),
                    _result_block("t2"), _use("t3", None), _result_block("t3"), _done()])
    assert [e.model_turn for e in evs[:-1]] == [1, 1, 1, 1, 1, 2, 2]


def test_subagent_messages_do_not_count():
    s = _session()
    evs = _turn(s, [_use("t1", "m1"), _say("inner", "sub1", parent="t1"), _result_block("t1"),
                    _say("Done.", "m2"), _done()])
    assert [(e.type, e.model_turn) for e in evs[:-1]] == [("tool_call", 1), ("tool_result", 1), ("text", 2)]
