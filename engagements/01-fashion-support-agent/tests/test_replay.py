import json

import pytest

from scripts.build_replay import build_replay


def _result(sid, tool="lookup_order"):
    turn = {"user_text": "Wo ist B-10002?", "reply_text": "Unterwegs mit DHL.", "stop_reason": "end_turn",
            "tool_calls": [{"name": tool, "input": {"order_no": "B-10002"}, "content": "{\"data\": {}}",
                            "is_error": False}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 900,
                      "cache_creation_input_tokens": 0},
            "cost_usd": 0.0001, "latency_ms": 900, "api_requests": 2}
    return {"id": sid, "category": "wismo", "lang": "de", "passed": True, "failures": [], "turns": [turn],
            "state": {"returns": [], "tickets": []}, "cost_usd": 0.0001, "latency_ms": 900}


@pytest.fixture
def page(tmp_path):
    results = tmp_path / "results.jsonl"
    rows = [_result("keep-a", "lookup_order"), _result("drop-b", "secret_tool"), _result("keep-c", "get_policy")]
    results.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "demo" / "index.html"
    build_replay(results, ["keep-a", "keep-c"], out)
    return out.read_text()


def test_replay_contains_selected_ids_only(page):
    assert "keep-a" in page and "keep-c" in page and "drop-b" not in page


def test_replay_has_label_and_tool_names(page):
    assert "Simulated engagement" in page and "lookup_order" in page and "get_policy" in page


def test_replay_is_self_contained(page):
    assert "<script src=" not in page and '<link href="http' not in page and "@import" not in page


def test_replay_has_no_secrets(page):
    assert "sk-ant" not in page and "ANTHROPIC_API_KEY" not in page


def test_replay_unknown_id_raises(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(_result("a")) + "\n")
    with pytest.raises(KeyError):
        build_replay(results, ["missing"], tmp_path / "x.html")
