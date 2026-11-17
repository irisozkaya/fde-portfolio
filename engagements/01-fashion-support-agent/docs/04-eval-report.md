# 04 · Eval Report

> **Simulated engagement: fictional company, synthetic data.**

## Headline

| | Result | Bar |
|---|---|---|
| Deterministic pass rate | **100 %** (35/35), stable over 3 repeat runs (105/105) | ≥ 85 % |
| Safety scenarios | **100 %** (9/9 per run, 27/27 over repeats) | 100 % |
| Cost per conversation | **≈ $0.0004–0.0007** (`claude-haiku-5-5`, effort `low`) | measured |
| Latency per customer turn | **p50 ≈ 3.1 s, p90 ≈ 4.6 s** | measured |
| LLM judge, means on a 1–5 scale | language 4.91 · tone 4.49 · policy faithfulness 4.83 · handoff summary 3.83 | secondary |

**Total API spend for the whole engagement** (development, every eval run, judge): **≈ $0.32**, tracked in a spend ledger capped at $5.

## How the evaluation works

- **35 scripted conversations** in German and English (`evals/scenarios/*.yaml`), each 1–3 customer turns, run against the real agent loop and a fresh copy of the mock shop.
  - **Normal categories:** where is my order (4), returns (6), sizing (3), product questions (4), escalation to a human (5), English customers (4).
  - **Safety categories:** verification (2), other customers' data (2), out-of-policy returns (2), prompt injection (3).
- **Primary grading is deterministic.** It checks which tools were called or *not* called, the final shop state (returns and tickets actually created), and forbidden or required text in the replies. A safety failure means data leaked or an action happened that the client forbade, so these checks never depend on a model's opinion.
- **Secondary grading is an LLM judge** (`claude-haiku-5-5`, rubric in `evals/judge_rubric.md`). It scores what string checks cannot see: language quality, tone, faithfulness to the policy and tool results, and the quality of handoff summaries.

## Published run

Run `20261117-181900` (results in `evals/results/published/`):

| Model | Effort | Scenarios | Pass rate | Safety pass rate | Cost (total) | Cost / conversation | Latency p50 | Latency p90 |
|---|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5` | low | 35 | 100 % | 100 % | $0.0250 | $0.0007 | 4370 ms | 7401 ms |

| Category | Scenarios | Passed |
|---|---|---|
| wismo | 4 | 4 |
| returns | 6 | 6 |
| sizing | 3 | 3 |
| product | 4 | 4 |
| escalation | 5 | 5 |
| english | 4 | 4 |
| safety_verification | 2 | 2 |
| safety_other_customer | 2 | 2 |
| safety_policy | 2 | 2 |
| safety_injection | 3 | 3 |

Latency here is **per conversation** (all turns). A single customer turn takes p50 3.1 s and p90 4.6 s.

## Stability

LLM output varies between runs, so the frozen prompt ran the full suite three more times:

| Run | Pass rate | Safety | Cost / conversation | Latency p50 / p90 (per conversation) |
|---|---|---|---|---|
| 1 | 100 % | 100 % | $0.00042 | 4.6 s / 7.7 s |
| 2 | 100 % | 100 % | $0.00041 | 4.1 s / 7.3 s |
| 3 | 100 % | 100 % | $0.00042 | 4.4 s / 7.2 s |

- **96 %** of input tokens were prompt-cache reads.
- On average there were 1.9 model requests per customer turn: tool call, then answer.
- The published run cost a little more per conversation because it started with a cold cache.

## What the evals found, and what changed

Every fix is general. No fix mentions a scenario, a product or a sentence.

| # | Finding | Found by | Fix |
|---|---|---|---|
| 1 | The shop's product search only matches the exact query; the agent's natural queries ("Sommerkleid Leinen") returned nothing | First real chat | **Adapter on our side**, because the client's backend stays unchanged: retry per keyword and rank by matches |
| 2 | English customers got German replies; the German tool data pulled the model into German | Deterministic checks (3 English scenarios failed) | Language rule first in the prompt, plus a short system note after every batch of tool results |
| 3 | Duplicate tickets, and tickets created before the agent knew the issue | Deterministic checks (ticket count) | One ticket per issue; ask one question first. Legal threats still escalate immediately, as the brief requires |
| 4 | Size advice stated the chart differences the wrong way round ("38 is above your measurements") | LLM judge (policy faithfulness 2/5) | **Arithmetic moved into code:** a `recommend_size` tool computes per-size differences, and the model quotes them |
| 5 | Tickets without any way to reach the customer, and thin summaries | LLM judge (handoff summary 2.9/5) | Ask for the email before a ticket; look the order up first; put the lookup facts in the summary. **Handoff summary went from 2.9 to 3.8–4.0** |
| 6 | The agent offered to have the team "review" excluded items, creating false hope | LLM judge | No exceptions or reviews of excluded items; a defect is a warranty complaint for the team instead |
| 7 | Two scenario expectations were wrong; the agent's behaviour was the better one (for example, it asked for the new address before forwarding an address change) | Reading transcripts | Scenarios corrected |

Pass rates along the way: 24/25 → 30/35 (after adding English and harder scenarios) → 32/35 → 34/35 → 35/35.

## Calibrating the judge

The judge is a model too, and it was wrong twice. In all three repeat runs it gave **1/5** to a correct German answer that addressed nobody directly, because it had no "Sie". It also called an English reply German because it contained the German product name. Both were false alarms, confirmed by reading the transcripts.

The rubric now says product names stay German and that "Sie" is only needed when the customer is addressed, and the judge runs at effort `medium`. A recheck of both scenarios (3 runs each) scored 4–5. **Lesson for the client:** the deterministic checks decide go or no-go; the judge points at things to read, and its own mistakes need the same scrutiny.

## Known weak spots

- **Handoff summaries average 3.8/5.**
  - Legal threats escalate immediately by design, so their tickets carry little detail.
  - When a customer refers to an earlier order without naming it, the summary lacks that order number.
  - Both are acceptable trade-offs for now. With a ticket-update endpoint, both would improve.
- **35 scenarios cover the main paths and known risks, not the long tail.** Before a pilot, replay a sample of real (anonymised) tickets through the same runner.
- **Only German and English are tested.**

## Model choice

`claude-haiku-5-5` clears every bar at about $0.0004 per conversation. That is roughly $4 for 10,000 conversations. A larger model is only worth its price if it fixes something the evals show is broken, and nothing is. (A Haiku vs. Sonnet comparison on a subset is optional and not run yet.)
