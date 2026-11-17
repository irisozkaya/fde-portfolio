import json
from types import SimpleNamespace

from agent.loop import TurnRecord
from agent.spend import SpendLedger
from evals.judge import JudgeScores, judge_conversation
from evals.runner import run
from evals.schema import Scenario
from tests.fakes import FakeClient, resp, text_block

SCORES = JudgeScores(language_quality=5, tone=4, policy_faithfulness=5, handoff_summary=None, notes="ok")


def parsed(scores=SCORES):
    return SimpleNamespace(parsed_output=scores, usage=SimpleNamespace(
        input_tokens=500, output_tokens=80, cache_read_input_tokens=0, cache_creation_input_tokens=0))


def scenario():
    return Scenario.model_validate({"id": "j1", "category": "wismo", "turns": ["Wo ist B-10002? PLZ 10115"]})


def test_judge_returns_scores_and_records_cost(tmp_path):
    fake = FakeClient([], parse_responses=[parsed()])
    ledger = SpendLedger(tmp_path / "spend.json")
    scores = judge_conversation(fake, scenario(), [TurnRecord(user_text="u", reply_text="r")], "Policy",
                                ledger=ledger)
    assert scores == SCORES
    kw = fake.parse_calls[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["output_format"] is JudgeScores
    assert "Policy" in kw["messages"][0]["content"] and "temperature" not in kw
    assert ledger.total() > 0


def test_runner_judge_flag_adds_scores_to_results(tmp_path):
    fake = FakeClient([resp([text_block("Unterwegs.")], "end_turn")], parse_responses=[parsed()])
    run_dir = run([scenario()], model="claude-haiku-5-5", effort="low", out_dir=tmp_path,
                  ledger=SpendLedger(tmp_path / "spend.json"), client=fake, judge=True)
    row = json.loads((run_dir / "results.jsonl").read_text().splitlines()[0])
    assert row["judge"]["tone"] == 4
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["judge_means"]["policy_faithfulness"] == 5.0
