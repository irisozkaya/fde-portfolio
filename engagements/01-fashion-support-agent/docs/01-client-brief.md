# 01 · Client Brief

> **Simulated engagement: fictional company, synthetic data.**
> *Fadenwerk* is a fictional company. A web search on 2026-11-17 (query: `"Fadenwerk" Mode Onlineshop`) found no real fashion retailer by that name.

## Who we are

Fadenwerk is a mid-sized German online fashion retailer: women's and men's clothing, shoes, underwear and swimwear. We ship only within Germany. Customers pay with PayPal, credit card, invoice or Klarna.

## The problem, in our words

> "Our customer service team is drowning. Most messages are the same few questions, and every peak (Black Friday, the end of season sales) we hire temporary staff who need weeks to learn our policies. Customers wait more than a day for an answer to 'Where is my order?'. We want an assistant that handles the repetitive part well, and hands the rest to our team without making things worse."

## The most frequent contact reasons

1. **"Where is my order?"**: order status, shipping and tracking.
2. **Returns**: "Can I return this?", "How do I start a return?", "When do I get my money back?"
3. **Size and fit**: "Which size should I order?"
4. **Product questions**: material, fit, availability of sizes.

Everything else goes to a human: complaints, payment disputes, legal threats, special requests.

## What we need

- **Automate the repetitive share** of these contacts, in German, in our tone (formal *Sie*, friendly, short).
- **Never give wrong information about orders or refunds.** A wrong "yes, you can return that" costs us more than a slow answer.
- **Hand off cleanly to our team** when the assistant should not handle something. The handoff must include a short summary, so the customer never has to repeat themselves.
- **Stay GDPR-conscious.** Never reveal one customer's order data to someone else. Order details only after the customer proves who they are.

## Constraints

- The assistant must work against our existing shop system's API. We will not change our backend for it.
- Our return policy is fixed (see `GET /policy` on the shop API). The assistant explains it; it does not make exceptions.
- We want to see evidence that it works before customers see it: measured results, known limits, and the running cost per conversation.
