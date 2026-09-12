# AI Judge Preparation

## The 30-second explanation

I built a hybrid AI-assisted financial decision agent. Deterministic Python code loads and joins the supplied records, resolves event states and dated currency conversions, simulates the next 90 days of cash flow, generates eligible payment plans, ranks them using the challenge rules, and validates the output. AI is used selectively for ambiguous image or message evidence and for concise explanations grounded in already-computed facts. The final CSV is never accepted without deterministic validation.

## Questions you should be ready to answer

### Why did you not build a UI?

The official deliverable is a batch agent and a CSV. A UI is optional and would not replace the required terminal workflow. The implementation prioritizes correctness, reproducibility, and strict output validation.

### Why not let the LLM make the final decision?

Financial safety depends on exact amounts, dates, minimum balances, deadlines, and user preferences. These are better enforced deterministically. The model may extract evidence or phrase an explanation, but it cannot bypass the simulator or validator.

### How do you handle pending transactions?

Pending debits are reserved conservatively. Pending credits are not counted until settled. Failed and cancelled events are ignored, while confirmed scheduled cash is applied on its settlement date.

### How do you use an image?

The image is joined through `images.csv` and `related_event_id`. A bounded extractor identifies document type, currency, amount labels, and dates. The result is cached and checked against the linked event context. The system does not simply choose the largest number visible in the document.

### How do you prevent prompt injection?

Messages and images are treated as untrusted evidence. Their contents can suggest financial facts but cannot override the challenge rules, execute commands, reveal secrets, or change system behavior.

### How do you choose among plans?

I generate all eligible candidates, simulate each candidate, reject any unsafe or preference-incompatible plan, and rank the survivors by deadline completion, no spending changes, total cost, start date, number of payments, and payment-option ID.

### What is the biggest limitation?

Recurrence and ambiguous evidence can be uncertain. The system addresses this with confidence-aware extraction, conservative treatment of unresolved facts, deterministic validation, and explicit logging of evidence sources. It does not invent income or expenses.

## Interview preparation checklist

Know the exact output schema. Be able to explain one public sample from each outcome category. Keep the final code, prompts, usage report, and transcript available. Know the final model names and token totals if a model was used. Explain one example of a conflict between an event and a message. Explain why `amount_safe_to_pay` and `earliest_date_for_full_payment` are calculated before optional spending changes.

The pasted platform instructions state that the interview lasts 30 minutes, remains available for 12 hours after successful submission, requires the camera to remain on, and ends on September 14, 2026 at 6:00 AM IST.
