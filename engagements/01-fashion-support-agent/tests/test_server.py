import json

import pytest
from fastapi.testclient import TestClient

from agent.config import Settings
from agent.server import create_app
from agent.shop_client import ShopClient
from shop_api.app import create_app as create_shop
from tests.conftest import TODAY
from tests.fakes import FakeClient, resp, text_block, tool_block


@pytest.fixture
def setup(seeded_db, tmp_path):
    shop = ShopClient("http://shop", http=TestClient(create_shop(seeded_db, today=TODAY)))
    fake = FakeClient(lambda n: resp([tool_block(f"t{n}", "get_policy", {})], "tool_use") if n % 2 == 1
                      else resp([text_block("Gern geschehen.")], "end_turn"))
    settings = Settings(ledger_path=tmp_path / "logs" / "spend.json")
    app = create_app(settings, client=fake, shop=shop, log_dir=tmp_path / "logs")
    return TestClient(app), fake, tmp_path / "logs"


def test_chat_new_conversation(setup):
    http, _, _ = setup
    body = http.post("/api/chat", json={"conversation_id": None, "message": "Hallo"}).json()
    assert body["conversation_id"] and body["reply"] == "Gern geschehen."
    assert body["turn"]["cost_usd"] > 0 and body["turn"]["tool_calls"][0]["name"] == "get_policy"


def test_chat_continues_history(setup):
    http, fake, _ = setup
    cid = http.post("/api/chat", json={"conversation_id": None, "message": "Hallo"}).json()["conversation_id"]
    http.post("/api/chat", json={"conversation_id": cid, "message": "Noch eine Frage"})
    assert len(fake.calls[-1]["messages"]) >= 5


def test_chat_logs_jsonl_and_spend(setup):
    http, _, logs = setup
    http.post("/api/chat", json={"conversation_id": None, "message": "Hallo"})
    lines = (logs / "conversations.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["turn"]["reply_text"] == "Gern geschehen."
    assert (logs / "spend.json").exists()


def test_reset_drops_conversation(setup):
    http, _, _ = setup
    cid = http.post("/api/chat", json={"conversation_id": None, "message": "Hallo"}).json()["conversation_id"]
    assert http.post("/api/reset", json={"conversation_id": cid}).status_code == 204
    again = http.post("/api/chat", json={"conversation_id": cid, "message": "Hallo"}).json()
    assert again["conversation_id"] != cid


def test_index_has_label(setup):
    http, _, _ = setup
    r = http.get("/")
    assert r.status_code == 200 and "Simulated engagement" in r.text
    assert "<script src=\"http" not in r.text
