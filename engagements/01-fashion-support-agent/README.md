# Engagement 01 · Fadenwerk: German Customer-Support Agent

> **Simulated engagement: fictional company, synthetic data.**

**The client:** Fadenwerk, a German online fashion retailer whose support team drowns in repetitive questions ([client brief](docs/01-client-brief.md)).

**What I built:** a German- and English-speaking assistant that answers order, return, size and product questions through the shop's own API, and hands everything else to the human team with a usable summary.

**▶ [Replay demo](https://irisozkaya.github.io/fde-portfolio/engagements/01-fashion-support-agent/demo/):** real recorded conversations, with every tool call, token and cent visible. Viewing it calls no API. (Source: [`demo/index.html`](demo/index.html).)

## Results

| | |
|---|---|
| Eval scenarios passed | **35/35**, in 3 independent runs (105/105) |
| Safety scenarios (data leaks, out-of-policy returns, prompt injection) | **100 %** |
| Cost per conversation | **≈ $0.00085** (`claude-haiku-5-5`), ≈ $8.50 per 10,000 |
| Latency per customer turn | p50 3.4 s · p90 4.7 s |
| Model choice | Haiku: `claude-sonnet-5-5` also passed 13/13 on the comparison subset, at ≈ 17–20× the cost and with slower replies |
| Total API spend for the whole engagement | ≈ $0.61 |

The full numbers, what the evals and an independent code review caught along the way, and one correction to earlier cost figures are in the [eval report](docs/04-eval-report.md).

## How it works

- **A hand-written agent loop** on the Claude Messages API, with no framework. It handles tool calls, refusals, cut-off answers, API errors and runaway loops, and every one of those paths has a unit test. See `agent/loop.py`.
- **Guardrails live where they cannot be talked around.** Customer verification and the return policy are enforced by the shop API; the prompt only explains. See the [solution design](docs/03-solution-design.md).
- **Adapters instead of backend changes.** The client's product search only matches exact strings, so the fix lives in our tool layer. Size arithmetic moved from the model into code after the judge caught the model getting comparisons backwards.
- **Evals decide.** 35 deterministic scenarios (tools called or not, final shop state, forbidden text) gate every change. An LLM judge scores tone, language and handoff quality on top.

## Engagement documents

1. [Client brief](docs/01-client-brief.md): the ask, in the client's words
2. [Discovery](docs/02-discovery.md): systems map, risks, success metrics
3. [Solution design](docs/03-solution-design.md): architecture, tools, guardrails, trade-offs
4. [Eval report](docs/04-eval-report.md): results, findings, judge calibration
5. [Handover](docs/05-handover.md): runbook, measured costs, limits, the deployment plan (not executed)

## Run it yourself

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
.venv/bin/uvicorn shop_api.main:app --port 8001 &
.venv/bin/uvicorn agent.main:app --port 8000        # → http://localhost:8000
.venv/bin/pytest                                    # unit tests, no API calls
.venv/bin/python -m evals.runner --subset all       # full eval, ≈ $0.03
```

## Layout

```
shop_api/   mock client system: FastAPI + SQLite, deterministic synthetic data, policy enforcement
agent/      loop, tools and adapters, prompt, pricing, spend ledger, chat server
web/        chat UI with an "under the hood" panel
evals/      scenarios (YAML), deterministic grader, LLM judge, runner, report
scripts/    replay page builder
demo/       generated replay page
docs/       the five engagement documents
```
