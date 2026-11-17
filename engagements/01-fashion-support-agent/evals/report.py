"""Markdown report from a run dir (feeds docs/04-eval-report.md)."""
import json
from pathlib import Path

from evals.schema import SAFETY_CATEGORIES


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f} %"


def build_report(run_dir: Path) -> str:
    run_dir = Path(run_dir)
    s = json.loads((run_dir / "summary.json").read_text())
    results = [json.loads(line) for line in (run_dir / "results.jsonl").read_text().splitlines()]
    lines = [
        f"### Run `{run_dir.name}`", "",
        "| Model | Effort | Scenarios | Pass rate | Safety pass rate | Cost (total) | Cost / conversation"
        " | Latency p50 | Latency p90 |",
        "|---|---|---|---|---|---|---|---|---|",
        f"| `{s['model']}` | {s['effort']} | {s['n']} | {_pct(s['pass_rate'])} | {_pct(s['safety_pass_rate'])} "
        f"| ${s['total_cost_usd']:.4f} | ${(s['mean_cost_per_conversation_usd'] or 0):.4f} "
        f"| {s['latency_ms_p50']} ms | {s['latency_ms_p90']} ms |", "",
        "| Category | Scenarios | Passed | Pass rate |", "|---|---|---|---|",
    ]
    for cat, c in s["by_category"].items():
        marker = " (safety)" if cat in SAFETY_CATEGORIES else ""
        lines.append(f"| {cat}{marker} | {c['n']} | {c['passed']} | {_pct(c['pass_rate'])} |")
    safety_ok = s["safety_pass_rate"] in (None, 1.0)
    lines += ["", f"**Safety bar (100 %):** {'met' if safety_ok else 'NOT met'}"
              f"{' (no safety scenarios in this run)' if s['safety_pass_rate'] is None else ''}.", ""]
    if s.get("judge_means"):
        jm = s["judge_means"]
        lines += ["**LLM judge (1-5, mean):**", "",
                  "| Language quality | Tone | Policy faithfulness | Handoff summary |", "|---|---|---|---|",
                  f"| {jm['language_quality']} | {jm['tone']} | {jm['policy_faithfulness']} "
                  f"| {jm['handoff_summary'] if jm['handoff_summary'] is not None else 'n/a'} |", ""]
    failing = [r for r in results if not r["passed"]]
    lines.append("**Failing scenarios:**" if failing else "**Failing scenarios:** none.")
    for r in failing:
        lines.append(f"- `{r['id']}` ({r['category']}): " + "; ".join(r["failures"]))
    if s.get("stopped_on_budget"):
        lines += ["", "> Run stopped early: the $5 spend cap was reached."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    import argparse
    p = argparse.ArgumentParser(description="Print the Markdown report for an eval run dir.")
    p.add_argument("run_dir", type=Path)
    print(build_report(p.parse_args(argv).run_dir))


if __name__ == "__main__":
    main()
