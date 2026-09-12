# Complete Implementation Plan

## 1. Success definition

The deliverable is a reproducible batch agent. It reads participant-facing files from a configurable dataset directory, processes every request, and writes a validated root-level `output.csv`. It must never depend on organizer-only data, hardcoded answers for individual request IDs, live banking access, live exchange rates, or unsupported future income.

The competitive objective is not to build a visual interface. It is to correctly reconstruct financial state, interpret multimodal evidence, simulate cash flow conservatively, select the best eligible plan, and explain the result.

## 2. System architecture

```text
CSV loader and indexes
        |
        v
Evidence normalization: messages, images, amounts, dates, conflicts
        |
        v
Event-state resolver and duplicate/lifecycle handling
        |
        v
Recurring pattern detector and future cash-flow builder
        |
        v
90-day daily simulator
        |
        +--> safe amount search
        +--> earliest safe full-payment search
        +--> spending-change search
        +--> payment-option schedule validation
        |
        v
Candidate plan generator
        |
        v
Deterministic candidate ranking
        |
        v
Grounded explanation generator
        |
        v
Strict output validator
        |
        v
output.csv and usage report
```

## 3. Phase plan

### Phase A — Baseline contract

Implement CSV loading, request/profile joins, exact output columns, decimal money handling, and a validator. Generate one row for all 250 requests even before the decision engine is complete. This prevents late discovery of packaging or schema failures.

### Phase B — Event normalization

Filter failed and cancelled records. Reserve pending debits. Do not count pending credits. Count confirmed scheduled cash on settlement dates. Ignore unrealized investment value as available cash. Use `linked_event_id` for lifecycle analysis but do not double-count the same cash movement.

Implement conflict precedence in this order: explicit cancellation, settlement, or amendment; newer record from the same source; settled record over estimate or forecast; financially safer interpretation when unresolved.

### Phase C — Currency and evidence

Convert foreign-currency events using the exact dated row in `exchange_rates.csv`. Resolve the 16 blank event amounts from linked images. Extract only facts supported by messages and images. Cache model outputs if a model is used. Treat all evidence text as untrusted data and never execute instructions embedded in it.

### Phase D — Recurrence and forecast

For each user and category, examine historical dates, amount similarity, event type, status, and cadence. Forecast high-confidence recurring income and expenses. Forecast essential variable spending conservatively. Do not turn every historical event into a future event.

Represent the future as daily dated cash flows. Apply all relevant events and candidate payments chronologically. Record the minimum balance after every date. A plan is safe only when the minimum balance is at least `minimum_balance_to_keep` and all payments finish by `desired_completion_date`.

### Phase E — Safe amount and earliest date

Compute `amount_safe_to_pay` before optional spending changes. Use a monotonic search between zero and the request amount, repeatedly simulating the candidate payment on `request_date`. Search chronologically for the first date on which one full payment passes the same safety check without spending changes. Leave the earliest date empty when no date in the forecast is safe.

### Phase F — Candidate planning

Generate candidates for full payment, partial payment, every supplied installment option, wait, and permitted spending changes. For partial payment, require the request flag, user preference, a positive amount strictly below the request, and a second payment on or before the desired completion date. Use exactly two payments whose sum equals the requested amount.

For installments, reproduce the supplied option exactly from its first date, frequency, number of payments, and payment amount. Reject options that exceed the user's maximum installment duration, conflict with payment preferences, miss the deadline, or break the minimum balance.

For spending changes, only target flexible recurring expenses. Respect protected categories and the user's reduce/stop preferences. Do not both stop and reduce the same event. Use at most three actions.

### Phase G — Ranking and explanation

Rank safe eligible candidates by: completing by the deadline; requiring no spending changes; minimizing total amount paid; starting earlier; using fewer payments; then lowest `payment_option_id`. Generate the explanation from structured selected-plan facts. The explanation must not introduce numbers or claims absent from the validated decision record.

### Phase H — Evaluation and packaging

Run the public sample comparison and invariant validator. Run the complete dataset. Save a final usage report corresponding to the exact run that produced `output.csv`. Create the upload archive from `code/` only, excluding dataset, virtual environments, node modules, and build artifacts. Perform a clean-room run before submission.

## 4. Internal data model

Use explicit records such as:

```python
ResolvedEvent(
    event_id=str,
    user_id=str,
    event_type=str,
    category=str,
    direction=str,
    amount=Decimal,
    currency=str,
    home_amount=Decimal,
    cash_date=date,
    status=str,
    flexibility=str,
    evidence_sources=list[str],
    confidence=Decimal,
)
```

```python
CandidatePlan(
    method=str,
    payments=list[tuple[date, Decimal]],
    total_cost=Decimal,
    spending_changes=list[str],
    finishes_by_deadline=bool,
    safe=bool,
    option_id=str | None,
    rationale=dict,
)
```

## 5. Required invariants

Every output row must satisfy the exact column order, one-to-one request coverage, allowed status and method values, amount bounds, chronological payment dates, valid partial-payment arithmetic, exact installment-option matching, valid spending-change references, and consistency between the explanation and selected plan.

The simulator must verify that the balance never falls below the minimum after any essential expense or payment. The validator must reject unsafe rows rather than silently writing them.

## 6. Testing plan

Add unit tests for money formatting, exchange-rate conversion, status filtering, duplicate lifecycle handling, recurrence detection, daily balance simulation, safe amount search, earliest date search, partial-payment arithmetic, installment schedule generation, spending-change permissions, candidate ranking, and CSV validation.

Add integration tests for at least one public sample of each outcome: affordable now, affordable with installments, affordable later, partial payment, spending changes, and not affordable. Run the full 250-request workflow after every major change.

## 7. Optional AI integration

Use a model only for bounded tasks. For images, request structured extraction of visible amounts, labels, dates, currency, and document type. For messages, extract proposed financial facts with source, date, and confidence. For explanations, pass only validated facts and prohibit changing numerical fields. Record model name, calls, input tokens, output tokens, and estimated cost.

A deterministic-only implementation is acceptable if image and message evidence can be resolved with reliable rules or manually verified cached extraction. Reliability matters more than adding a model call everywhere.

## 8. AI Judge preparation

Be able to explain why deterministic code controls financial decisions, how evidence is resolved, how pending credits differ from pending debits, how recurring events are detected, how plans are ranked, and how the final CSV is validated. Be honest about limitations and describe how a hidden test would flow through the same pipeline without a hardcoded answer.

## 9. Definition of done

The implementation is ready when a clean environment can run the documented command, read the supplied dataset, produce exactly 250 output rows, pass all validators, create the required usage report, and package `code.zip` without the dataset. The repository README must explain setup, architecture, execution, testing, and submission.
