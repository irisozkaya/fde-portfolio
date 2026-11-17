"""Token prices and cost calculation.

Source: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-17).
Haiku 5.5 prices are the tier for prompts up to 100K tokens; this agent's prompts stay far below that.
Cache writes use the 5-minute TTL price (the default for cache_control ephemeral).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input: float        # USD per million tokens
    output: float
    cache_read: float
    cache_write: float


PRICES: dict[str, ModelPrice] = {
    "claude-haiku-5-5": ModelPrice(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),
    "claude-sonnet-5-5": ModelPrice(input=2.00, output=10.00, cache_read=0.10, cache_write=2.50),
}


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, usage) -> None:
        """Accumulate an SDK `response.usage` object (cache fields may be None)."""
        self.input_tokens += usage.input_tokens or 0
        self.output_tokens += usage.output_tokens or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0


def cost_usd(model: str, usage: UsageTotals) -> float:
    p = PRICES[model]
    return (usage.input_tokens * p.input + usage.output_tokens * p.output
            + usage.cache_read_input_tokens * p.cache_read
            + usage.cache_creation_input_tokens * p.cache_write) / 1_000_000
