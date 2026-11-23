"""Claude engine: Reply.turn_usage from per-message usage and the raw stream (stand-in client, no process, no tokens)."""
import asyncio

from agentlib import Agent, AgentError, TurnUsage, Usage
from agentlib.engines import claude as ce          # SDK types via the engine module (no direct SDK import)
from agentlib.engines.claude import ClaudeSession


class _Client:
    def __init__(self, messages):
        self.messages = messages

    async def query(self, message):
        return None

    async def receive_response(self):
        for m in self.messages:
            if isinstance(m, Exception):
                raise m
            yield m

    async def disconnect(self):
        return None

    async def interrupt(self):
        return None


def _u(inp=0, out=0, cr=0, cw=0):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cw}


def _say(text, mid, usage=None, parent=None, model="claude-haiku"):
    return ce.AssistantMessage(content=[ce.TextBlock(text)], model=model, message_id=mid,
                               parent_tool_use_id=parent, usage=usage)


def _use(cid, mid, usage=None):
    return ce.AssistantMessage(content=[ce.ToolUseBlock(cid, "Read", {"file_path": f"{cid}.md"})],
                               model="claude-haiku", message_id=mid, usage=usage)


def _result(cid):
    return ce.UserMessage(content=[ce.ToolResultBlock(cid, "file text")])


def _ev(event, parent=None):
    return ce.StreamEvent(uuid="u", session_id="sid", event=event, parent_tool_use_id=parent)


def _start(mid, usage, model="claude-haiku"):
    return _ev({"type": "message_start", "message": {"id": mid, "model": model, "usage": usage}})


def _delta(usage):
    return _ev({"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": usage})


def _stop():
    return _ev({"type": "message_stop"})


def _done(usage):
    return ce.ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                            session_id="sid", total_cost_usd=0.01, usage=usage)


def _session():
    return ClaudeSession(Agent("a", tools=["Read"], include_ask_user=False), resume=None, fork=False, cost_base=0)


def _turn(s, messages):
    s._client = _Client(messages)

    async def go():
        q = asyncio.Queue()
        try:
            await s._turn("hi", q)
        except AgentError as e:
            return e
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out
    return asyncio.run(go())


def test_same_message_id_seen_several_times_is_not_double_counted():
    # one reply with text + two tool calls arrives as three AssistantMessages carrying the same usage
    u1 = _u(10, 30, 1000, 200)
    evs = _turn(_session(), [
        _say("Reading two", "m1", u1), _use("t1", "m1", u1), _use("t2", "m1", u1),
        _result("t1"), _result("t2"),
        _say("Done.", "m2", _u(5, 8, 1300, 0)), _done(_u(15, 38, 2300, 200))])
    r = evs[-1].reply
    assert r.turn_usage == [TurnUsage(1, Usage(10, 30, 1000, 200), "claude-haiku"),
                            TurnUsage(2, Usage(5, 8, 1300, 0), "claude-haiku")]
    total = r.turn_usage[0].usage + r.turn_usage[1].usage
    assert (total.input_tokens, total.output_tokens, total.cache_read_tokens, total.cache_write_tokens) == \
        (r.usage.input_tokens, r.usage.output_tokens, r.usage.cache_read_tokens, r.usage.cache_write_tokens)
    assert {c.model_turn for c in r.tool_calls} == {1}


def test_partial_output_on_block_messages_is_completed_by_message_delta():
    # blocks arrive with the output count from message_start (partial); message_delta has the final count
    evs = _turn(_session(), [
        _start("m1", _u(3, 1, 500, 50)),
        _say("Reading", "m1", _u(3, 1, 500, 50)), _use("t1", "m1", _u(3, 1, 500, 50)),
        _delta({"output_tokens": 42}), _stop(),
        _result("t1"),
        _start("m2", _u(4, 1, 550, 0)), _say("Done.", "m2", _u(4, 1, 550, 0)),
        _delta({"output_tokens": 9}), _stop(),
        _done(_u(7, 51, 1050, 50))])
    r = evs[-1].reply
    assert [(t.model_turn, t.usage) for t in r.turn_usage] == [(1, Usage(3, 42, 500, 50)), (2, Usage(4, 9, 550, 0))]


def test_stream_alone_is_enough_and_cumulative_delta_input_is_not_added_twice():
    evs = _turn(_session(), [
        _start("m1", _u(3, 1, 500, 50)), _use("t1", "m1"),                        # block without usage
        _delta(_u(3, 20, 500, 50)), _stop(), _result("t1"), _done(_u(3, 20, 500, 50))])
    assert evs[-1].reply.turn_usage == [TurnUsage(1, Usage(3, 20, 500, 50), "claude-haiku")]


def test_numbers_run_on_over_the_session_and_subagents_are_left_out():
    s = _session()
    _turn(s, [_use("t1", "m1", _u(1, 1)), _result("t1"), _say("ok", "m2", _u(2, 2)), _done(_u(3, 3))])
    evs = _turn(s, [
        _start("sub", _u(99, 99), model="x"), _ev({"type": "message_delta", "usage": {"output_tokens": 500}},
                                                 parent="t2"),
        _use("t2", "m3", _u(5, 6)),
        _say("inner", "sub1", _u(77, 77), parent="t2"), _result("t2"), _done(_u(5, 6))])
    r = evs[-1].reply
    # "sub" had a message_start but no top-level AssistantMessage: no model_turn, so not a turn entry
    assert [(t.model_turn, t.usage) for t in r.turn_usage] == [(3, Usage(5, 6))]


def test_no_usage_reported_gives_an_empty_list():
    evs = _turn(_session(), [_use("t1", "m1"), _result("t1"), _say("ok", "m2"), _done(_u(1, 1))])
    assert evs[-1].reply.turn_usage == []


def test_failed_turn_keeps_turn_usage():
    e = _turn(_session(), [_use("t1", "m1", _u(10, 3)), _result("t1"), RuntimeError("process died")])
    assert isinstance(e, AgentError)
    assert [(t.model_turn, t.usage) for t in e.reply.turn_usage] == [(1, Usage(10, 3))]


def test_capability_flag():
    from agentlib import get_engine
    assert get_engine("claude").capabilities.turn_usage
