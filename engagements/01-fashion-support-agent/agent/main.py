"""Entry point: `uvicorn agent.main:app --port 8000` (needs ANTHROPIC_API_KEY in .env and the shop on SHOP_URL)."""
import anthropic
from dotenv import load_dotenv

from agent.config import Settings
from agent.server import create_app

load_dotenv()
app = create_app(Settings(), client=anthropic.Anthropic())
