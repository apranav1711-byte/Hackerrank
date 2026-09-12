# Repository Audit: HackerRank Orchestrate — Buy or Wait?

## Executive conclusion

This repository contains a deterministic Python decision engine for the **Buy or Wait?** financial-affordability challenge. Its core approach is sound: reconstruct a 90-day cash-flow forecast, preserve a user-defined minimum balance, calculate a safe payment amount, generate candidate payment plans, and emit the required eight-column CSV.

The requested Priority 0 and core correctness fixes are now implemented. Ten regression tests pass, Python compilation passes, packaging passes, and the local quality gate correctly distinguishes skipped dataset checks from completed checks. The official dataset is still absent from this checkout, so the public benchmark and full 250-request evaluation remain unverified. The repository should not be called fully submission-ready until those dataset-backed checks pass.

## Runtime architecture

`code/main.py` is the execution entry point. `run()` loads the CSV data, resolves image-linked amounts, and calls `decide()` for each request. `decide()` normalizes financial events, builds a 90-day forecast, calculates the maximum safe payment, finds the earliest safe full-payment date, evaluates payment options and spending changes, ranks eligible candidates, and writes the result.

`code/data_loader.py` reads and indexes the CSV files. `code/evidence.py` performs bounded OCR when available and falls back to verified image mappings. `code/validator.py` performs basic output-contract checks. `check_all.py` runs tests, optional dataset-backed evaluation, packaging, and audit-log validation.

## Changes implemented

| Area | Change | Result |
|---|---|---|
| Image resolution | `run()` now calls `resolve_image_amounts()` using `dataset/media/images` and passes the resolved map into event normalization. | Unseen blank image-linked events can be resolved by OCR when OCR is available. |
| Optional OCR | Pillow is imported lazily inside the image-extraction function. | Missing Pillow no longer prevents the deterministic engine from starting. |
| Fallback evidence | The verified event-to-amount mapping remains available as a deterministic fallback. | Known challenge images remain reproducible without OCR. |
| Audit log | An ignored `log.txt` was created with a current session entry. The quality gate now checks for a non-empty tool tag rather than hardcoding another harness name. | Local audit-log validation passes. |
| Dataset workflow | `check_all.py` accepts `--dataset-dir`, and the benchmark runner accepts the same argument. | The official dataset can live outside the repository. |
| Honest quality gate | Missing dataset checks are reported as `SKIPPED`, not `PASSED`. | Local success no longer masquerades as full submission validation. |
| Linked events | Events are grouped by lifecycle link and selected through deterministic cancellation, amendment, status, and date precedence. | The old first-row-wins bug is removed. |
| Exchange rates | Missing direct or inverse dated rates now raise an explicit `ValueError`. | Foreign amounts cannot silently be treated as home-currency amounts. |
| Regression tests | Tests cover missing rates, settled-over-pending selection, and blank amounts without evidence. | The new behavior is protected. |

## Verification performed

| Check | Result | Interpretation |
|---|---:|---|
| Unit tests | **10 passed** | Existing tests and new regression tests pass. |
| Python compilation | **Passed** | Source files compile successfully. |
| `git diff --check` | **Passed** | No whitespace errors were found. |
| Packaging | **Passed** | `code.zip` contains the expected source and usage report. |
| Audit-log validation | **Passed** | The ignored log contains a session start and valid tool tag. |
| Public benchmark | **Skipped** | The official dataset is not present in this checkout. |
| Full evaluation | **Skipped** | The official dataset is not present in this checkout. |

The honest interpretation is: **the local engineering checks pass, but the competitive result is unknown until the official dataset is run.**

## Remaining high-risk issues

### 1. Dataset-backed validation is still the most important blocker

The README claims 25 public samples and 250 full-dataset requests were previously matched, but those results cannot be reproduced from this clone. Obtain the official starter dataset outside the repository and run:

```bash
python3 check_all.py --dataset-dir /path/to/hackerrank-orchestrate-september26/dataset
```

Do not trust the previous benchmark claim until the current commit passes the benchmark and full validator.

### 2. OCR behavior still needs real-media validation

The runtime path is now connected, but OCR is inherently error-prone. Test an image not present in `VERIFIED_IMAGE_AMOUNTS`. Confirm that the parser selects the correct labeled amount rather than the largest visible number, especially for payslips with gross pay, deductions, net pay, and totals.

If the target runner does not install `requirements.txt`, every blank event must be covered by the verified fallback mapping or the implementation must include another available image-reading strategy.

### 3. Linked-event precedence needs more fixtures

The new implementation fixes the first-row-wins problem and covers settled versus pending. Add tests for cancelled versus original, amended versus settled, same-day records, different sources, and linked rows where the cancellation itself has a different event date. Compare these cases against the official dataset’s actual status vocabulary.

The current precedence is a defensible deterministic policy, but it should be calibrated against the challenge data before submission.

### 4. Message interpretation remains a major correctness risk

`message_salary_info()` still scans user-wide messages and uses broad substring matching. An unrelated message containing words such as “pay,” “leaving,” or “cancelled” can affect salary projection. This should be tightened before final submission.

Use relevance based on `request_id`, `related_event_id`, user scope, source, and message date. Parse explicit salary labels rather than simply selecting the first currency amount. Add tests for unrelated payment messages, multiple amounts, contract termination, salary amendments, and cancellation language.

### 5. Output validation is not yet strong enough

`code/validator.py` checks columns, IDs, numeric bounds, allowed enums, and explanation presence. It does not fully validate payment-plan syntax, chronology, partial-payment sums, installment-option matching, status-method consistency, or spending-change eligibility.

This is an important pre-submission improvement because it can detect engine bugs before upload, even though it cannot measure hidden-ground-truth accuracy.

### 6. Spending-change optimization is not fully ranked

`find_spending_candidates()` returns the first safe combination after sorting individual actions by savings. It does not enumerate and rank every safe combination according to the challenge’s complete plan-ranking rules. A less disruptive combination may be skipped.

Enumerate the bounded combinations of up to three actions, reject duplicate-event actions, and rank all safe candidates deterministically.

### 7. End-to-end test coverage remains small

Ten tests are better than seven, but they still do not cover the full decision surface. Add synthetic complete-request fixtures for full payment, wait, partial payment, installments, spending changes, not affordable, salary termination, foreign exchange, pending credits, recurring expenses, and conflicts.

## Recommended order before submission

| Priority | Required action | Why |
|---:|---|---|
| P0 | Run the current commit against the official dataset. | This is the only way to know whether the changes preserve or improve benchmark accuracy. |
| P0 | Validate every blank image amount, including at least one real OCR path. | Blank amounts directly affect forecast safety and recommendations. |
| P1 | Tighten message relevance and salary parsing. | Current broad matching can create silent financial-state errors. |
| P1 | Add strict output-contract validation. | Invalid plans can lose points even when the recommendation is conceptually correct. |
| P1 | Expand linked-event conflict tests and compare with official records. | Lifecycle interpretation changes cash flow. |
| P1 | Enumerate and rank all spending-change combinations. | Current selection is order-dependent. |
| P2 | Add complete synthetic end-to-end fixtures. | The engine has too many branches for helper-only testing. |
| P2 | Update README benchmark claims after the current run. | Documentation must report reproducible results from the final commit. |

## Honest competitive judgment

The project has a credible foundation and a good performance profile. A deterministic, auditable engine is appropriate for this challenge, and adding an LLM would probably increase complexity and failure modes unless the dataset contains genuinely ambiguous evidence that deterministic parsing cannot handle.

However, this is not yet an “all or nothing” winning submission. The largest uncertainty is not code execution; it is **decision accuracy on the official dataset**. The current implementation contains several heuristic areas that can silently produce wrong financial forecasts: message parsing, recurring-expense inference, lifecycle conflict handling, and payment-plan ranking. Those areas should be improved and benchmarked before spending time on cosmetic documentation or model integration.

The best next move is to run the official dataset now, inspect every mismatch, and use those mismatches to guide targeted fixes. Do not claim 100% accuracy again until the current commit has produced the evidence.

## References

[1]: problem_statement.md "Buy or Wait? challenge specification"

[2]: AGENTS.md "Repository agent instructions and project contract"

[3]: code/main.py "Deterministic cash-flow and decision engine"

[4]: code/data_loader.py "Dataset loading and indexing"

[5]: code/evidence.py "OCR and image evidence extraction"

[6]: code/validator.py "Output schema validator"

[7]: check_all.py "Master quality gate"

[8]: README.md "Repository overview and benchmark claims"

[9]: data/README.md "Local dataset setup instructions"
