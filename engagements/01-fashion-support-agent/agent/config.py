"""Agent settings. Every field can be overridden in the constructor (the eval runner does this)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

SHOP_NAME = "Fadenwerk"


@dataclass
class Settings:
    model: str = field(default_factory=lambda: os.environ.get("AGENT_MODEL", "claude-haiku-5-5"))
    effort: str = field(default_factory=lambda: os.environ.get("AGENT_EFFORT", "low"))
    shop_url: str = field(default_factory=lambda: os.environ.get("SHOP_URL", "http://localhost:8001"))
    max_tokens: int = 4000
    max_tool_iterations: int = 8
    ledger_path: Path = Path("logs/spend.json")
