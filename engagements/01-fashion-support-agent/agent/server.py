"""Chat API + static UI. Conversations live in memory; every turn is logged to logs/conversations.jsonl."""
import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from agent.config import Settings
from agent.loop import Conversation, run_turn
from agent.shop_client import ShopClient
from agent.spend import SpendLedger
from agent.tools import ToolExecutor

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResetRequest(BaseModel):
    conversation_id: str


def create_app(settings: Settings, *, client=None, shop: ShopClient | None = None,
               log_dir: Path = Path("logs")) -> FastAPI:
    app = FastAPI(title="Fadenwerk support agent (demo)")
    executor = ToolExecutor(shop or ShopClient(settings.shop_url))
    ledger = SpendLedger(settings.ledger_path)
    conversations: dict[str, Conversation] = {}
    log_dir = Path(log_dir)

    @app.post("/api/chat")
    def chat(req: ChatRequest):
        conv = conversations.get(req.conversation_id or "")
        if conv is None:
            conv = Conversation()
            conversations[conv.id] = conv
        turn = run_turn(client, conv, req.message, executor, settings, ledger=ledger, ledger_source="chat")
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "conversations.jsonl").open("a") as f:
            f.write(json.dumps({"conversation_id": conv.id, "model": settings.model, "turn": turn.to_dict()},
                               ensure_ascii=False) + "\n")
        return {"conversation_id": conv.id, "reply": turn.reply_text, "turn": turn.to_dict()}

    @app.post("/api/reset", status_code=204)
    def reset(req: ResetRequest):
        conversations.pop(req.conversation_id, None)
        return Response(status_code=204)

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app
