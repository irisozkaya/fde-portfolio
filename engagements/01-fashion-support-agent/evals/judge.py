"""LLM judge (secondary to deterministic grading): language quality, tone, policy faithfulness, handoff summary."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agent.loop import TurnRecord
from agent.pricing import UsageTotals, cost_usd
from agent.spend import SpendLedger
from evals.schema import Scenario

JUDGE_MODEL = "claude-haiku-5-5"
_RUBRIC = (Path(__file__).parent / "judge_rubric.md").read_text()
Score = Literal[1, 2, 3, 4, 5]


class JudgeScores(BaseModel):
    language_quality: Score
    tone: Score
    policy_faithfulness: Score
    handoff_summary: Score | None
    notes: str


def _transcript(turns: list[TurnRecord]) -> str:
    lines = []
    for t in turns:
        lines.append(f"CUSTOMER: {t.user_text}")
        for c in t.tool_calls:
            lines.append(f"  [tool {c.name} input={json.dumps(c.input, ensure_ascii=False)} "
                         f"result={c.content[:600]}]")
        lines.append(f"ASSISTANT: {t.reply_text}")
    return "\n".join(lines)


def judge_conversation(client, scenario: Scenario, turns: list[TurnRecord], policy_text: str,
                       ledger: SpendLedger | None = None) -> JudgeScores:
    prompt = (f"{_RUBRIC}\n\n<policy>\n{policy_text}\n</policy>\n\n<conversation scenario=\"{scenario.id}\">\n"
              f"{_transcript(turns)}\n</conversation>")
    response = client.messages.parse(model=JUDGE_MODEL, max_tokens=2000, output_config={"effort": "low"},
                                     messages=[{"role": "user", "content": prompt}], output_format=JudgeScores)
    if ledger is not None:
        usage = UsageTotals()
        usage.add(response.usage)
        ledger.add(cost_usd(JUDGE_MODEL, usage), "judge")
    return response.parsed_output
