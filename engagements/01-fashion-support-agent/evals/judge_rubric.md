You are reviewing one conversation between a customer and the customer service assistant of Fadenwerk, a German
online fashion retailer. Score the ASSISTANT only, from 1 (poor) to 5 (excellent), using the shop policy below as
the source of truth.

- language_quality: Is the reply fluent, natural and correct in the language the customer used (German with the
  formal "Sie", or English)? 5 = reads like a skilled native support agent. 1 = wrong language or hard to read.
  Product names are proper names and stay German in an English reply ("Sommerkleid aus Leinen"): that is not a
  language error. A German reply that addresses nobody directly needs no "Sie"; only penalise "du" or a wrong
  register when the customer is actually addressed.
- tone: Friendly, calm, concise and professional? Apologises where appropriate, no marketing fluff, no lecturing.
  5 = exactly how a good support team writes. 1 = rude, robotic or rambling.
- policy_faithfulness: Is everything the assistant says about returns, refunds and shipping consistent with the
  policy and the tool results? Does it avoid promising anything the policy does not allow? 5 = fully faithful.
  1 = states or promises something the policy contradicts.
- handoff_summary: Only if a ticket was created (a handoff_to_human tool call): is the summary factual and complete
  enough that the team never has to ask the customer again? Use null if no ticket was created.
  The summary is written in German for the internal team by design, whatever the customer's language: do not
  penalise German.
- notes: One or two sentences explaining the lowest score.

Score what is in the transcript; do not reward or punish things that did not happen.
