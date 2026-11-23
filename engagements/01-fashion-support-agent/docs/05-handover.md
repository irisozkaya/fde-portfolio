# 05 · Handover

> **Simulated engagement: fictional company, synthetic data.**

What Fadenwerk's team needs to run, evaluate and extend the assistant.

## Run it locally

```bash
cd engagements/01-fashion-support-agent
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env          # your own key; .env is gitignored
.venv/bin/uvicorn shop_api.main:app --port 8001 &    # mock shop (rebuilt with fresh data on each start)
.venv/bin/uvicorn agent.main:app --port 8000         # agent + chat UI → http://localhost:8000
```

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Required for the agent and evals |
| `AGENT_MODEL` | `claude-haiku-5-5` | Model for the agent |
| `AGENT_EFFORT` | `low` | Reasoning effort |
| `SHOP_URL` | `http://localhost:8001` | Shop API base URL |
| `SHOP_DB_PATH`, `SHOP_TODAY` | `./shop.db`, today | Mock shop data file and reference date |

## Test and evaluate

```bash
.venv/bin/pytest                                       # unit tests: no API calls, run in CI on every push
.venv/bin/python -m evals.runner --subset smoke        # 5 scenarios, ~$0.005
.venv/bin/python -m evals.runner --subset all --judge  # 35 scenarios + LLM judge, ~$0.04
.venv/bin/python -m evals.report evals/results/<run_dir>  # Markdown summary of one run
```

- **Before every prompt or tool change goes live, run the full suite.** Safety scenarios must stay at 100 %.
- Add a scenario for every real failure you see in production. Write the fix so it covers the whole class of failures, not one sentence.
- Every API call is logged in `logs/spend.json`. The runner refuses to start when the ledger reaches the $5 cap; `--allow-over-budget` overrides this.

## Cost and latency (measured)

From three independent runs of the full suite (105 conversations, 156 customer turns) on `claude-haiku-5-5`, effort `low`. The runs were spaced longer than the prompt-cache lifetime, so no run reused another run's conversations:

| Metric | Value |
|---|---|
| Cost per conversation | ≈ $0.00085 (max $0.0014) |
| Cost per customer turn | ≈ $0.0006 |
| Cost for 10,000 conversations | ≈ $8.50 |
| Latency per customer turn | p50 3.4 s · p90 4.7 s |
| Model requests per customer turn | 1.85 on average (tool call, then answer) |
| Share of input tokens served from the prompt cache | 62 % |

Prices are from the Anthropic pricing page (checked 2026-11-17) and live in `agent/pricing.py`. Update them there when prices change.

## Known limits

- **One language pair.** German and English are tested. Other languages work only by accident.
- **No customer accounts.** Verification is order number + postcode or email. A logged-in chat would remove that step.
- **Tickets are fire-and-forget.** The shop API cannot update a ticket, so details a customer adds afterwards stay in the chat transcript.
- **The eval set is small (35 scenarios).** It covers the main paths and the known risks, not the long tail. Real transcripts should grow it.
- **Legal threats need an email.** The agent asks only for the email, then escalates. If the customer will not give one, the ticket has no way to reach them.
- **The $5 cap is enforced by the eval runner only.** The chat server records spend in the same ledger but does not stop at the cap; a deployment needs the daily cap described below.

## Next steps

1. **Pilot on real tickets.** Replay 200 anonymised past tickets through the eval runner before any customer sees the assistant.
2. **Voice channel.** The loop is channel-agnostic; a phone front end (speech-to-text and text-to-speech) is the next interface.
3. **A real shop integration.** Swap the mock client for the production API: the tools stay the same, only `ShopClient` changes.
4. **Ticket updates.** With an update endpoint, details added after handoff could go into the existing ticket.

## Deployment runbook: NOT EXECUTED

This engagement ships no live deployment; the demo is a replay page. If Fadenwerk deploys it, the plan is:

- **Services:**
  - `agent` (FastAPI, serves the chat UI), with 1–2 small instances.
  - The shop API is Fadenwerk's own system.
- **Secrets:** the Anthropic key lives in the platform's secret store, never in the image or repo.
- **Access control:** the chat sits behind the shop's login, or a signed session token from the shop frontend. That also replaces the postcode or email verification.
- **Abuse and spend control:**
  - A per-session message cap and a per-IP rate limit.
  - A daily spend cap in the app, using the same ledger idea as here.
  - A monthly spend limit in the Anthropic Console as a backstop.
- **Conversation state:** move conversations from memory to Redis or Postgres, so instances can restart and scale.
- **Monitoring:**
  - Log tokens, cost, latency and tool errors per turn; this already exists as JSON lines.
  - Alert on the fallback-reply rate, the handoff rate and the cost per conversation.
  - Run the eval suite nightly against the production prompt.
- **Data protection (GDPR):**
  - Conversation logs contain personal data. Define retention (for example 30 days) and deletion.
  - Keep a data processing agreement with the model provider.
