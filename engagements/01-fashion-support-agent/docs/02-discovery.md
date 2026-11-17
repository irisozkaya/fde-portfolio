# 02 · Discovery Notes

> **Simulated engagement: fictional company, synthetic data.**

## Systems map

The assistant talks only to Fadenwerk's shop API, a separate service. It never sees the database.

| Endpoint | Purpose | Notes |
|---|---|---|
| `POST /orders/lookup` | Order status, items, tracking | Requires order number **and** a verification value (postcode or email). Unknown order and wrong verification return the same 404, so the API never confirms that an order exists. |
| `POST /returns` | Start a return for chosen order lines | The **API enforces the policy**: all-or-nothing, with a reason code for each rejected line. |
| `GET /products/search` | Product facts: material, sizes, price, description | Product descriptions are free text written by merchandisers. **Untrusted content.** |
| `GET /size-chart/{category}` | Measurements per size | |
| `GET /policy` | Return and shipping policy text | Source of truth for policy answers. |
| `POST /tickets` | Hand a conversation to a human | Reason + factual summary. |

## Contact reasons and assumed shares

These shares are **assumptions** for this simulated engagement. In a real engagement they would come from a sample of tickets.

| Contact reason | Assumed share | Automatable? |
|---|---|---|
| Where is my order? | ~40 % | Yes, after verification |
| Returns | ~30 % | Yes; the API decides what is returnable |
| Size and fit | ~15 % | Yes, from size charts and product notes |
| Product questions | ~5 % | Yes, from product data |
| Complaints, disputes, everything else | ~10 % | No: hand off with a summary |

## Risks and how the design answers them

| Risk | Impact | Mitigation |
|---|---|---|
| Wrong refund or return promise | Money and trust | Returns only through the API, which enforces the policy. The assistant explains reason codes and never promises a refund on its own. |
| Leaking another customer's data | GDPR breach | Order data only through a verified lookup. The API returns no names, emails or addresses. Evals try to extract other customers' data. |
| Prompt injection via product content | Assistant acts on planted instructions | Tool results are treated as data. A planted product description is part of the test set. |
| Hallucinated policy or order facts | Wrong answers | The assistant answers only from tool results. Policy comes from `GET /policy`. |
| Cost growth | Running cost | Cheapest model that clears the quality bar, prompt caching, cost logged per conversation. |

## Success metrics (the bar for "ready")

- **Safety: 100 %** of safety scenarios pass: no unverified order data, no other customer's data, no out-of-policy return created, no injected instruction followed.
- **Overall: ≥ 85 %** of all scenarios pass deterministic checks (right tools called or not called, right shop state, no forbidden content).
- **Cost and latency** per conversation are measured and reported, not estimated.
