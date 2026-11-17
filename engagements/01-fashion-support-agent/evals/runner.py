"""Run scenarios against the real agent loop and an in-process shop; write results + summary.

CLI: python -m evals.runner --subset smoke|comparison|all|<id,id> [--model ...] [--effort ...]
"""
import argparse
import json
import math
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from agent.config import Settings
from agent.loop import Conversation, run_turn
from agent.shop_client import ShopClient
from agent.spend import BudgetExceeded, SpendLedger
from agent.tools import ToolExecutor
from evals.grading import grade
from evals.judge import judge_conversation
from evals.schema import SAFETY_CATEGORIES, Scenario, load_scenarios
from shop_api.app import create_app as create_shop
from shop_api.db import connect, init_schema
from shop_api.policy import POLICY_TEXT_DE
from shop_api.seed import seed

EVAL_TODAY = datetime(2026, 11, 17).date()


def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def _run_one(scenario: Scenario, client, settings: Settings, ledger: SpendLedger, judge: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "shop.db")
        conn = connect(db)
        init_schema(conn)
        seed(conn, today=EVAL_TODAY)
        conn.commit()
        conn.close()
        shop_http = TestClient(create_shop(db, today=EVAL_TODAY, expose_state=True))
        executor = ToolExecutor(ShopClient("http://shop", http=shop_http))
        conv = Conversation()
        turns = [run_turn(client, conv, text, executor, settings, ledger=ledger, ledger_source="eval")
                 for text in scenario.turns]
        state = {"returns": shop_http.get("/_state/returns").json(),
                 "tickets": shop_http.get("/_state/tickets").json()}
    result = grade(scenario, turns, state)
    judged = (judge_conversation(client, scenario, turns, POLICY_TEXT_DE, ledger=ledger).model_dump()
              if judge else None)
    return {"judge": judged, "id": scenario.id, "category": scenario.category, "lang": scenario.lang, "passed": result.passed,
            "failures": result.failures, "turns": [t.to_dict() for t in turns], "state": state,
            "cost_usd": sum(t.cost_usd for t in turns), "latency_ms": sum(t.latency_ms for t in turns)}


def _judge_means(results: list[dict]) -> dict | None:
    judged = [r["judge"] for r in results if r.get("judge")]
    if not judged:
        return None
    means = {}
    for key in ("language_quality", "tone", "policy_faithfulness", "handoff_summary"):
        vals = [j[key] for j in judged if j[key] is not None]
        means[key] = round(sum(vals) / len(vals), 2) if vals else None
    return means


def _summary(results: list[dict], model: str, effort: str, stopped: bool, ledger: SpendLedger) -> dict:
    by_cat: dict[str, dict] = {}
    for r in results:
        c = by_cat.setdefault(r["category"], {"n": 0, "passed": 0})
        c["n"] += 1
        c["passed"] += r["passed"]
    for c in by_cat.values():
        c["pass_rate"] = c["passed"] / c["n"]
    safety = [r for r in results if r["category"] in SAFETY_CATEGORIES]
    n = len(results)
    total_cost = sum(r["cost_usd"] for r in results)
    latencies = [r["latency_ms"] for r in results]
    return {"model": model, "effort": effort, "n": n,
            "pass_rate": sum(r["passed"] for r in results) / n if n else None,
            "by_category": dict(sorted(by_cat.items())),
            "safety_pass_rate": sum(r["passed"] for r in safety) / len(safety) if safety else None,
            "total_cost_usd": total_cost, "mean_cost_per_conversation_usd": total_cost / n if n else None,
            "latency_ms_p50": _percentile(latencies, 0.5), "latency_ms_p90": _percentile(latencies, 0.9),
            "stopped_on_budget": stopped, "spend_ledger_total_usd": ledger.total(),
            "judge_means": _judge_means(results)}


def run(scenarios: list[Scenario], *, model: str, effort: str, out_dir: Path, ledger: SpendLedger, client=None,
        allow_over_budget: bool = False, judge: bool = False) -> Path:
    if ledger.is_over_cap() and not allow_over_budget:
        raise BudgetExceeded(f"spend ledger at ${ledger.total():.2f}; cap reached")
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    settings = Settings(model=model, effort=effort, ledger_path=ledger.path)
    run_dir = Path(out_dir) / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}_{model}_{effort}"
    run_dir.mkdir(parents=True)
    results, stopped = [], False
    with (run_dir / "results.jsonl").open("w") as f:
        for scenario in scenarios:
            if ledger.is_over_cap() and not allow_over_budget:
                stopped = True
                break
            result = _run_one(scenario, client, settings, ledger, judge=judge)
            results.append(result)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
    summary = _summary(results, model, effort, stopped, ledger)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return run_dir


def _select(scenarios: list[Scenario], subset: str) -> list[Scenario]:
    if subset == "all":
        return scenarios
    if subset == "smoke":
        return [s for s in scenarios if s.smoke]
    if subset == "comparison":
        return [s for s in scenarios if s.comparison]
    wanted = set(subset.split(","))
    return [s for s in scenarios if s.id in wanted]


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv
    load_dotenv()
    defaults = Settings()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subset", default="smoke")
    p.add_argument("--model", default=defaults.model)
    p.add_argument("--effort", default=defaults.effort)
    p.add_argument("--scenarios-dir", type=Path, default=Path("evals/scenarios"))
    p.add_argument("--out", type=Path, default=Path("evals/results"))
    p.add_argument("--allow-over-budget", action="store_true")
    p.add_argument("--judge", action="store_true", help="also score each conversation with the LLM judge")
    args = p.parse_args(argv)
    ledger = SpendLedger(defaults.ledger_path)
    chosen = _select(load_scenarios(args.scenarios_dir), args.subset)
    print(f"{len(chosen)} scenarios · model {args.model} · effort {args.effort} · ledger ${ledger.total():.4f}")
    run_dir = run(chosen, model=args.model, effort=args.effort, out_dir=args.out, ledger=ledger,
                  allow_over_budget=args.allow_over_budget, judge=args.judge)
    s = json.loads((run_dir / "summary.json").read_text())
    print(json.dumps({k: s[k] for k in ("pass_rate", "safety_pass_rate", "total_cost_usd", "latency_ms_p50",
                                        "latency_ms_p90", "stopped_on_budget", "spend_ledger_total_usd")}))
    print(f"run dir: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
