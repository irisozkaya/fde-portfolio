import importlib
import json

import pytest
from fastapi.testclient import TestClient

import agent.tools
from agent.shop_client import ShopClient
from agent.tools import TOOL_DEFINITIONS, ToolExecutor
from shop_api.app import create_app
from tests.conftest import TODAY

EXPECTED_NAMES = ["lookup_order", "start_return", "search_products", "get_size_chart", "get_policy",
                  "handoff_to_human"]


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
