import importlib
import json

import pytest
from fastapi.testclient import TestClient

import agent.tools
from agent.shop_client import ShopClient
from agent.tools import TOOL_DEFINITIONS, ToolExecutor
from shop_api.app import create_app
from tests.conftest import TODAY

EXPECTED_NAMES = ["lookup_order", "start_return", "search_products", "get_size_chart", "recommend_size",
                  "get_policy", "handoff_to_human"]


@pytest.fixture
def shop_http(seeded_db):
    return TestClient(create_app(seeded_db, today=TODAY, expose_state=True))


@pytest.fixture
def executor(shop_http):
    return ToolExecutor(ShopClient("http://shop", http=shop_http))


def test_tool_definitions_shape():
    assert [t["name"] for t in TOOL_DEFINITIONS] == EXPECTED_NAMES
    for t in TOOL_DEFINITIONS:
        schema = t["input_schema"]
        assert t["strict"] is True
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert t["description"]


def test_tool_definitions_deterministic():
    before = json.dumps(TOOL_DEFINITIONS, sort_keys=False)
    after = json.dumps(importlib.reload(agent.tools).TOOL_DEFINITIONS, sort_keys=False)
    assert before == after


def test_execute_lookup_ok(executor):
    out = executor.execute("lookup_order", {"order_no": "B-10001", "verification": "10115"})
    assert out.is_error is False
    assert json.loads(out.content)["data"]["order_no"] == "B-10001"


def test_execute_lookup_unverified(executor):
    out = executor.execute("lookup_order", {"order_no": "B-10001", "verification": "99999"})
    assert out.is_error is True and "not_found_or_unverified" in out.content


def test_execute_return_policy_violation(executor):
    out = executor.execute("start_return", {"order_no": "B-10001", "verification": "10115",
                                            "line_nos": [2], "reason": "gefällt nicht"})
    assert out.is_error is True and "non_returnable_category" in out.content


def test_execute_search_accepts_null_optionals(executor):
    out = executor.execute("search_products", {"query": "Leinen", "category": None, "size": None})
    assert out.is_error is False and json.loads(out.content)["data"]


def test_execute_invalid_input(executor):
    out = executor.execute("lookup_order", {})
    assert out.is_error is True and "invalid_input" in out.content


def test_execute_unknown_tool(executor):
    out = executor.execute("delete_everything", {})
    assert out.is_error is True and "unknown_tool" in out.content


def test_execute_handoff_creates_ticket(executor, shop_http):
    out = executor.execute("handoff_to_human", {"reason": "complaint", "summary": "Kundin ist unzufrieden.",
                                                "order_no": "B-10002", "customer_email": None})
    assert out.is_error is False and "ticket_id" in json.loads(out.content)["data"]
    assert len(shop_http.get("/_state/tickets").json()) == 1


def test_search_falls_back_to_single_words(executor):
    """The shop's search is exact-substring; the agent often sends 'Sommerkleid Leinen'. Adapter must cope."""
    out = executor.execute("search_products", {"query": "Sommerkleid Leinen", "category": "Kleider", "size": None})
    skus = [p["sku"] for p in json.loads(out.content)["data"]]
    assert out.is_error is False and skus and skus[0] == "P-1001"


def test_search_word_fallback_ignores_stopwords(executor):
    out = executor.execute("search_products", {"query": "Leinen und Kleid", "category": None, "size": None})
    skus = [p["sku"] for p in json.loads(out.content)["data"]]
    assert skus[0] == "P-1001" and len(skus) <= 5


from agent.tools import recommend_size  # noqa: E402
from shop_api.fixtures import SIZE_CHARTS  # noqa: E402

DRESS = {"category": "Kleider", "rows": SIZE_CHARTS["Kleider"]}


def test_recommend_size_between_sizes():
    out = recommend_size(DRESS, {"bust_cm": 89, "waist_cm": 73, "hip_cm": 97})
    assert out["recommended_size"] == "40" and out["closest_size"] == "38"
    row38 = next(r for r in out["rows"] if r["size"] == "38")
    assert row38["difference_cm"] == {"bust_cm": -1, "waist_cm": -1, "hip_cm": -1}


def test_recommend_size_exact_fit():
    out = recommend_size(DRESS, {"bust_cm": 88, "waist_cm": 72, "hip_cm": 96})
    assert out["recommended_size"] == "38" and out["closest_size"] == "38"


def test_recommend_size_larger_than_chart():
    out = recommend_size(DRESS, {"bust_cm": 120, "waist_cm": 100, "hip_cm": 125})
    assert out["recommended_size"] is None and out["closest_size"] == "44"


def test_recommend_size_ignores_measurements_not_in_chart():
    shoes = {"category": "Schuhe", "rows": SIZE_CHARTS["Schuhe"]}
    out = recommend_size(shoes, {"foot_length_cm": 25.4, "waist_cm": 80})
    assert out["recommended_size"] == "40" and out["used_measurements"] == ["foot_length_cm"]


def test_execute_recommend_size(executor):
    args = {"category": "Kleider", "bust_cm": 89, "chest_cm": None, "waist_cm": 73, "hip_cm": 97,
            "underbust_cm": None, "foot_length_cm": None}
    out = executor.execute("recommend_size", args)
    assert out.is_error is False and json.loads(out.content)["data"]["recommended_size"] == "40"


def test_execute_recommend_size_without_usable_measurements(executor):
    args = {"category": "Schuhe", "bust_cm": 89, "chest_cm": None, "waist_cm": None, "hip_cm": None,
            "underbust_cm": None, "foot_length_cm": None}
    out = executor.execute("recommend_size", args)
    assert out.is_error is True and "no_matching_measurements" in out.content
