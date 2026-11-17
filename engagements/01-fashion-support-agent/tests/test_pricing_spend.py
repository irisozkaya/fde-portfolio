from types import SimpleNamespace

import pytest

from agent.pricing import UsageTotals, cost_usd
from agent.spend import BUDGET_CAP_USD, SpendLedger


def test_cost_haiku_io():
    u = UsageTotals(input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost_usd("claude-haiku-5-5", u) == pytest.approx(0.60)


def test_cost_cache_tokens():
    assert cost_usd("claude-haiku-5-5", UsageTotals(cache_read_input_tokens=1_000_000)) == pytest.approx(0.01)
    assert cost_usd("claude-haiku-5-5", UsageTotals(cache_creation_input_tokens=1_000_000)) == pytest.approx(0.125)


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        cost_usd("claude-unknown", UsageTotals())


def test_usage_add_tolerates_none():
    u = UsageTotals()
    u.add(SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=None,
                          cache_creation_input_tokens=None))
    u.add(SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=7,
                          cache_creation_input_tokens=3))
    assert (u.input_tokens, u.output_tokens, u.cache_read_input_tokens, u.cache_creation_input_tokens) == (11, 6, 7, 3)


def test_ledger_accumulates_and_persists(tmp_path):
    path = tmp_path / "logs" / "spend.json"
    led = SpendLedger(path)
    led.add(0.50, "eval")
    led.add(0.25, "chat")
    assert SpendLedger(path).total() == pytest.approx(0.75)


def test_ledger_over_cap(tmp_path):
    led = SpendLedger(tmp_path / "spend.json")
    assert BUDGET_CAP_USD == 5.00
    assert not led.is_over_cap()
    led.add(5.00, "eval")
    assert led.is_over_cap()
