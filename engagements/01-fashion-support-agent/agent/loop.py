"""The agent loop, written by hand on the Anthropic Messages API.

History is append-only: assistant content goes back exactly as the API returned it (thinking blocks included),
every tool_use gets a tool_result in ONE following user message, and abnormal endings (refusal, cut-off tool
call, iteration limit, API error) append a fixed fallback reply so the conversation stays valid for the next turn.
"""
import time
import uuid

import anthropic
from dataclasses import asdict, dataclass, field

from agent.config import Settings
from agent.pricing import UsageTotals, cost_usd
from agent.prompts import FALLBACK_REPLY_DE, LANGUAGE_REMINDER, build_system_prompt
from agent.spend import SpendLedger
from agent.tools import TOOL_DEFINITIONS, ToolExecutor


@dataclass
class ToolCallRecord:
    name: str
    input: dict
    content: str
    is_error: bool


@dataclass
class TurnRecord:
    user_text: str
    reply_text: str = ""
    stop_reason: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: UsageTotals = field(default_factory=UsageTotals)
    cost_usd: float = 0.0
    latency_ms: int = 0
    api_requests: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    messages: list = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)


def _fallback(conv: Conversation, turn: TurnRecord, stop_reason: str) -> None:
    conv.messages.append({"role": "assistant", "content": [{"type": "text", "text": FALLBACK_REPLY_DE}]})
    turn.reply_text = FALLBACK_REPLY_DE
    turn.stop_reason = stop_reason


def _text(content) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()


def run_turn(client, conv: Conversation, user_text: str, executor: ToolExecutor, settings: Settings,
             ledger: SpendLedger | None = None, ledger_source: str = "chat") -> TurnRecord:
    turn = TurnRecord(user_text=user_text)
    started = time.perf_counter()
    conv.messages.append({"role": "user", "content": user_text})

    for _ in range(settings.max_tool_iterations):
        try:
            response = client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=build_system_prompt(),
                tools=TOOL_DEFINITIONS,
                messages=conv.messages,
                thinking={"type": "adaptive"},
                output_config={"effort": settings.effort},
                cache_control={"type": "ephemeral"},
            )
        except anthropic.APIError:
            # Still failing after the SDK's own retries. The last message is always a user message here, so the
            # fallback keeps roles alternating; requests that did succeed are billed below.
            _fallback(conv, turn, "api_error")
            break
        turn.api_requests += 1
        turn.usage.add(response.usage)
        stop = response.stop_reason
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if stop == "refusal":
            _fallback(conv, turn, "refusal")
            break
        if stop == "max_tokens" and tool_uses:
            # A tool_use cut off without its tool_result cannot stay in history.
            _fallback(conv, turn, "max_tokens")
            break

        conv.messages.append({"role": "assistant", "content": response.content})

        if stop == "tool_use":
            results = []
            for block in tool_uses:
                outcome = executor.execute(block.name, block.input)
                turn.tool_calls.append(ToolCallRecord(block.name, block.input, outcome.content, outcome.is_error))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": outcome.content,
                                "is_error": outcome.is_error})
            results.append({"type": "text", "text": LANGUAGE_REMINDER})
            conv.messages.append({"role": "user", "content": results})
            continue
        if stop == "pause_turn":
            continue

        turn.reply_text = _text(response.content) or FALLBACK_REPLY_DE
        turn.stop_reason = stop
        break
    else:
        _fallback(conv, turn, "iteration_limit")

    turn.cost_usd = cost_usd(settings.model, turn.usage)
    turn.latency_ms = int((time.perf_counter() - started) * 1000)
    if ledger is not None:
        ledger.add(turn.cost_usd, ledger_source)
    conv.turns.append(turn)
    return turn
