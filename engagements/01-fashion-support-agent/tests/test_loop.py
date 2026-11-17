import pytest

from agent.config import SHOP_NAME, Settings
from agent.loop import Conversation, run_turn
from agent.pricing import UsageTotals, cost_usd
from agent.prompts import FALLBACK_REPLY_DE, build_system_prompt
from agent.spend import SpendLedger
from agent.tools import TOOL_DEFINITIONS, ToolOutcome
from tests.fakes import FakeClient, resp, text_block, thinking_block, tool_block


class StubExecutor:
    def __init__(self, outcome=ToolOutcome('{"data": {"ok": true}}', False)):
        self.outcome = outcome
        self.calls = []

    def execute(self, name, tool_input):
        self.calls.append((name, tool_input))
        return self.outcome


@pytest.fixture
def settings(tmp_path):
    return Settings(model="claude-haiku-5-5", effort="low", ledger_path=tmp_path / "spend.json")


def roles(conv):
    return [m["role"] for m in conv.messages]


def test_plain_reply(settings):
    client = FakeClient([resp([text_block("Guten Tag!")], "end_turn")])
    conv = Conversation()
    turn = run_turn(client, conv, "Hallo", StubExecutor(), settings)
    assert turn.reply_text == "Guten Tag!" and turn.api_requests == 1 and turn.stop_reason == "end_turn"
    assert roles(conv) == ["user", "assistant"]


def test_request_params(settings):
    client = FakeClient([resp([text_block("Hi")], "end_turn")])
    run_turn(client, Conversation(), "Hallo", StubExecutor(), settings)
    kw = client.calls[0]
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"] == {"effort": "low"}
    assert kw["cache_control"] == {"type": "ephemeral"}
    assert kw["tools"] is TOOL_DEFINITIONS
    assert kw["system"] == build_system_prompt()
    assert "temperature" not in kw and "tool_choice" not in kw


def test_tool_roundtrip(settings):
    client = FakeClient([
        resp([tool_block("tu_1", "lookup_order", {"order_no": "B-10002", "verification": "10115"})], "tool_use"),
        resp([text_block("Ihre Bestellung ist unterwegs.")], "end_turn"),
    ])
    ex = StubExecutor()
    turn = run_turn(client, Conversation(), "Wo ist B-10002? PLZ 10115", ex, settings)
    last = client.calls[1]["messages"][-1]
    assert last["role"] == "user"
    assert [b["tool_use_id"] for b in last["content"] if b["type"] == "tool_result"] == ["tu_1"]
    assert last["content"][0]["type"] == "tool_result"
    assert turn.tool_calls[0].name == "lookup_order" and ex.calls[0][0] == "lookup_order"
    assert turn.reply_text == "Ihre Bestellung ist unterwegs."


def test_parallel_tool_results_in_one_message(settings):
    client = FakeClient([
        resp([tool_block("a", "get_policy", {}), tool_block("b", "get_size_chart", {"category": "Kleider"})],
             "tool_use"),
        resp([text_block("ok")], "end_turn"),
    ])
    run_turn(client, Conversation(), "x", StubExecutor(), settings)
    last = client.calls[1]["messages"][-1]
    assert [b["tool_use_id"] for b in last["content"] if b["type"] == "tool_result"] == ["a", "b"]


def test_tool_error_flag_passed(settings):
    client = FakeClient([resp([tool_block("a", "lookup_order", {})], "tool_use"), resp([text_block("ok")], "end_turn")])
    turn = run_turn(client, Conversation(), "x", StubExecutor(ToolOutcome('{"error": "invalid_input"}', True)), settings)
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True
    assert turn.tool_calls[0].is_error is True


def test_assistant_content_passed_unchanged(settings):
    blocks = [thinking_block(), text_block("Hallo")]
    response = resp(blocks, "end_turn")
    conv = Conversation()
    run_turn(FakeClient([response]), conv, "x", StubExecutor(), settings)
    assert conv.messages[-1]["content"] is response.content


def test_refusal_fallback(settings):
    conv = Conversation()
    turn = run_turn(FakeClient([resp([], "refusal")]), conv, "x", StubExecutor(), settings)
    assert turn.reply_text == FALLBACK_REPLY_DE and turn.stop_reason == "refusal"
    assert conv.messages[-1]["role"] == "assistant"


def test_max_tokens_returns_partial_text(settings):
    turn = run_turn(FakeClient([resp([text_block("Teilantwort")], "max_tokens")]), Conversation(), "x",
                    StubExecutor(), settings)
    assert turn.reply_text == "Teilantwort" and turn.stop_reason == "max_tokens"


def test_iteration_limit(settings):
    client = FakeClient(lambda n: resp([tool_block(f"t{n}", "get_policy", {})], "tool_use"))
    conv = Conversation()
    turn = run_turn(client, conv, "x", StubExecutor(), settings)
    assert turn.api_requests == 8 and turn.stop_reason == "iteration_limit"
    assert turn.reply_text == FALLBACK_REPLY_DE and conv.messages[-1]["role"] == "assistant"


def test_next_turn_after_fallback(settings):
    client = FakeClient([resp([], "refusal"), resp([text_block("Gern!")], "end_turn")])
    conv = Conversation()
    run_turn(client, conv, "x", StubExecutor(), settings)
    turn = run_turn(client, conv, "Neue Frage", StubExecutor(), settings)
    assert turn.reply_text == "Gern!"
    assert roles(conv) == ["user", "assistant", "user", "assistant"]


def test_usage_and_cost_accumulate(settings):
    client = FakeClient([resp([tool_block("a", "get_policy", {})], "tool_use", in_tok=1000, out_tok=50),
                         resp([text_block("ok")], "end_turn", in_tok=200, out_tok=30, cache_read=900)])
    turn = run_turn(client, Conversation(), "x", StubExecutor(), settings)
    expected = UsageTotals(input_tokens=1200, output_tokens=80, cache_read_input_tokens=900)
    assert turn.usage == expected
    assert turn.cost_usd == pytest.approx(cost_usd("claude-haiku-5-5", expected))


def test_ledger_updated(settings):
    ledger = SpendLedger(settings.ledger_path)
    turn = run_turn(FakeClient([resp([text_block("ok")], "end_turn")]), Conversation(), "x", StubExecutor(),
                    settings, ledger=ledger, ledger_source="eval")
    assert ledger.total() == pytest.approx(turn.cost_usd) and turn.cost_usd > 0


def test_turn_record_to_dict(settings):
    client = FakeClient([resp([tool_block("a", "get_policy", {})], "tool_use"), resp([text_block("ok")], "end_turn")])
    d = run_turn(client, Conversation(), "x", StubExecutor(), settings).to_dict()
    assert d["tool_calls"][0]["name"] == "get_policy" and d["usage"]["input_tokens"] == 200
    assert {"user_text", "reply_text", "stop_reason", "cost_usd", "latency_ms", "api_requests"} <= set(d)


def test_system_prompt_deterministic_and_branded():
    assert build_system_prompt() == build_system_prompt()
    assert SHOP_NAME in build_system_prompt()


def test_max_tokens_with_dangling_tool_use_keeps_history_valid(settings):
    """A tool_use block without its tool_result would make the next request invalid."""
    client = FakeClient([resp([tool_block("a", "get_policy", {})], "max_tokens"),
                         resp([text_block("Gern!")], "end_turn")])
    conv = Conversation()
    turn = run_turn(client, conv, "x", StubExecutor(), settings)
    assert turn.reply_text == FALLBACK_REPLY_DE and turn.stop_reason == "max_tokens"
    assert all(getattr(b, "type", None) != "tool_use" for b in conv.messages[-1]["content"]
               if not isinstance(b, dict))
    run_turn(client, conv, "Neue Frage", StubExecutor(), settings)
    assert roles(conv) == ["user", "assistant", "user", "assistant"]


def test_tool_results_message_ends_with_language_reminder(settings):
    from agent.prompts import LANGUAGE_REMINDER
    client = FakeClient([resp([tool_block("a", "get_policy", {})], "tool_use"), resp([text_block("ok")], "end_turn")])
    run_turn(client, Conversation(), "How long can I return things?", StubExecutor(), settings)
    content = client.calls[1]["messages"][-1]["content"]
    assert [b["type"] for b in content] == ["tool_result", "text"]
    assert content[-1]["text"] == LANGUAGE_REMINDER
